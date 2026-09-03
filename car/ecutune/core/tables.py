"""SEMANTIC table IDs, the universal vocabulary the whole deterministic layer speaks.

Every ECU exposes the same tuning surface (fuel scaling, injector dead time, airflow transfer,
AFR targets, timing, idle targets, the concepts behind the SAE J1979 channel vocabulary), so the
algorithms and safety clamps operate ONLY on these platform-neutral semantic IDs. What a given
platform *calls* each table lives in ecutune/platforms/ adapters:

    semantic ID              subaru_ecuflash (A2WC400x)        tunerstudio (speeduino.ini)
    fuel.injector_flow    -> "Injector Flow Scaling"           (reqFuel scalar analog)
    sensor.maf_transfer   -> "MAF Sensor Scaling"              (speed-density: absent)

This keeps Subaru as adapter #1 rather than the foundation, the universal-first constraint
(decisions.md 2026-07-03). Adapters also absorb per-ROM-def name drift (the 2005 FXT def says
"Injector Latency"; the Forester 2.5 def says "Injector Latency_", same table, same semantic ID).
"""
from __future__ import annotations

# --- fuel path (global scalars / curves: the idle Stage-2 levers) --------------------
FUEL_INJECTOR_FLOW = "fuel.injector_flow"        # injector flow the ECU believes (cc/min); INVERSE lever
FUEL_INJECTOR_LATENCY = "fuel.injector_latency"  # injector dead time vs battery voltage (ms); DIRECT
SENSOR_MAF_TRANSFER = "sensor.maf_transfer"      # MAF sensor transfer/scaling (airflow estimate); DIRECT

# --- fuel targets / closed-loop infrastructure -----------------------------------------
FUEL_TARGET_AFR_PRIMARY_A = "fuel.target_afr_primary_a"   # primary open-loop AFR target map (X=load, Y=rpm)
FUEL_TARGET_AFR_PRIMARY_B = "fuel.target_afr_primary_b"
FUEL_CL_LEARNING_RANGES = "fuel.cl_learning_ranges"       # A/F learning airflow ranges
FUEL_CL_LEARNING_LIMITS = "fuel.cl_learning_limits"       # A/F learning clamp limits

# --- ignition ---------------------------------------------------------------------------
IGNITION_BASE_TIMING = "ignition.base_timing"
IGNITION_TIMING_COMP_A = "ignition.timing_comp_a"         # per-cylinder/aux timing compensation
# The advance the ECU adds ON TOP of the base map, scaled by IAM. Read-only for the layer: the
# timing stage needs it to know how much advance a cell LOSES when IAM collapses, which is what
# turns "IAM went to zero" from a severity signal into a number of degrees per cell.
IGNITION_KNOCK_ADVANCE_MAX = "ignition.knock_advance_max"
# The ECU's own starting IAM. On this ROM it is 0.5, NOT 1.0 -- so an observed IAM of 0.5 is the
# healthy value, not a halved one, and the deficit at IAM 0 is 0.5 of the advance map.
IGNITION_ADVANCE_MULT_INITIAL = "ignition.advance_multiplier_initial"

# --- idle / boost ------------------------------------------------------------------------
IDLE_SPEED_TARGET_A = "idle.speed_target_a"
BOOST_WASTEGATE_DUTY = "boost.wastegate_duty"
