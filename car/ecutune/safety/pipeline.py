"""Compose the ordered clamps into a single fold. apply_clamps() is the ONLY way a Proposal
becomes a set of edits eligible to touch a Table.

Order rationale:
  1. knock_auto_abort      — fail fast on the hardest hard-stop.
  2. fuel_before_timing    — ordering gates: reject out-of-sequence proposals before any work.
  3. steady_before_transient
  4. boost_gate            — defer boost edits until the three boost preconditions hold.
  5. timing_row_ceiling    — bound timing edits.
  6. ve_rate_limit         — bound every fuel edit to +/-3% per iteration.
  7. afr_floor             — LAST: the final hard word on boost AFR cells (may richen past the
                             rate limit; rich is safe, lean-at-boost is the hazard).

Each modifier consumes the prior clamp's surviving edits; any gate that returns ok=False
short-circuits the whole proposal (no partial writes).
"""
from __future__ import annotations

from dataclasses import replace

from ..core.models import ClampContext, ClampResult, Proposal
from . import clamps

CLAMP_PIPELINE = (
    clamps.clamp_knock_auto_abort,
    clamps.clamp_fuel_before_timing,
    clamps.clamp_steady_before_transient,
    clamps.clamp_boost_gate,
    clamps.clamp_timing_row_ceiling,
    clamps.clamp_ve_rate_limit,
    clamps.clamp_afr_floor,
)


def apply_clamps(prop: Proposal, ctx: ClampContext, pipeline=CLAMP_PIPELINE) -> ClampResult:
    """Fold the clamp pipeline over the proposal, accumulating the full audit trail."""
    edits = tuple(prop.edits)
    all_viols: list = []
    for clamp in pipeline:
        res = clamp(replace(prop, edits=edits), ctx)
        all_viols.extend(res.violations)
        if not res.ok:
            return ClampResult(False, (), tuple(all_viols), res.aborted_by)
        edits = res.clamped_edits
    return ClampResult(True, tuple(edits), tuple(all_viols), None)
