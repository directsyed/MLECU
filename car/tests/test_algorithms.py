"""Controller + idle global-scalar tests."""
from __future__ import annotations

import numpy as np

from ecutune.algorithms import AlgoState, propose_idle_correction
from ecutune.algorithms.controller import BoundedIntegralState, PIConfig, step
from ecutune.core.config import load_config
from ecutune.core.models import ClampContext, Table, TableSet
from ecutune.core.tables import FUEL_INJECTOR_FLOW, FUEL_INJECTOR_LATENCY, SENSOR_MAF_TRANSFER
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
        FUEL_INJECTOR_LATENCY: Table(FUEL_INJECTOR_LATENCY, "scalar", np.array(1.0), units="ms"),
        FUEL_INJECTOR_FLOW: Table(FUEL_INJECTOR_FLOW, "scalar", np.array(800.0), units="cc/min"),
        SENSOR_MAF_TRANSFER: Table(SENSOR_MAF_TRANSFER, "scalar", np.array(1.0), units="scale"),
    })


def test_controller_output_never_exceeds_clamp():
    st = BoundedIntegralState()
    cfg = PIConfig(kp=0.5, ki=0.1, step_clamp=0.03, damping=0.6)
    for err in (1.0, -1.0, 0.5, 0.11, -0.2):
        c, st = step(err, st, cfg)
        assert abs(c) <= 0.03 + 1e-12


def test_controller_converges_well_damped():
    """Drive a unit-sensitivity plant with the controller; trim must decay to ~0 and stay
    well-damped, a small bounded overshoot, not the large ringing of an unclamped integral."""
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
    assert set(by_id) == {FUEL_INJECTOR_LATENCY, FUEL_INJECTOR_FLOW, SENSOR_MAF_TRANSFER}
    # lean => add fuel: latency UP, MAF UP, flow-scaling DOWN (inverse lever)
    assert by_id[FUEL_INJECTOR_LATENCY] > 1.0
    assert by_id[SENSOR_MAF_TRANSFER] > 1.0
    assert by_id[FUEL_INJECTOR_FLOW] < 800.0


def test_idle_proposal_passes_clamps_clean():
    """The controller self-limits below +/-3%, so a well-formed idle proposal trips NO clamp
    violation; the clamp is the backstop, not the primary limiter."""
    grid = _grid_with_trim(11.0)
    tables = _tables()
    prop, _ = propose_idle_correction(grid, tables, AlgoState(), CFG.algo)
    res = apply_clamps(prop, ClampContext(tables, CFG.safety))
    assert res.ok
    assert res.violations == ()        # every per-scalar move is < 3%


def test_integrator_is_PER_KNOB_not_shared():
    """One shared BoundedIntegralState meant a correction to injector LATENCY inherited the
    integral accumulated while correcting injector FLOW, a multiplexed controller sharing one
    accumulator. State is now keyed by table id."""
    import numpy as np
    from ecutune.algorithms import AlgoState, propose_idle_correction
    from ecutune.algorithms import fueling
    from ecutune.core.config import load_config
    from ecutune.core.tables import FUEL_INJECTOR_FLOW, FUEL_INJECTOR_LATENCY
    from ecutune.logparse.binning import BinnedGrid, GridSpec

    cfg = load_config().algo
    spec = GridSpec(x_role="maf_gs", x_breaks=(2.5,), y_breaks=(850.0,), min_samples=1)
    grid = BinnedGrid(spec, np.array([[30.0]]), np.array([[6.0]]),
                      np.array([[14.7]]), np.array([[0.0]]), np.array([[True]]))
    tables = _tables() if "_tables" in globals() else None
    from ecutune.core.models import Table, TableSet
    from ecutune.core.tables import SENSOR_MAF_TRANSFER
    tables = TableSet({
        FUEL_INJECTOR_FLOW: Table(FUEL_INJECTOR_FLOW, "scalar", np.array(500.0)),
        FUEL_INJECTOR_LATENCY: Table(FUEL_INJECTOR_LATENCY, "scalar", np.array(1.0)),
        SENSOR_MAF_TRANSFER: Table(SENSOR_MAF_TRANSFER, "scalar", np.array(1.0)),
    })
    st = AlgoState()
    # three corrections routed at FLOW build integral history there...
    for _ in range(3):
        _, st = propose_idle_correction(grid, tables, st, cfg,
                                        split=fueling.ScalarSplit(0.0, 1.0, 0.0))
    assert FUEL_INJECTOR_FLOW in st.ctrl
    # ...and LATENCY must start from a clean integrator, not inherit flow's
    assert st.for_knob(FUEL_INJECTOR_LATENCY).integral == 0.0


def test_llm_provenance_is_recorded_on_the_proposal():
    """An edit made on a model's say-so must be distinguishable from one the algorithm made."""
    import numpy as np
    from ecutune.algorithms import AlgoState, propose_idle_correction, fueling
    from ecutune.core.config import load_config
    from ecutune.core.models import Table, TableSet
    from ecutune.core.tables import (FUEL_INJECTOR_FLOW, FUEL_INJECTOR_LATENCY,
                                     SENSOR_MAF_TRANSFER)
    from ecutune.logparse.binning import BinnedGrid, GridSpec
    spec = GridSpec(x_role="maf_gs", x_breaks=(2.5,), y_breaks=(850.0,), min_samples=1)
    grid = BinnedGrid(spec, np.array([[30.0]]), np.array([[6.0]]),
                      np.array([[14.7]]), np.array([[0.0]]), np.array([[True]]))
    tables = TableSet({
        FUEL_INJECTOR_FLOW: Table(FUEL_INJECTOR_FLOW, "scalar", np.array(500.0)),
        FUEL_INJECTOR_LATENCY: Table(FUEL_INJECTOR_LATENCY, "scalar", np.array(1.0)),
        SENSOR_MAF_TRANSFER: Table(SENSOR_MAF_TRANSFER, "scalar", np.array(1.0)),
    })
    prop, _ = propose_idle_correction(grid, tables, AlgoState(), load_config().algo,
                                      split=fueling.ScalarSplit(0.0, 1.0, 0.0),
                                      provenance="llm:qwen27b-dense",
                                      metadata={"diagnosis": "injector_flow_lean",
                                                "stability_run": 3})
    assert prop.provenance == "llm:qwen27b-dense"
    assert prop.metadata["diagnosis"] == "injector_flow_lean"
    assert prop.metadata["stability_run"] == 3
    assert prop.metadata["knob"] == FUEL_INJECTOR_FLOW
