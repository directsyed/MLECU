"""Subaru ECUFlash/RomRaider adapter — semantic IDs -> the 2005 FXT (A2WC400x) table names.

Primary names verified against the ingested SubaruDefs for the 2005 USDM Forester XT 4EAT
(A2WC400D/H family); VARIANTS carry the spellings seen in sibling defs (e.g. the Forester 2.5
E2UE101J def suffixes some names with underscores / map letters). The future ROM-value reader
resolves a ROM's def against BOTH so per-def drift never reaches the algorithms.
"""
from __future__ import annotations

from ..core import tables as T

PLATFORM = "subaru_ecuflash"

TO_PLATFORM: dict[str, str] = {
    T.FUEL_INJECTOR_FLOW: "Injector Flow Scaling",
    T.FUEL_INJECTOR_LATENCY: "Injector Latency",
    T.SENSOR_MAF_TRANSFER: "MAF Sensor Scaling",
    T.FUEL_TARGET_AFR_PRIMARY_A: "Primary Open Loop Fueling",
    T.FUEL_TARGET_AFR_PRIMARY_B: "Primary Open Loop Fueling (Failsafe)",
    T.FUEL_CL_LEARNING_RANGES: "A/F Learning #1 Airflow Ranges",
    T.FUEL_CL_LEARNING_LIMITS: "A/F Learning #1 Limits",
    T.IGNITION_BASE_TIMING: "Base Timing",
    T.IGNITION_TIMING_COMP_A: "Timing Compensation Per Cylinder A__",
    T.IDLE_SPEED_TARGET_A: "Idle Speed Target A",
    # no factory wastegate-duty table exposed at this level yet — boost stage is future work
}

# Alternate spellings across sibling ECUFlash defs (same semantic table).
VARIANTS: dict[str, tuple[str, ...]] = {
    T.FUEL_INJECTOR_LATENCY: ("Injector Latency_",),
    T.FUEL_TARGET_AFR_PRIMARY_A: ("Primary Open Loop Fueling A_",),
    T.FUEL_TARGET_AFR_PRIMARY_B: ("Primary Open Loop Fueling B_",),
    T.IGNITION_TIMING_COMP_A: ("Timing Compensation A", "Timing Compensation (IAT)"),
}
