"""Compose the ordered clamps into a single fold. apply_clamps() is the ONLY way a Proposal
becomes a set of edits eligible to touch a Table.

Order rationale:
  1. knock_auto_abort, fail fast on the hardest hard-stop.
  1b. diagnosis_agreement, the layer's OWN fault estimate must agree with the proposal's
                             target table, else abort + escalate (the LLM points, it does not
                             command). Inert when no estimate is supplied.
  2. fuel_before_timing, ordering gates: reject out-of-sequence proposals before any work.
  3. steady_before_transient
  4. boost_gate, defer boost edits until the three boost preconditions hold.
  5. timing_row_ceiling, where a timing cell is allowed to END UP (absolute advance cap,
                             tightest of the rpm-keyed and load-keyed limits).
  5b. timing_rate_limit, HOW FAST it may get there, plus retard-only and a cumulative floor
                             against stock. Deliberately AFTER the ceiling: the ceiling floors
                             a cell to a value in one move (up to 18.12 deg on this ROM), so if
                             it ran last it would override Syed's ratified 6 deg/iteration and
                             the rate limit would be decorative. Ceiling decides WHERE, this
                             decides HOW FAST, so this one has the last word. (D31)
  6. ve_rate_limit, bound every fuel edit to +/-3% per iteration (VELOCITY).
  6b. belief_envelope, bound every fuel belief's DISTANCE from the stock ROM. The rate
                             limit alone lets 12 iterations compound to 43%.
  6c. sensor_calibration, bound SENSOR recalibrations by EVIDENCE + DISPLACEMENT + curve
                             monotonicity instead of velocity. Disjoint from 6/6b: those key
                             off targets_kind=='fuel', this off 'sensor', so neither throttles
                             the other. A MAF curve is a measurement to correct, not a target
                             to chase.
  7. afr_floor, LAST: the final hard word on boost AFR cells (may richen past the
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
    clamps.clamp_diagnosis_agreement,
    clamps.clamp_fuel_before_timing,
    clamps.clamp_steady_before_transient,
    clamps.clamp_boost_gate,
    clamps.clamp_timing_row_ceiling,
    clamps.clamp_timing_rate_limit,
    clamps.clamp_ve_rate_limit,
    clamps.clamp_belief_envelope,
    clamps.clamp_sensor_calibration,
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
