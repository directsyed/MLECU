"""Turn one MVEM steady state into a synthetic RomRaider-shaped LogTable.

Deliberately emits the SAME LogTable shape that logparse.parse_romraider_csv produces, so a real
datalog later drops into the identical bin -> propose -> clamp path (the log-replay goal). The
wideband sits at stoich because the ECU's closed loop holds it there, the signal the algorithm
acts on is the TRIM (the work the ECU is doing), not the AFR. Noise is seeded for determinism.
"""
from __future__ import annotations

import numpy as np

from ..core.tables import SENSOR_MAF_TRANSFER
from ..logparse.romraider_csv import LogTable
from . import ecu_loop
from .mvem import EngineParams, OperatingPoint, FAST_IDLE_RPM, steady_trim


def _scalar(tables, table_id: str) -> float:
    return float(np.asarray(tables.get(table_id).values).reshape(-1)[0])


def synth_idle_log(tables, params: EngineParams, op: OperatingPoint,
                   rng: np.random.Generator, n: int = 60,
                   air_scale: float = 1.0, voltage: float | None = None) -> LogTable:
    """One steady-state probe point as a RomRaider-shaped log.

    `air_scale` / `voltage` (added 2026-08-05) are what let the deterministic layer see the
    same three probe points the LLM prompt has always shown it. Defaults reproduce the previous
    idle-at-v_ref behaviour exactly.

    TWO THINGS THE OLD VERSION GOT WRONG for identification purposes:
      * `maf_gs` was the TRUE airflow. On a real car the logged MAF is the ECU's ESTIMATE, so a
        wrong MAF transfer shows up directly in the logged value; that is a free, trim-free
        read on MAF belief error, and the estimator uses it.
      * `battery_v` was never emitted at all, despite being a canonical channel role in
        logparse/schema.py. Without it the voltage probe cannot be reconstructed from a log.
    """
    v = params.v_ref if voltage is None else voltage
    trim_pct = steady_trim(tables, params, air_scale=air_scale, voltage=voltage) * 100.0
    learn, corr = ecu_loop.split_trim(trim_pct)
    maf_belief_ratio = _scalar(tables, SENSOR_MAF_TRANSFER) / params.maf_scaling_true
    rpm = op.rpm if air_scale == 1.0 else FAST_IDLE_RPM
    return LogTable(channels={
        "rpm": rpm + rng.normal(0.0, 3.0, n),
        "maf_gs": op.maf_gs * air_scale * maf_belief_ratio + rng.normal(0.0, 0.03, n),
        "load": np.full(n, op.load_grev * air_scale),
        "af_learning": learn + rng.normal(0.0, 0.1, n),
        "af_correction": corr + rng.normal(0.0, 0.2, n),
        "wideband_afr": params.afr_target + rng.normal(0.0, 0.1, n),   # held at stoich by closed loop
        "knock_retard": np.zeros(n),
        "tps": np.zeros(n),
        "battery_v": v + rng.normal(0.0, 0.05, n),
    }, raw_headers=(), sample_hz=10.0, source_path="<synthetic>")
