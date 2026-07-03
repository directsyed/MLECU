"""MVEM + convergence harness — the keystone offline proof that the loop fixes the bad idle."""
from __future__ import annotations

import numpy as np

from ecutune.core.models import Table, TableSet
from ecutune.core.tables import FUEL_INJECTOR_FLOW, FUEL_INJECTOR_LATENCY, SENSOR_MAF_TRANSFER
from ecutune.simulation.harness import CONVERGENCE_TOL_PCT, run_convergence
from ecutune.simulation.mvem import EngineParams, steady_trim


def _tables(latency, flow, maf) -> TableSet:
    return TableSet({
        FUEL_INJECTOR_LATENCY: Table(FUEL_INJECTOR_LATENCY, "scalar", np.array(float(latency))),
        FUEL_INJECTOR_FLOW: Table(FUEL_INJECTOR_FLOW, "scalar", np.array(float(flow))),
        SENSOR_MAF_TRANSFER: Table(SENSOR_MAF_TRANSFER, "scalar", np.array(float(maf))),
    })


def test_mvem_zero_trim_at_true_calibration():
    p = EngineParams()
    assert abs(steady_trim(_tables(p.latency_true, p.flow_true, p.maf_scaling_true), p)) < 1e-9


def test_mvem_more_fuel_lowers_trim():
    p = EngineParams()
    lean = steady_trim(_tables(0.95, 850.0, 0.98), p)
    richer = steady_trim(_tables(1.05, 850.0, 0.98), p)   # more dead time => more fuel
    assert lean > 0 and richer < lean


def test_convergence_recovers_mismatch():
    """THE keystone: starting from the seeded EJ20X-vs-EJ255 mismatch, the loop drives trim
    within +/-5% with ZERO clamp violations, in a sane iteration count."""
    r = run_convergence(seed=0)
    assert r.converged
    assert abs(r.trim_history[-1]) <= CONVERGENCE_TOL_PCT
    assert r.clamp_violations == 0           # the controller respects the bound; clamp never fires
    assert r.trim_history[0] > 10.0          # started meaningfully lean
    assert r.iterations <= 15                # converges quickly


def test_convergence_is_deterministic():
    a, b = run_convergence(seed=0), run_convergence(seed=0)
    for k in a.final_tables.tables:
        assert np.array_equal(a.final_tables.tables[k].values, b.final_tables.tables[k].values)
    assert a.trim_history == b.trim_history


def test_no_clamp_violations_across_seeds():
    for seed in range(8):
        r = run_convergence(seed=seed)
        assert r.converged, f"seed {seed} did not converge"
        assert r.clamp_violations == 0, f"seed {seed} tripped a clamp"
