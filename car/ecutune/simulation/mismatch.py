"""Seed the KNOWN mismatch the harness must recover — build-specific to THIS Forester (2005 FXT).

The swap keeps the OEM FXT intake manifold + injectors + harness on the FXT ECU, so the injectors
(~500 cc/min side-feed) are NOMINALLY matched to the stock ROM — a useful prior, but NOT a licence to
exclude them. Real injectors vary unit-to-unit, latency shifts with battery voltage and fuel pressure,
and the intake mods move the MAF calibration; on a fresh swap everything is a little off at once. So we
seed error across ALL the fuel levers and let the loop correct all of them — we do not pre-decide which
is "the" problem. That is the whole point of reading the car: the data sets the priorities.

Caveat kept honest: at a single idle operating point the levers are DEGENERATE — a MAF error and an
injector error look identical in the trim — so the loop converges the *trim* to a valid combination,
not each scalar to its true value. Separating them (real prioritization) needs logs across operating
conditions. Timing, AVCS and idle-airflow are separate axes (their own stages), likewise data-
prioritized — see car/build-sheet.md.
"""
from __future__ import annotations

import numpy as np

from ..core.models import Table, TableSet
from ..core.tables import INJECTOR_FLOW_SCALING, INJECTOR_LATENCY, MAF_SENSOR_SCALING
from .mvem import EngineParams


def ej20x_into_ej255() -> tuple[TableSet, EngineParams]:
    """Return (believed starting tables, true engine params). Error seeded across ALL fuel levers."""
    believed = TableSet({
        INJECTOR_LATENCY: Table(INJECTOR_LATENCY, "scalar", np.array(0.96), units="ms"),           # ~4% off
        INJECTOR_FLOW_SCALING: Table(INJECTOR_FLOW_SCALING, "scalar", np.array(510.0), units="cc/min"),  # ~2% off
        MAF_SENSOR_SCALING: Table(MAF_SENSOR_SCALING, "scalar", np.array(0.93), units="scale"),     # ~7% low (intake mods)
    })
    truth = EngineParams(
        displacement_l=2.0, idle_air_g=0.10,
        flow_true=500.0, latency_true=1.0, maf_scaling_true=1.0,
    )
    return believed, truth
