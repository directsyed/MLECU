"""Seed the KNOWN mismatch the harness must recover — build-specific to THIS Forester.

IMPORTANT: this car runs the ENTIRE OEM 2005 FXT (EJ255) intake manifold + injectors + wiring
harness on the OEM FXT ECU. So the injectors (~500 cc/min side-feed) are MATCHED to the stock ROM's
injector scaling and latency — those scalars are already correct. With matched injectors + MAF
metering, the idle FUEL error reduces cleanly to the MAF calibration: the modified intake tract
(STI top-mount, fully catless) makes the ROM's MAF curve read a few % low at idle, so the ECU
under-estimates air and carries a standing lean trim the closed loop is compensating for. The idle
algorithm bakes that residual back into MAF scaling. (Proof: with matched injectors the MVEM's
delivered fuel == the ECU's target, so trim == 1/maf_ratio − 1 — a pure MAF error.)

Out of scope for this mean-value FUEL model (they are NOT fuel-trim errors — they need real logs +
a richer model): the 2.0 L-on-2.5 L VE/load mismatch, exhaust-AVCS/TGV-delete overlap & idle
stability, and timing too advanced for the 9.5:1 CR on 93 oct. See car/build-sheet.md.
"""
from __future__ import annotations

import numpy as np

from ..core.models import Table, TableSet
from ..core.tables import INJECTOR_FLOW_SCALING, INJECTOR_LATENCY, MAF_SENSOR_SCALING
from .mvem import EngineParams


def ej20x_into_ej255() -> tuple[TableSet, EngineParams]:
    """Return (believed starting tables, true engine params). Injectors matched; MAF reads ~12% low."""
    believed = TableSet({
        INJECTOR_LATENCY: Table(INJECTOR_LATENCY, "scalar", np.array(1.0), units="ms"),          # matched
        INJECTOR_FLOW_SCALING: Table(INJECTOR_FLOW_SCALING, "scalar", np.array(500.0), units="cc/min"),  # OEM FXT, matched
        MAF_SENSOR_SCALING: Table(MAF_SENSOR_SCALING, "scalar", np.array(0.88), units="scale"),   # reads ~12% low on the modified intake
    })
    truth = EngineParams(
        displacement_l=2.0, idle_air_g=0.10,
        flow_true=500.0, latency_true=1.0, maf_scaling_true=1.0,
    )
    return believed, truth
