"""Mean-Value Engine Model — a cycle-averaged (not crank-resolved) idle fuel model.

The right fidelity for proving idle FUEL convergence: we model how much fuel the ECU actually
delivers given its believed injector/airflow calibration vs the engine's true parameters, and the
steady-state closed-loop trim that results. We do NOT model combustion, knock physics, or
transients — knock in the harness is a scripted state for testing the abort clamp, not physics.

Fuel path (all masses per intake event; only ratios matter, so units are nominal):
  A_est   = A_true * (maf_believed / maf_true)         # ECU's airflow estimate
  m_target= A_est / AFR_target                          # open-loop fuel the ECU wants
  pw      = m_target / (flow_believed*K) + latency_believed   # pulsewidth it computes
  m_deliv = (pw - latency_true) * flow_true * K          # fuel actually injected
  trim    = m_required / m_deliv - 1                     # closed loop makes up the difference
where m_required = A_true / AFR_target and K converts cc/min*ms -> mass. At the TRUE calibration
every believed==true and trim==0; any mismatch shows up as a non-zero steady-state trim — exactly
the bad-idle symptom.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.models import TableSet
from ..core.tables import FUEL_INJECTOR_FLOW, FUEL_INJECTOR_LATENCY, SENSOR_MAF_TRANSFER


@dataclass
class EngineParams:
    """Ground truth — what the engine actually is. The ECU's tables start out NOT matching these."""
    displacement_l: float = 2.0      # EJ20X
    afr_target: float = 14.7
    fuel_density: float = 0.74       # g/cc
    idle_air_g: float = 0.10         # true air mass per event at idle (nominal)
    flow_true: float = 500.0         # OEM 2005 FXT side-feed injectors (~500 cc/min) — matched to the ROM
    latency_true: float = 1.0        # true injector dead time, ms
    maf_scaling_true: float = 1.0    # the MAF scaling that would make A_est == A_true

    @property
    def k(self) -> float:
        """cc/min * ms -> grams of fuel."""
        return self.fuel_density / 60000.0


@dataclass(frozen=True)
class OperatingPoint:
    rpm: float = 850.0
    maf_gs: float = 2.5
    load_grev: float = 0.30


def _scalar(tables: TableSet, table_id: str) -> float:
    return float(np.asarray(tables.get(table_id).values).reshape(-1)[0])


def open_loop_fuel(tables: TableSet, params: EngineParams) -> tuple[float, float]:
    """Return (delivered, required) fuel mass per event for the believed tables."""
    flow_b = _scalar(tables, FUEL_INJECTOR_FLOW)
    lat_b = _scalar(tables, FUEL_INJECTOR_LATENCY)
    maf_b = _scalar(tables, SENSOR_MAF_TRANSFER)
    a_true = params.idle_air_g
    a_est = a_true * (maf_b / params.maf_scaling_true)
    m_target = a_est / params.afr_target
    pw = m_target / (flow_b * params.k) + lat_b           # ms
    delivered = max(0.0, pw - params.latency_true) * params.flow_true * params.k
    required = a_true / params.afr_target
    return delivered, required


def steady_trim(tables: TableSet, params: EngineParams) -> float:
    """Steady-state closed-loop fuel trim (fraction). +ve = ECU adding fuel (base map lean)."""
    delivered, required = open_loop_fuel(tables, params)
    if delivered <= 0.0:
        return 1.0
    return required / delivered - 1.0
