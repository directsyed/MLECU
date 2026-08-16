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
from ..algorithms.identify import Observation
from ..core.config import Config, load_config
from ..core.models import ClampContext, TableSet
from ..logparse.binning import GridSpec, bin_log, weighted_mean_trim
from ..safety import apply_proposal
from .mismatch import ej20x_into_ej255
from .mvem import (FAST_IDLE_RPM, NOMINAL_MAF_IDLE, PROBE_POINTS, OperatingPoint)
from .synth_log import synth_idle_log

CONVERGENCE_TOL_PCT = 5.0   # +/-5% trim = "idle dialed in"


def idle_grid_spec(op: OperatingPoint) -> GridSpec:
    return GridSpec(x_role="maf_gs", x_breaks=(op.maf_gs,), y_breaks=(op.rpm,), min_samples=20)


def probe_grid_spec(op: OperatingPoint) -> GridSpec:
    """A grid covering BOTH airflow probe points. `bin_log` already supported multi-cell grids —
    x_breaks/y_breaks are tuples and idle_grid_spec simply passed single-element ones, so this
    needed no change to the binning machinery at all."""
    return GridSpec(x_role="maf_gs",
                    x_breaks=(op.maf_gs, op.maf_gs * PROBE_POINTS[1][0]),
                    y_breaks=(op.rpm, FAST_IDLE_RPM), min_samples=20)


def collect_observations(tables, params, op: OperatingPoint, rng,
                         n: int = 60) -> list[Observation]:
    """Run the three-point probe protocol and bin each point into an Observation.

    Voltage is not a grid axis, so each probe point is logged and binned separately and the
    results assembled here — which is also exactly how the real car will capture them (three
    separate steady-state pulls, see car/logging/CAPTURE-PROTOCOL.md).

    This is the data the deterministic layer has always been entitled to and never received:
    `propose_idle_correction` sees one binned idle cell, while the LLM prompt has always shown
    all three points. That asymmetry is why the layer could not disagree with a diagnosis.
    """
    obs: list[Observation] = []
    for air_scale, voltage in PROBE_POINTS:
        log = synth_idle_log(tables, params, op, rng, n=n,
                             air_scale=air_scale, voltage=voltage)
        spec = GridSpec(x_role="maf_gs",
                        x_breaks=(op.maf_gs * air_scale,),
                        y_breaks=(op.rpm if air_scale == 1.0 else FAST_IDLE_RPM,),
                        min_samples=20)
        grid = bin_log(log, spec)
        maf = float(np.nanmean(log.get("maf_gs")))
        volts = float(np.nanmean(log.get("battery_v")))
        obs.append(Observation(air_scale=air_scale, voltage=volts,
                               trim=weighted_mean_trim(grid) / 100.0,
                               maf_reading=maf,
                               nominal_maf=NOMINAL_MAF_IDLE * air_scale,
                               # inside the SIM the seeded baseline IS the truth by construction
                               # (synth_log builds maf_gs from it) — so it is validated *for
                               # this world*. A real-log loader must NOT copy this line; it
                               # takes `MafBaseline.validated` from the capture instead.
                               nominal_validated=True))
    return obs


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
                    cfg: Config | None = None,
                    seeded: tuple[TableSet, "EngineParams", OperatingPoint] | None = None,
                    ) -> ConvergenceResult:
    """`seeded` overrides the synthetic mismatch — e.g. rom_seed.fxt_rom_into_ej20x() grounds
    the believed tables + idle operating point in the real A2WC411D calibration."""
    cfg = cfg or load_config()
    max_iters = max_iters or cfg.algo.max_iters
    if seeded is not None:
        tables, params, op = seeded
    else:
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
        prop, state = propose_idle_correction(grid, tables, state, cfg.algo)
        ctx = ClampContext(tables, cfg.safety)   # idle: no knock, fuel-only
        tables, result = apply_proposal(tables, prop, ctx)
        violations += len(result.violations)

    from .mvem import _scalar
    from ..core.tables import FUEL_INJECTOR_FLOW, FUEL_INJECTOR_LATENCY, SENSOR_MAF_TRANSFER
    scalars = {tid: round(_scalar(tables, tid), 4)
               for tid in (FUEL_INJECTOR_LATENCY, FUEL_INJECTOR_FLOW, SENSOR_MAF_TRANSFER)}
    return ConvergenceResult(
        iterations=len(trims),
        converged=abs(trims[-1]) <= CONVERGENCE_TOL_PCT,
        trim_history=trims,
        clamp_violations=violations,
        final_tables=tables,
        seed=seed,
        scalars=scalars,
    )
