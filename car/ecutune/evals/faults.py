"""Fault taxonomy — each fault is a seeded perturbation of believed tables vs engine truth.

Baseline truth is THIS build (OEM 2005 FXT ~500 cc/min injectors, 1.0 ms dead time, unity MAF
transfer). Magnitude ranges are chosen to produce realistic trim signatures (roughly +6..+20%),
inside typical A/F-learning authority. `acceptable` lists faults genuinely indistinguishable from
the label at this fidelity (leak vs dead-time needs a voltage sweep — real-car territory).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.models import Table, TableSet
from ..core.tables import FUEL_INJECTOR_FLOW, FUEL_INJECTOR_LATENCY, SENSOR_MAF_TRANSFER
from ..simulation.mvem import EngineParams


@dataclass(frozen=True)
class FaultSpec:
    fault_id: str
    acceptable: tuple[str, ...]          # answers scored as correct (incl. itself)
    magnitude_range: tuple[float, float]  # sampled uniformly; semantics per-fault


FAULTS: tuple[FaultSpec, ...] = (
    FaultSpec("healthy", ("healthy",), (0.0, 0.0)),
    FaultSpec("maf_low", ("maf_low",), (0.86, 0.94)),                    # believed/true transfer
    FaultSpec("maf_high", ("maf_high",), (1.06, 1.15)),
    FaultSpec("injector_flow_lean", ("injector_flow_lean",), (1.06, 1.18)),   # believed/true flow
    FaultSpec("injector_flow_rich", ("injector_flow_rich",), (0.85, 0.94)),
    FaultSpec("injector_latency_lean", ("injector_latency_lean", "vacuum_leak"), (0.75, 0.90)),
    FaultSpec("vacuum_leak", ("vacuum_leak", "injector_latency_lean"), (0.08, 0.18)),  # leak/idle air
)

FAULT_IDS = tuple(f.fault_id for f in FAULTS)

# v2 (sim_eval_v2): the case includes a low-battery-voltage probe point that separates
# latency-belief errors from vacuum leaks (dead time is voltage-dependent; unmetered air is
# not). The degeneracy is BROKEN, so the acceptable sets tighten to exact-only.
FAULTS_V2: tuple[FaultSpec, ...] = tuple(
    FaultSpec(f.fault_id, (f.fault_id,), f.magnitude_range) for f in FAULTS
)

_TRUE_FLOW = 500.0     # OEM 2005 FXT side-feed (build-sheet)
_TRUE_LATENCY = 1.0
_TRUE_MAF = 1.0


def build_case_world(spec: FaultSpec, rng: np.random.Generator) -> tuple[TableSet, EngineParams, float]:
    """Return (believed tables, true engine params, magnitude_pct) for one sampled fault instance.

    The ECU's believed tables start CORRECT (matched OEM build) and the fault perturbs exactly one
    thing — either a belief (scaling faults) or the engine itself (leak).
    """
    lo, hi = spec.magnitude_range
    mag = float(rng.uniform(lo, hi))
    flow_b, lat_b, maf_b = _TRUE_FLOW, _TRUE_LATENCY, _TRUE_MAF
    leak = 0.0
    magnitude_pct = 0.0

    if spec.fault_id in ("maf_low", "maf_high"):
        maf_b = _TRUE_MAF * mag
        magnitude_pct = (mag - 1.0) * 100.0
    elif spec.fault_id in ("injector_flow_lean", "injector_flow_rich"):
        flow_b = _TRUE_FLOW * mag
        magnitude_pct = (mag - 1.0) * 100.0
    elif spec.fault_id == "injector_latency_lean":
        lat_b = _TRUE_LATENCY * mag                       # believes less dead time than real -> lean
        magnitude_pct = (mag - 1.0) * 100.0
    elif spec.fault_id == "vacuum_leak":
        leak = 0.10 * mag                                 # fraction of nominal idle air, unmetered
        magnitude_pct = mag * 100.0

    believed = TableSet({
        FUEL_INJECTOR_LATENCY: Table(FUEL_INJECTOR_LATENCY, "scalar", np.array(lat_b), units="ms"),
        FUEL_INJECTOR_FLOW: Table(FUEL_INJECTOR_FLOW, "scalar", np.array(flow_b), units="cc/min"),
        SENSOR_MAF_TRANSFER: Table(SENSOR_MAF_TRANSFER, "scalar", np.array(maf_b), units="scale"),
    })
    truth = EngineParams(flow_true=_TRUE_FLOW, latency_true=_TRUE_LATENCY,
                         maf_scaling_true=_TRUE_MAF, leak_air_g=leak)
    return believed, truth, magnitude_pct
