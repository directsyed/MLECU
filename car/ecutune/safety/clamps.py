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
    # int() on each comparison, not on the difference: numpy bools do not support `-`
    # (TypeError: "numpy boolean subtract"). CellEdit.new_value is TYPED float but nothing
    # coerces it, so a caller handing in an np.float64 -- which any array-derived proposal
    # naturally would -- crashed clamp_ve_rate_limit here. Found 2026-08-27.
    return int(x > 0) - int(x < 0)


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
        load = t.cell_x(e) if t is not None else None
        ceiling = ctx.safety.timing_ceiling_for(rpm if rpm is not None else 0.0, load)
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


def clamp_diagnosis_agreement(prop: Proposal, ctx: ClampContext) -> ClampResult:
    """GATE — the LLM POINTS, it does not COMMAND (Syed, 2026-08-05).

    E4 (2026-08-04) showed the closed loop failing structurally, not for want of a better model.
    At one operating point the observable is scalar and the state is 3-dimensional, so any of
    the three beliefs can null the trim: the diagnosis was not advice, it was THE MISSING
    CONSTRAINT that made the problem solvable — and the layer had no independent basis on which
    to disagree with it. One slip in twelve iterations permanently bent a table, and nine of
    forty-two episodes ended with a SECOND belief corrupted that was never faulty.

    With `algorithms.identify` the layer now reaches its own verdict from three probe points.
    This gate requires the two to agree on WHICH TABLE moves before anything is written:

      * layer cannot identify (degenerate, or no single fault fits) -> ABORT, escalate
      * layer names a different knob than the proposal moves        -> ABORT, escalate
      * layer names NO_EDIT (leak/healthy) and the proposal edits   -> ABORT, escalate

    Comparison is by KNOB, not by label: `maf_low` and `maf_high` move the same table and the
    direction comes from the measured trim, so disagreeing on the label while agreeing on the
    table is not a conflict.

    When `ctx.fault_estimate` is absent the gate is INERT — it cannot manufacture a second
    opinion it does not have, and refusing every proposal on a single-point log would break the
    existing convergence path. Absence is visible in the audit trail rather than silently
    treated as agreement.

    Replayed over all 8 masking events from the 2026-08-04 E4 run, evaluated on the diagnosis
    that actually caused each edit: 8/8 refused.
    """
    est = ctx.fault_estimate
    if est is None or not prop.edits:
        return ClampResult(True, tuple(prop.edits))

    # Compare only edits that MATERIALLY change a value. propose_idle_correction always emits
    # one edit per table and zeroes the non-selected weights, so a split of (0, 1, 0) still
    # carries three CellEdits — two of them no-ops writing the current value back. Comparing
    # raw edit targets made the gate report knob_mismatch even when both sides agreed.
    material = {e.table_id for e in prop.edits
                if not math.isclose(e.new_value, _cur(ctx, e), rel_tol=1e-9, abs_tol=1e-12)}
    if not material:
        return ClampResult(True, tuple(prop.edits))         # nothing actually moves

    if not getattr(est, "identifiable", False):
        return ClampResult(False, (), _viol_all("diagnosis_agreement", ctx, prop, "aborted"),
                           aborted_by="diagnosis_agreement:not_identifiable")

    dl_knob = est.knob() if hasattr(est, "knob") else None
    if dl_knob is None:
        return ClampResult(False, (), _viol_all("diagnosis_agreement", ctx, prop, "aborted"),
                           aborted_by="diagnosis_agreement:layer_says_no_table_edit")
    if material != {dl_knob}:
        return ClampResult(False, (), _viol_all("diagnosis_agreement", ctx, prop, "aborted"),
                           aborted_by="diagnosis_agreement:knob_mismatch")
    return ClampResult(True, tuple(prop.edits))


