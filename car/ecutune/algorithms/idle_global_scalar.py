"""The idle global-scalar corrector. Stage 2 for the bad idle.

The EJ20X-into-EJ255-ECU mismatch is GLOBAL (injectors + airflow estimate differ), so we fix
global scalars, not map cells: idle only ever visits ~one fuel cell, but the wrong scalar poisons
the whole map. Each iteration we read the steady-state trim error, run it through the bounded
controller, and split the resulting feedforward correction across the three scalars (latency,
flow, MAF) in priority order, emitting ONE Proposal. We never touch a Table here: the caller
routes the Proposal through safety.apply_proposal.

We correct only feedforward tables; the ECU's own closed-loop fuel PI tracks AFR live. We are
removing the steady-state error it keeps having to trim out, not fighting its loop.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..core.config import AlgoCfg
from ..core.models import CellEdit, Proposal, TableSet
from ..core.tables import FUEL_INJECTOR_FLOW, FUEL_INJECTOR_LATENCY, SENSOR_MAF_TRANSFER
from ..logparse.binning import BinnedGrid, weighted_mean_trim
from . import fueling
from .controller import BoundedIntegralState, PIConfig, step


@dataclass
class AlgoState:
    """PER-KNOB integrator state (2026-08-05).

    This was ONE BoundedIntegralState shared across all three tables. The integral term exists
    to kill stubborn residual error, but with a single accumulator a correction applied to
    injector LATENCY inherited the urgency accumulated while correcting injector FLOW, a
    multiplexed controller sharing one integrator, which is simply a control bug.

    Honest scope: anti-windup FREEZES the integral whenever the output saturates at the clamp,
    and with kp=0.5 ki=0.05 damping=0.7 clamp=0.029 it only accumulates in the 5%-8.3% trim
    window, i.e. the last iteration or two before convergence. Small blast radius, but that
    endgame is exactly where residual belief error is decided.
    """
    ctrl: dict = field(default_factory=dict)     # table_id -> BoundedIntegralState
    iterations: int = 0

    def for_knob(self, table_id: str) -> BoundedIntegralState:
        return self.ctrl.get(table_id, BoundedIntegralState())


def _scalar(tables: TableSet, table_id: str) -> float:
    return float(np.asarray(tables.get(table_id).values).reshape(-1)[0])


def _dominant_knob(split: fueling.ScalarSplit) -> str:
    """Which table this split actually moves, the integrator key."""
    return max(((FUEL_INJECTOR_LATENCY, split.w_latency),
                (FUEL_INJECTOR_FLOW, split.w_flow),
                (SENSOR_MAF_TRANSFER, split.w_maf)), key=lambda kv: kv[1])[0]


def propose_idle_correction(grid: BinnedGrid, tables: TableSet, state: AlgoState,
                            cfg: AlgoCfg, split: fueling.ScalarSplit | None = None,
                            provenance: str = "algorithm:idle_global_scalar",
                            metadata: dict | None = None
                            ) -> tuple[Proposal, AlgoState]:
    """Produce one bounded idle-fueling Proposal from the binned log. Pure: returns a new state.

    `provenance` / `metadata` (2026-08-05): when an LLM diagnosis selected the split, the audit
    trail must say so. Proposal's own docstring has always specified "llm:vN", but this function
    hardcoded the algorithm string, so an edit made on a model's say-so was indistinguishable
    from one the neutral default made, in a safety-critical write path where the clamps'
    docstring calls auditability "itself a safety property".
    """
    split = split or fueling.ScalarSplit()
    error = fueling.trim_to_fuel_fraction(weighted_mean_trim(grid))   # fractional fuel error
    pi = PIConfig(cfg.kp, cfg.ki, cfg.step_clamp, cfg.damping)
    knob = _dominant_knob(split)
    correction, ctrl_knob = step(error, state.for_knob(knob), pi)

    why = f"idle trim {error * 100:+.1f}% -> feedforward {correction * 100:+.2f}%"
    edits = (
        # priority order: latency, then flow, then MAF (degenerate at one idle point; the loop
        # separates them over iterations, attributing conservatively).
        CellEdit(FUEL_INJECTOR_LATENCY, 0, 0,
                 fueling.corrected_latency(_scalar(tables, FUEL_INJECTOR_LATENCY),
                                           split.w_latency * correction), why),
        CellEdit(FUEL_INJECTOR_FLOW, 0, 0,
                 fueling.corrected_flow_scaling(_scalar(tables, FUEL_INJECTOR_FLOW),
                                                split.w_flow * correction), why),
        CellEdit(SENSOR_MAF_TRANSFER, 0, 0,
                 fueling.corrected_maf(_scalar(tables, SENSOR_MAF_TRANSFER),
                                       split.w_maf * correction), why),
    )
    meta = {"trim_error": error, "correction": correction, "knob": knob,
            "split": (split.w_latency, split.w_flow, split.w_maf)}
    meta.update(metadata or {})
    prop = Proposal(f"idle-{state.iterations}", "idle_stage2", edits, "fuel", provenance, meta)
    return prop, AlgoState({**state.ctrl, knob: ctrl_knob}, state.iterations + 1)
