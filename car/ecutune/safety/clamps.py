"""The hard clamps — each a PURE function (Proposal, ClampContext) -> ClampResult.

This is the safety boundary of the whole project. Mirrors corpus_pipeline/core/gates.py's
pure-`evaluate` shape, but richer: a clamp must produce an AUDIT TRAIL (every modification is
recorded as a ClampViolation), because auditability is itself a safety property — and a future
training signal.

Two kinds of clamp:
  * GATES (knock, ordering, boost) — reject the WHOLE proposal: ok=False, no edits survive.
  * MODIFIERS (afr_floor, timing_ceiling, ve_rate_limit) — bound individual edits: ok=True,
    edits pass through possibly rate-limited / floored.

Pipeline order (see pipeline.py) puts fail-fast gates first and ve_rate_limit late so survivors
are bounded; afr_floor is dead last so it is the FINAL hard word on any boost AFR cell (it may
richen past the rate limit — rich is the safe direction; sitting lean at boost is the hazard).
"""
from __future__ import annotations

import math

from ..core import units
from ..core.models import CellEdit, ClampContext, ClampResult, ClampViolation, Proposal

_FUEL_TARGETS = ("fuel",)


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def _cur(ctx: ClampContext, e: CellEdit) -> float:
    """Current live table value at the edit's cell, or NaN if the table/cell is absent."""
    try:
        return ctx.tables.current(e)
    except (KeyError, IndexError):
        return float("nan")


def _viol_all(name: str, ctx: ClampContext, prop: Proposal, action: str) -> tuple[ClampViolation, ...]:
    return tuple(
        ClampViolation(name, e.table_id, e.row, e.col, e.new_value, _cur(ctx, e), action)
        for e in prop.edits
    )


# --- GATES ------------------------------------------------------------------

def clamp_knock_auto_abort(prop: Proposal, ctx: ClampContext) -> ClampResult:
    """Knock feedback active => STOP. Hard abort, no edit survives. The single most important
    clamp: a knock event means the engine is already at risk; we do not negotiate."""
    if ctx.knock_active:
        return ClampResult(False, (), _viol_all("knock_auto_abort", ctx, prop, "aborted"),
                           aborted_by="knock_auto_abort")
    return ClampResult(True, tuple(prop.edits))


def clamp_fuel_before_timing(prop: Proposal, ctx: ClampContext) -> ClampResult:
    """Never advance timing while fuel is still wrong. A timing proposal is deferred until the
    fuel trims have converged (a lean miss + extra timing = detonation)."""
    if prop.targets_kind == "timing" and not ctx.fuel_trims_converged:
        return ClampResult(False, (), _viol_all("fuel_before_timing", ctx, prop, "deferred"))
    return ClampResult(True, tuple(prop.edits))


def clamp_steady_before_transient(prop: Proposal, ctx: ClampContext) -> ClampResult:
    """Tune steady-state before transients. A proposal flagged transient (metadata.transient)
    is deferred until steady-state is in tolerance."""
    if prop.metadata.get("transient") and not ctx.steady_state_ok:
        return ClampResult(False, (), _viol_all("steady_before_transient", ctx, prop, "deferred"))
    return ClampResult(True, tuple(prop.edits))


def clamp_boost_gate(prop: Proposal, ctx: ClampContext) -> ClampResult:
    """Boost edits stay gated until (a) trims within +/-5%, (b) wideband tracking command,
    (c) boost control verified against the VF48. Any one unmet => defer the whole proposal."""
    if prop.targets_kind == "boost":
        ungated = (
            abs(ctx.max_trim_abs) <= ctx.safety.boost_trim_tol
            and ctx.wideband_tracking
            and ctx.boost_control_verified
        )
        if not ungated:
            return ClampResult(False, (), _viol_all("boost_gate", ctx, prop, "deferred"))
    return ClampResult(True, tuple(prop.edits))


# --- MODIFIERS --------------------------------------------------------------