def clamp_belief_envelope(prop: Proposal, ctx: ClampContext) -> ClampResult:
    """MODIFIER — bound each belief's DISTANCE from the stock ROM, not just its per-step rate.

    `clamp_ve_rate_limit` is a velocity bound: no cell moves more than 3% per iteration. Nothing
    bounded DISPLACEMENT, so twelve iterations compounds to 43% and a sustained wrong diagnosis
    walks a belief arbitrarily far from a calibration that was known-good. The "provable bound"
    in the safety story was on how FAST we can be wrong, not on how wrong we can end up.

    These bounds are physical, not statistical: an OEM injector does not flow 25% off spec. An
    edit that wants to leave the envelope is evidence the DIAGNOSIS is wrong, so the edit is
    clamped to the boundary and the violation recorded — repeated envelope hits are an
    escalation trigger, not a routine event.

    Inert when no baseline is supplied (e.g. the sim harness before a stock ROM is archived).
    """
    if prop.targets_kind not in _FUEL_TARGETS or ctx.baseline_tables is None:
        return ClampResult(True, tuple(prop.edits))
    out: list[CellEdit] = []
    viols: list[ClampViolation] = []
    for e in prop.edits:
        try:
            base = ctx.baseline_tables.current(e)
        except (KeyError, IndexError):
            out.append(e)
            continue
        frac = ctx.safety.belief_envelope.get(e.table_id, ctx.safety.belief_envelope_default)
        if math.isnan(base) or abs(base) < ctx.safety.zero_base_eps:
            out.append(e)
            continue
        lo, hi = base * (1.0 - frac), base * (1.0 + frac)
        lo, hi = min(lo, hi), max(lo, hi)
        if lo <= e.new_value <= hi:
            out.append(e)
            continue
        bounded = min(hi, max(lo, e.new_value))
        out.append(CellEdit(e.table_id, e.row, e.col, bounded, e.reason))
        viols.append(ClampViolation("belief_envelope", e.table_id, e.row, e.col,
                                    e.new_value, bounded, "envelope_limited"))
    return ClampResult(True, tuple(out), tuple(viols))


def clamp_sensor_calibration(prop: Proposal, ctx: ClampContext) -> ClampResult:
    """MODIFIER — bound a SENSOR recalibration by evidence and displacement, not by velocity.

    Why this clamp exists (2026-08-27). `clamp_ve_rate_limit` bounds a fuel edit to 3% per
    iteration because idle convergence chases a target that moves as the loop corrects it —
    creeping is the whole point. A MAF transfer curve is a different kind of object: it is a
    MEASUREMENT that is wrong by a fixed amount, established over ~20k steady samples. Bounding
    its speed would mean eleven flash cycles to reach a correction the data already supports,
    on a car whose ECU is currently at ~75% of its total fuel-correction authority. So the
    bound moves from "how fast" to "how far, and on what evidence".

    Three independent bounds, applied in order:
      1. EVIDENCE  — a breakpoint no log data supports does not move at all. Inert (skipped)
                     when ctx.sensor_sample_counts is absent, matching belief_envelope's
                     treatment of a missing baseline.
      2. DISPLACEMENT — |new/current - 1| <= safety.max_sensor_recal. Clamped to the boundary,
                     sign preserved, never flipped.
      3. MONOTONICITY — the resulting curve must stay strictly ascending. A transfer curve that
                     doubles back is physically meaningless AND unflashable: romread.plausible()
                     rejects non-monotonic axes, so this catches at proposal time what would
                     otherwise fail at write time. Only EDITED cells are moved to restore order;
                     a pre-existing violation in untouched cells is not ours to silently repair.

    Note the deliberate asymmetry with the fuel clamps: those key off `targets_kind == "fuel"`,
    this off `"sensor"`, so the two paths cannot interfere. A sensor proposal is untouched by
    the 3% rate limit, and a fuel proposal is untouched by this.
    """
    if prop.targets_kind != "sensor":
        return ClampResult(True, tuple(prop.edits))

    cap = ctx.safety.max_sensor_recal
    counts = ctx.sensor_sample_counts or {}
    out: list[CellEdit] = []
    viols: list[ClampViolation] = []

    for e in prop.edits:
        cur = _cur(ctx, e)

        # 1. EVIDENCE
        per_table = counts.get(e.table_id)
        if per_table is not None:
            n = per_table[e.col] if e.col < len(per_table) else 0
            if n < ctx.safety.min_sensor_samples:
                keep = e.new_value if math.isnan(cur) else cur
                out.append(CellEdit(e.table_id, e.row, e.col, keep, e.reason))
                if keep != e.new_value:
                    viols.append(ClampViolation("sensor_calibration", e.table_id, e.row, e.col,
                                                e.new_value, keep, "insufficient_evidence"))
                continue

        # 2. DISPLACEMENT — per iteration, against the table's current value
        if math.isnan(cur) or abs(cur) < ctx.safety.zero_base_eps:
            out.append(e)
            continue
        lo, hi = cur * (1.0 - cap), cur * (1.0 + cap)
        lo, hi = min(lo, hi), max(lo, hi)

        # 2b. CUMULATIVE DISPLACEMENT — against the ARCHIVED STOCK ROM. Step bounds do not bound
        # distance: enough small iterations walk a sensor belief arbitrarily far from a
        # calibration that was known-good. Inert without a baseline.
        action = "recal_limited"
        if ctx.baseline_tables is not None:
            try:
                base = ctx.baseline_tables.current(e)
            except (KeyError, IndexError):
                base = float("nan")
            if not math.isnan(base) and abs(base) >= ctx.safety.zero_base_eps:
                env = ctx.safety.sensor_envelope
                blo, bhi = base * (1.0 - env), base * (1.0 + env)
                blo, bhi = min(blo, bhi), max(blo, bhi)
                if blo > lo or bhi < hi:
                    lo, hi = max(lo, blo), min(hi, bhi)
                    if not (lo <= e.new_value <= hi):
                        action = "sensor_envelope_limited"

        if lo <= e.new_value <= hi:
            out.append(e)
        else:
            bounded = min(hi, max(lo, e.new_value))
            out.append(CellEdit(e.table_id, e.row, e.col, bounded, e.reason))
            viols.append(ClampViolation("sensor_calibration", e.table_id, e.row, e.col,
                                        e.new_value, bounded, action))

    # 3. MONOTONICITY — cross-cell, so it runs once over the surviving edits per table.
    if ctx.safety.sensor_require_monotonic:
        out, mono_viols = _enforce_monotonic(out, ctx)
        viols.extend(mono_viols)

    return ClampResult(True, tuple(out), tuple(viols))


