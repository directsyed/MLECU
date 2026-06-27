"""Canonical ECUFlash table IDs — verified in the ingested SubaruDefs.

Using the *exact* RomRaider/ECUFlash names as our internal table_id means the eventual
ROM-write bridge is a 1:1 name map (no translation layer to get wrong). Source of truth:
ml/data-pipeline/data/raw/SubaruDefs/ECUFlash/subaru standard/Forester 2.5/E2UE101J.xml
"""
from __future__ import annotations

# Global scalars / 1-D curves — the EJ20X-vs-EJ255 idle problem lives here.
INJECTOR_FLOW_SCALING = "Injector Flow Scaling"   # scalar; cc/min — whole-map fuel shift
INJECTOR_LATENCY = "Injector Latency_"            # 1-D curve vs battery voltage (dead time, ms)
MAF_SENSOR_SCALING = "MAF Sensor Scaling"         # 1-D curve, 48 pts — airflow estimate

# 2-D maps (X = load, Y = rpm).
PRIMARY_OPEN_LOOP_FUELING_A = "Primary Open Loop Fueling A_"   # commanded AFR target map
PRIMARY_OPEN_LOOP_FUELING_B = "Primary Open Loop Fueling B_"

# Closed-loop trim infrastructure (the ECU's own fuel learning).
AF_LEARNING_1_RANGES = "A/F Learning #1 Airflow Ranges"
AF_LEARNING_1_LIMITS = "A/F Learning #1 Limits"
