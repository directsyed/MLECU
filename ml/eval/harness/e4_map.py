"""E4 diagnosis -> action map. THE SAFETY BOUNDARY, expressed as a lookup table.

This module is the entire interface between the language model and the ECU tables, and it is
deliberately the dullest file in the project. The model emits ONE TOKEN from a fixed enum. That
token indexes this table. The table yields a set of three weights — nothing else. Every number
that reaches a table is computed downstream by `propose_idle_correction` from the measured trim
and then clamped by `safety.apply_proposal`.

Read that again as a safety property: THERE IS NO PATH from model output to a table value. The
model cannot widen a correction, cannot pick a magnitude, cannot reach a table it was not
routed to, and cannot act at all on a diagnosis that maps to NO_EDIT. A compromised, confused
or hallucinating model can at worst select the wrong PATHWAY — and selecting the wrong pathway
is precisely what E4 measures and what `masking` scores.

Kept free of ecutune imports so it can be unit-tested, and read by a reviewer, on its own.
"""
from __future__ import annotations

# Believed-scalar table ids (mirrored from car/ecutune/core/tables.py; asserted equal by test).
FUEL_INJECTOR_FLOW = "fuel.injector_flow"
FUEL_INJECTOR_LATENCY = "fuel.injector_latency"
SENSOR_MAF_TRANSFER = "sensor.maf_transfer"

NO_EDIT = None

# diagnosis -> (w_latency, w_flow, w_maf), matching ScalarSplit's field order.
# One weight at 1.0: the diagnosis selects WHICH belief is wrong, and the whole bounded
# correction goes there. The neutral default (0.34/0.33/0.33) is what the algorithm uses when
# nobody knows which lever is at fault — it smears the correction across all three and
# converges the trim while leaving every belief slightly wrong. That is the masking behaviour
# E4 exists to detect, so E4 must not reproduce it.
DIAGNOSIS_ACTION: dict[str, tuple[float, float, float] | None] = {
    "maf_low":               (0.0, 0.0, 1.0),
    "maf_high":              (0.0, 0.0, 1.0),
    "injector_flow_lean":    (0.0, 1.0, 0.0),
    "injector_flow_rich":    (0.0, 1.0, 0.0),
    "injector_latency_lean": (1.0, 0.0, 0.0),
    # A vacuum leak is unmetered air entering the engine. It does not live in any table, so
    # there is no table edit that fixes it — the correct action is "go find the leak". Any edit
    # here would converge the trim by corrupting a belief that was CORRECT, which is the
    # textbook definition of masking a fault. The deterministic layer must refuse.
    "vacuum_leak":           NO_EDIT,
    "healthy":               NO_EDIT,
}

# Which believed scalar each diagnosis actually moves. Used by the scorer to tell "wrong label,
# right knob" (maf_low vs maf_high — the sign comes from the measured trim, not the label, so
# the loop still converges correctly) from "wrong knob" (genuine masking).
DIAGNOSIS_KNOB: dict[str, str | None] = {
    "maf_low":               SENSOR_MAF_TRANSFER,
    "maf_high":              SENSOR_MAF_TRANSFER,
    "injector_flow_lean":    FUEL_INJECTOR_FLOW,
    "injector_flow_rich":    FUEL_INJECTOR_FLOW,
    "injector_latency_lean": FUEL_INJECTOR_LATENCY,
    "vacuum_leak":           None,
    "healthy":               None,
}

# Ground truth for the believed scalars in the E4 world (mirrors evals/faults.py; test asserts).
TRUE_SCALARS = {
    FUEL_INJECTOR_FLOW: 500.0,
    FUEL_INJECTOR_LATENCY: 1.0,
    SENSOR_MAF_TRANSFER: 1.0,
}


def action_for(diagnosis: str) -> tuple[float, float, float] | None:
    """Weights for a diagnosis, or NO_EDIT. An UNKNOWN diagnosis is NO_EDIT, never a default
    split: an unrecognised model output must not fall through into "edit everything a bit"."""
    return DIAGNOSIS_ACTION.get(diagnosis, NO_EDIT)


def knob_for(diagnosis: str) -> str | None:
    return DIAGNOSIS_KNOB.get(diagnosis)