def _enforce_monotonic(edits: list[CellEdit],
                       ctx: ClampContext) -> tuple[list[CellEdit], list[ClampViolation]]:
    """Keep each edited curve strictly ascending, moving ONLY edited cells.

    Builds the curve that would result from these edits, then walks it in order. When an edited
    cell would sit at or below its predecessor it is raised to just above it; when it would sit
    at or above its successor it is lowered to just below. Untouched cells are left exactly as
    they are — if the STOCK curve is already non-monotonic somewhere, that is a finding to
    report, not something to quietly rewrite.
    """
    by_table: dict[str, dict[int, CellEdit]] = {}
    for e in edits:
        by_table.setdefault(e.table_id, {})[e.col] = e
    viols: list[ClampViolation] = []
    replaced: dict[tuple[str, int], CellEdit] = {}

    for table_id, cell_edits in by_table.items():
        t = ctx.tables.tables.get(table_id)
        if t is None or t.kind != "curve_1d":
            continue
        stock = [float(v) for v in t.values.ravel()]
        curve = list(stock)
        for col, e in cell_edits.items():
            if 0 <= col < len(curve):
                curve[col] = e.new_value
        # The separation must SURVIVE STORAGE ENCODING. zero_base_eps (1e-9) does not: these
        # curves are stored as float32, whose relative precision is ~1.2e-7, so at a value of
        # 30 a 1e-9 gap collapses to equality on write and the "strictly ascending" guarantee
        # silently evaporates in the flashed image. Found 2026-08-27 by the write path's own
        # read-back check. A relative gap clears float32 with two orders of margin.
        def _sep(v: float) -> float:
            return max(ctx.safety.zero_base_eps, abs(v) * 1e-5)

        for col in sorted(cell_edits):
            if not (0 <= col < len(curve)):
                continue
            lo = curve[col - 1] + _sep(curve[col - 1]) if col > 0 else -math.inf
            hi = curve[col + 1] - _sep(curve[col + 1]) if col + 1 < len(curve) else math.inf
            if lo > hi:
                # Boxed in — the neighbours leave no ordered slot. This only happens when the
                # STOCK curve is already non-monotonic here, so fall back to the cell's CURRENT
                # value (NOT curve[col], which is the proposal we are adjudicating). Refusing to
                # move is right: silently repairing cells we were not asked to touch would hide
                # a bad ROM read or a bad definition behind our own edit.
                lo = hi = stock[col]
            bounded = min(hi, max(lo, curve[col]))
            if bounded != curve[col]:
                e = cell_edits[col]
                viols.append(ClampViolation("sensor_calibration", table_id, e.row, col,
                                            e.new_value, bounded, "monotonicity_limited"))
                curve[col] = bounded
                replaced[(table_id, col)] = CellEdit(table_id, e.row, col, bounded, e.reason)

    if not replaced:
        return edits, viols
    return [replaced.get((e.table_id, e.col), e) for e in edits], viols
