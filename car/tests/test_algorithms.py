"""Controller + idle global-scalar tests."""
from __future__ import annotations

import numpy as np

from ecutune.algorithms import AlgoState, propose_idle_correction
from ecutune.algorithms.controller import BoundedIntegralState, PIConfig, step
from ecutune.core.config import load_config
from ecutune.core.models import ClampContext, Table, TableSet
from ecutune.core.tables import INJECTOR_FLOW_SCALING, INJECTOR_LATENCY, MAF_SENSOR_SCALING
from ecutune.logparse.binning import BinnedGrid, GridSpec
from ecutune.safety import apply_clamps

CFG = load_config()


def _grid_with_trim(trim_pct: float) -> BinnedGrid:
    spec = GridSpec(x_role="maf_gs", x_breaks=(2.0,), y_breaks=(850.0,), min_samples=1)
    return BinnedGrid(spec, count=np.array([[40.0]]), mean_trim=np.array([[trim_pct]]),
                      mean_afr=np.array([[14.7]]), mean_knock=np.array([[0.0]]),
                      confidence=np.array([[True]]))


def _tables() -> TableSet:
    return TableSet({
        INJECTOR_LATENCY: Table(INJECTOR_LATENCY, "scalar", np.array(1.0), units="ms"),
        INJECTOR_FLOW_SCALING: Table(INJECTOR_FLOW_SCALING, "scalar", np.array(800.0), units="cc/min"),
        MAF_SENSOR_SCALING: Table(MAF_SENSOR_SCALING, "scalar", np.array(1.0), units="scale"),
    })


def test_controller_output_never_exceeds_clamp():
    st = BoundedIntegralState()
    cfg = PIConfig(kp=0.5, ki=0.1, step_clamp=0.03, damping=0.6)
    for err in (1.0, -1.0, 0.5, 0.11, -0.2):
        c, st = step(err, st, cfg)
        assert abs(c) <= 0.03 + 1e-12


def test_controller_converges_well_damped():
    """Drive a unit-sensitivity plant with the controller; trim must decay to ~0 and stay
    well-damped — a small bounded overshoot, not the large ringing of an unclamped integral."""
    st = BoundedIntegralState()
    cfg = PIConfig(kp=CFG.algo.kp, ki=CFG.algo.ki, step_clamp=CFG.algo.step_clamp,
                   damping=CFG.algo.damping)
    trim = 0.11
    history = [trim]
    for _ in range(40):
        c, st = step(trim, st, cfg)
        trim -= c                      # plant: 1% feedforward removes 1% trim
        history.append(trim)
    assert abs(trim) < 0.005           # converged within 0.5%
    assert min(history) > -0.015       # overshoot < 1.5% of the 11% step => well damped


def test_idle_proposal_shape_and_signs():
    grid = _grid_with_trim(11.0)       # lean: ECU adding 11% fuel
    prop, state2 = propose_idle_correction(grid, _tables(), AlgoState(), CFG.algo)
    assert prop.targets_kind == "fuel"
    assert prop.provenance == "algorithm:idle_global_scalar"
    assert state2.iterations == 1
    by_id = {e.table_id: e.new_value for e in prop.edits}
    assert set(by_id) == {INJECTOR_LATENCY, INJECTOR_FLOW_SCALING, MAF_SENSOR_SCALING}
    # lean => add fuel: latency UP, MAF UP, flow-scaling DOWN (inverse lever)
    assert by_id[INJECTOR_LATENCY] > 1.0
    assert by_id[MAF_SENSOR_SCALING] > 1.0
    assert by_id[INJECTOR_FLOW_SCALING] < 800.0


def test_idle_proposal_passes_clamps_clean():
    """The controller self-limits below +/-3%, so a well-formed idle proposal trips NO clamp
    violation — the clamp is the backstop, not the primary limiter."""
    grid = _grid_with_trim(11.0)
    tables = _tables()
    prop, _ = propose_idle_correction(grid, tables, AlgoState(), CFG.algo)
    res = apply_clamps(prop, ClampContext(tables, CFG.safety))
    assert res.ok
    assert res.violations == ()        # every per-scalar move is < 3%
