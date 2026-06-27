"""The idle global-scalar corrector — Stage 2 for the bad idle.

The EJ20X-into-EJ255-ECU mismatch is GLOBAL (injectors + airflow estimate differ), so we fix
global scalars, not map cells: idle only ever visits ~one fuel cell, but the wrong scalar poisons
the whole map. Each iteration we read the steady-state trim error, run it through the bounded
controller, and split the resulting feedforward correction across the three scalars (latency,
flow, MAF) in priority order — emitting ONE Proposal. We never touch a Table here: the caller
routes the Proposal through safety.apply_proposal.

We correct only feedforward tables; the ECU's own closed-loop fuel PI tracks AFR live. We are
removing the steady-state error it keeps having to trim out, not fighting its loop.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..core.config import AlgoCfg
from ..core.models import CellEdit, Proposal, TableSet
from ..core.tables import INJECTOR_FLOW_SCALING, INJECTOR_LATENCY, MAF_SENSOR_SCALING
from ..logparse.binning import BinnedGrid, weighted_mean_trim
from . import fueling
from .controller import BoundedIntegralState, PIConfig, step


@dataclass
class AlgoState:
    ctrl: BoundedIntegralState = field(default_factory=BoundedIntegralState)
    iterations: int = 0


def _scalar(tables: TableSet, table_id: str) -> float:
    return float(np.asarray(tables.get(table_id).values).reshape(-1)[0])


def propose_idle_correction(grid: BinnedGrid, tables: TableSet, state: AlgoState,
                            cfg: AlgoCfg, split: fueling.ScalarSplit | None = None
                            ) -> tuple[Proposal, AlgoState]:
    """Produce one bounded idle-fueling Proposal from the binned log. Pure: returns a new state."""
    split = split or fueling.ScalarSplit()
    error = fueling.trim_to_fuel_fraction(weighted_mean_trim(grid))   # fractional fuel error
    pi = PIConfig(cfg.kp, cfg.ki, cfg.step_clamp, cfg.damping)
    correction, ctrl2 = step(error, state.ctrl, pi)

    why = f"idle trim {error * 100:+.1f}% -> feedforward {correction * 100:+.2f}%"
    edits = (
        # priority order: latency, then flow, then MAF (degenerate at one idle point; the loop
        # separates them over iterations, attributing conservatively).
        CellEdit(INJECTOR_LATENCY, 0, 0,
                 fueling.corrected_latency(_scalar(tables, INJECTOR_LATENCY),
                                           split.w_latency * correction), why),
        CellEdit(INJECTOR_FLOW_SCALING, 0, 0,
                 fueling.corrected_flow_scaling(_scalar(tables, INJECTOR_FLOW_SCALING),
                                                split.w_flow * correction), why),
        CellEdit(MAF_SENSOR_SCALING, 0, 0,
                 fueling.corrected_maf(_scalar(tables, MAF_SENSOR_SCALING),
                                       split.w_maf * correction), why),
    )
    prop = Proposal(f"idle-{state.iterations}", "idle_stage2", edits, "fuel",
                    "algorithm:idle_global_scalar", {"trim_error": error, "correction": correction})
    return prop, AlgoState(ctrl2, state.iterations + 1)
