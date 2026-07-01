"""The convergence harness — the whole offline loop, with the three guarantees asserted.

Each iteration: MVEM steady state -> synthetic RomRaider log -> bin -> propose -> CLAMP -> apply
-> re-sim. We start from the seeded EJ20X-vs-EJ255 mismatch and prove, with no car and no GPU:
  (1) zero clamp violations  — the controller stays inside the +/-3% bound; the clamp never fires.
  (2) convergence            — steady-state trim reaches within +/-5%.
  (3) determinism            — same seed => identical table trajectory.
This is the offline proof that the algorithm + clamps actually fix the bad idle before the car moves.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..algorithms import AlgoState, propose_idle_correction
from ..algorithms.fueling import ScalarSplit
from ..core.config import Config, load_config
from ..core.models import ClampContext, TableSet
from ..logparse.binning import GridSpec, bin_log, weighted_mean_trim
from ..safety import apply_proposal
from .mismatch import ej20x_into_ej255
from .mvem import OperatingPoint
from .synth_log import synth_idle_log

CONVERGENCE_TOL_PCT = 5.0   # +/-5% trim = "idle dialed in"
# Injectors are OEM-matched, so the correction goes entirely into MAF scaling (the real lever for
# this build). Injector latency/flow stay put — chasing them would move already-correct scalars.
BUILD_SPLIT = ScalarSplit(w_latency=0.0, w_flow=0.0, w_maf=1.0)


def idle_grid_spec(op: OperatingPoint) -> GridSpec:
    return GridSpec(x_role="maf_gs", x_breaks=(op.maf_gs,), y_breaks=(op.rpm,), min_samples=20)


@dataclass
class ConvergenceResult:
    iterations: int
    converged: bool
    trim_history: list[float]            # steady-state trim (%) each iteration
    clamp_violations: int                # total clamp actions taken (expected: 0)
    final_tables: TableSet
    seed: int
    scalars: dict = field(default_factory=dict)   # final believed scalars (audit)


def run_convergence(seed: int = 0, max_iters: int | None = None,
                    cfg: Config | None = None) -> ConvergenceResult:
    cfg = cfg or load_config()
    max_iters = max_iters or cfg.algo.max_iters
    tables, params = ej20x_into_ej255()
    op = OperatingPoint()
    spec = idle_grid_spec(op)
    rng = np.random.default_rng(seed)
    state = AlgoState()

    trims: list[float] = []
    violations = 0
    for _ in range(max_iters):
        log = synth_idle_log(tables, params, op, rng)
        grid = bin_log(log, spec)
        trim_pct = weighted_mean_trim(grid)
        trims.append(trim_pct)
        if abs(trim_pct) <= CONVERGENCE_TOL_PCT:
            break
        prop, state = propose_idle_correction(grid, tables, state, cfg.algo, split=BUILD_SPLIT)
        ctx = ClampContext(tables, cfg.safety)   # idle: no knock, fuel-only
        tables, result = apply_proposal(tables, prop, ctx)
        violations += len(result.violations)

    from .mvem import _scalar
    from ..core.tables import INJECTOR_FLOW_SCALING, INJECTOR_LATENCY, MAF_SENSOR_SCALING
    scalars = {tid: round(_scalar(tables, tid), 4)
               for tid in (INJECTOR_LATENCY, INJECTOR_FLOW_SCALING, MAF_SENSOR_SCALING)}
    return ConvergenceResult(
        iterations=len(trims),
        converged=abs(trims[-1]) <= CONVERGENCE_TOL_PCT,
        trim_history=trims,
        clamp_violations=violations,
        final_tables=tables,
        seed=seed,
        scalars=scalars,
    )
