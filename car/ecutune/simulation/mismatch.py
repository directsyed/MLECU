"""Seed the KNOWN EJ20X-into-EJ255-ECU mismatch — the ground-truth error the convergence harness
must recover.

The base ROM is calibrated for the EJ255 (2.5L) the factory ECU expects; the engine is actually a
JDM EJ20X (2.0L) with different injectors and intake. So the believed tables differ from the true
engine parameters in three places, each making idle LEAN (the real symptom):
  * injector flow: ROM believes bigger injectors than fitted -> commands too-short pulse -> lean.
  * injector latency: ROM uses less dead time than real -> effective pulse too short -> lean.
  * MAF scaling: ROM under-estimates the (smaller-displacement) airflow -> commands too little fuel.

Numbers are illustrative and flagged for Syed to set from the real swap; the harness proves the
LOOP recovers whatever mismatch is seeded, not these specific values.
"""
from __future__ import annotations

import numpy as np

from ..core.models import Table, TableSet
from ..core.tables import INJECTOR_FLOW_SCALING, INJECTOR_LATENCY, MAF_SENSOR_SCALING
from .mvem import EngineParams


def ej20x_into_ej255() -> tuple[TableSet, EngineParams]:
    """Return (believed starting tables, true engine params). Their gap is the seeded error."""
    believed = TableSet({
        INJECTOR_LATENCY: Table(INJECTOR_LATENCY, "scalar", np.array(0.95), units="ms"),
        INJECTOR_FLOW_SCALING: Table(INJECTOR_FLOW_SCALING, "scalar", np.array(850.0), units="cc/min"),
        MAF_SENSOR_SCALING: Table(MAF_SENSOR_SCALING, "scalar", np.array(0.98), units="scale"),
    })
    truth = EngineParams(
        displacement_l=2.0, idle_air_g=0.10,
        flow_true=820.0, latency_true=1.0, maf_scaling_true=1.0,
    )
    return believed, truth
