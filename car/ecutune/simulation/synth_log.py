"""Turn one MVEM steady state into a synthetic RomRaider-shaped LogTable.

Deliberately emits the SAME LogTable shape that logparse.parse_romraider_csv produces, so a real
datalog later drops into the identical bin -> propose -> clamp path (the log-replay goal). The
wideband sits at stoich because the ECU's closed loop holds it there — the signal the algorithm
acts on is the TRIM (the work the ECU is doing), not the AFR. Noise is seeded for determinism.
"""
from __future__ import annotations

import numpy as np

from ..logparse.romraider_csv import LogTable
from . import ecu_loop
from .mvem import EngineParams, OperatingPoint, steady_trim


def synth_idle_log(tables, params: EngineParams, op: OperatingPoint,
                   rng: np.random.Generator, n: int = 60) -> LogTable:
    trim_pct = steady_trim(tables, params) * 100.0
    learn, corr = ecu_loop.split_trim(trim_pct)
    return LogTable(channels={
        "rpm": op.rpm + rng.normal(0.0, 3.0, n),
        "maf_gs": op.maf_gs + rng.normal(0.0, 0.03, n),
        "load": np.full(n, op.load_grev),
        "af_learning": learn + rng.normal(0.0, 0.1, n),
        "af_correction": corr + rng.normal(0.0, 0.2, n),
        "wideband_afr": params.afr_target + rng.normal(0.0, 0.1, n),   # held at stoich by closed loop
        "knock_retard": np.zeros(n),
        "tps": np.zeros(n),
    }, raw_headers=(), sample_hz=10.0, source_path="<synthetic>")