def clamp_timing_row_ceiling(prop: Proposal, ctx: ClampContext) -> ClampResult:
    """Floor each timing cell to its per-RPM-row ceiling (config). Only acts on timing proposals."""
    if prop.targets_kind != "timing":
        return ClampResult(True, tuple(prop.edits))
    out: list[CellEdit] = []
    viols: list[ClampViolation] = []
    for e in prop.edits:
        t = ctx.tables.tables.get(e.table_id)
        rpm = t.cell_rpm(e) if t is not None else None
        ceiling = ctx.safety.timing_ceiling_for(rpm if rpm is not None else 0.0)
        if e.new_value > ceiling:
            out.append(CellEdit(e.table_id, e.row, e.col, ceiling, e.reason))
            viols.append(ClampViolation("timing_row_ceiling", e.table_id, e.row, e.col,
                                        e.new_value, ceiling, "floored"))
        else:
            out.append(e)
    return ClampResult(True, tuple(out), tuple(viols))


def clamp_ve_rate_limit(prop: Proposal, ctx: ClampContext) -> ClampResult:
    """The provable bound: no fuel/VE cell moves more than +/-max_ve_step (3%) per iteration.
    Clamps |new - current| to <= 3%*|current|, preserving the sign of the requested change
    (never overshoots, never flips). This same limit is the controller's anti-windup."""
    if prop.targets_kind not in _FUEL_TARGETS:
        return ClampResult(True, tuple(prop.edits))
    step = ctx.safety.max_ve_step
    eps = ctx.safety.zero_base_eps
    out: list[CellEdit] = []
    viols: list[ClampViolation] = []
    for e in prop.edits:
        cur = _cur(ctx, e)
        if math.isnan(cur) or abs(cur) < eps:
            # No relative bound against a ~zero base: refuse movement, flag it (a 0-valued
            # fuel cell is degenerate; we will not let it jump by an unbounded relative amount).
            keep = e.new_value if math.isnan(cur) else cur
            out.append(CellEdit(e.table_id, e.row, e.col, keep, e.reason))
            if not math.isnan(cur) and keep != e.new_value:
                viols.append(ClampViolation("ve_rate_limit", e.table_id, e.row, e.col,
                                            e.new_value, keep, "rate_limited"))
            continue
        delta = e.new_value - cur
        max_delta = step * abs(cur)
        if abs(delta) > max_delta:
            clamped = cur + _sign(delta) * max_delta
            out.append(CellEdit(e.table_id, e.row, e.col, clamped, e.reason))
            viols.append(ClampViolation("ve_rate_limit", e.table_id, e.row, e.col,
                                        e.new_value, clamped, "rate_limited"))
        else:
            out.append(e)
    return ClampResult(True, tuple(out), tuple(viols))


def clamp_afr_floor(prop: Proposal, ctx: ClampContext) -> ClampResult:
    """HARD final guarantee: never command leaner than the AFR floor at boost. Acts on AFR/lambda
    target tables (e.g. Primary Open Loop Fueling) at boost-region cells (load >= threshold). A
    too-lean target is floored to exactly the floor — richening even past the rate limit, because
    commanding lean at boost is the engine-grenade case and rich is the safe direction. Runs LAST."""
    floor = ctx.safety.afr_floor
    out: list[CellEdit] = []
    viols: list[ClampViolation] = []
    for e in prop.edits:
        t = ctx.tables.tables.get(e.table_id)
        unit = (t.units.upper() if t is not None else "")
        if unit not in ("AFR", "LAMBDA"):
            out.append(e)
            continue
        load = t.cell_x(e)
        if load is None or load < ctx.safety.boost_load_threshold:
            out.append(e)
            continue
        proposed_afr = e.new_value if unit == "AFR" else units.lambda_to_afr(e.new_value)
        if proposed_afr > floor:  # leaner than allowed at boost
            safe_val = floor if unit == "AFR" else units.afr_to_lambda(floor)
            out.append(CellEdit(e.table_id, e.row, e.col, safe_val, e.reason))
            viols.append(ClampViolation("afr_floor", e.table_id, e.row, e.col,
                                        e.new_value, safe_val, "floored"))
        else:
            out.append(e)
    return ClampResult(True, tuple(out), tuple(viols))
