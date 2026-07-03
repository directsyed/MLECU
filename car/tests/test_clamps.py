"""Unit tests for each safety clamp — hand-built tables + proposals, exact expected output."""
from __future__ import annotations

import numpy as np

from ecutune.core.config import load_config
from ecutune.core.models import CellEdit, ClampContext, Proposal, Table, TableAxis, TableSet
from ecutune.safety import apply_clamps

SAFETY = load_config().safety


def _ts(*tables: Table) -> TableSet:
    return TableSet({t.table_id: t for t in tables})


def _ctx(ts: TableSet, **kw) -> ClampContext:
    return ClampContext(ts, SAFETY, **kw)


def _fuel_scalar(val: float, tid: str = "fuel.injector_flow") -> Table:
    return Table(tid, "scalar", np.array(float(val)), units="cc/min")


def _afr_map(val: float, load: float = 2.0, rpm: float = 3000.0) -> Table:
    return Table("fuel.target_afr_primary_a", "map_2d", np.array([[float(val)]]), units="AFR",
                 x_axis=TableAxis("load", (load,), "g/rev"), y_axis=TableAxis("rpm", (rpm,), "rpm"))


def _timing_map(val: float, rpm: float = 4500.0, load: float = 2.0) -> Table:
    return Table("ignition.timing_comp_a", "map_2d", np.array([[float(val)]]), units="deg",
                 x_axis=TableAxis("load", (load,), "g/rev"), y_axis=TableAxis("rpm", (rpm,), "rpm"))


def _fuel_prop(edits) -> Proposal:
    return Proposal("p", "idle_stage2", tuple(edits), "fuel", "algorithm:test")


def _timing_prop(edits) -> Proposal:
    return Proposal("p", "stage3", tuple(edits), "timing", "algorithm:test")


def _boost_prop(edits) -> Proposal:
    return Proposal("p", "stage3", tuple(edits), "boost", "algorithm:test")


def test_ve_rate_limit_caps_at_3pct():
    ts = _ts(_fuel_scalar(750.0))
    res = apply_clamps(_fuel_prop([CellEdit("fuel.injector_flow", 0, 0, 900.0)]), _ctx(ts))  # +20%
    assert res.ok
    assert res.clamped_edits[0].new_value == 750.0 * 1.03  # 772.5
    assert res.violations[0].clamp == "ve_rate_limit"
    assert res.violations[0].action == "rate_limited"


def test_ve_rate_limit_passes_small_change():
    ts = _ts(_fuel_scalar(750.0))
    res = apply_clamps(_fuel_prop([CellEdit("fuel.injector_flow", 0, 0, 760.0)]), _ctx(ts))  # +1.3%
    assert res.clamped_edits[0].new_value == 760.0
    assert res.violations == ()


def test_ve_rate_limit_negative_direction():
    ts = _ts(_fuel_scalar(1000.0))
    res = apply_clamps(_fuel_prop([CellEdit("fuel.injector_flow", 0, 0, 500.0)]), _ctx(ts))  # -50%
    assert res.clamped_edits[0].new_value == 970.0  # 1000*0.97, sign preserved


def test_knock_aborts_everything():
    ts = _ts(_fuel_scalar(750.0))
    res = apply_clamps(_fuel_prop([CellEdit("fuel.injector_flow", 0, 0, 760.0)]),
                       _ctx(ts, knock_active=True))
    assert res.ok is False
    assert res.clamped_edits == ()
    assert res.aborted_by == "knock_auto_abort"


def test_afr_floor_floors_lean_at_boost():
    ts = _ts(_afr_map(12.0, load=2.0))  # boost cell (load 2.0 >= 1.5 threshold)
    res = apply_clamps(_fuel_prop([CellEdit("fuel.target_afr_primary_a", 0, 0, 13.5)]), _ctx(ts))
    assert res.clamped_edits[0].new_value == SAFETY.afr_floor  # 11.5 — hard floor wins
    assert any(v.clamp == "afr_floor" for v in res.violations)


def test_afr_floor_ignores_below_boost_threshold():
    ts = _ts(_afr_map(14.7, load=0.5))  # cruise/idle, below boost threshold
    res = apply_clamps(_fuel_prop([CellEdit("fuel.target_afr_primary_a", 0, 0, 15.0)]), _ctx(ts))
    assert res.clamped_edits[0].new_value == 15.0  # +2% < 3%, and not at boost => untouched


def test_timing_ceiling_floors():
    ts = _ts(_timing_map(10.0, rpm=4500))  # ceiling at 4500 rpm = 14.0 deg
    res = apply_clamps(_timing_prop([CellEdit("ignition.timing_comp_a", 0, 0, 20.0)]),
                       _ctx(ts, fuel_trims_converged=True))  # pass the fuel-before-timing gate
    assert res.clamped_edits[0].new_value == 14.0
    assert any(v.clamp == "timing_row_ceiling" for v in res.violations)


def test_fuel_before_timing_defers():
    ts = _ts(_timing_map(10.0))
    res = apply_clamps(_timing_prop([CellEdit("ignition.timing_comp_a", 0, 0, 12.0)]),
                       _ctx(ts, fuel_trims_converged=False))
    assert res.ok is False
    assert res.clamped_edits == ()
    assert res.violations[0].action == "deferred"


def test_steady_before_transient_defers_then_passes():
    ts = _ts(_fuel_scalar(750.0))
    prop = Proposal("p", "accel", (CellEdit("fuel.injector_flow", 0, 0, 755.0),),
                    "fuel", "algorithm:test", {"transient": True})
    assert apply_clamps(prop, _ctx(ts, steady_state_ok=False)).ok is False
    assert apply_clamps(prop, _ctx(ts, steady_state_ok=True)).ok is True


def test_boost_gate_defers_until_all_preconditions():
    ts = _ts(_fuel_scalar(15.0, tid="boost.wastegate_duty"))
    prop = _boost_prop([CellEdit("boost.wastegate_duty", 0, 0, 16.0)])
    assert apply_clamps(prop, _ctx(ts, max_trim_abs=0.10, wideband_tracking=False)).ok is False
    ok = apply_clamps(prop, _ctx(ts, max_trim_abs=0.02, wideband_tracking=True,
                                 boost_control_verified=True))
    assert ok.ok is True
    assert ok.clamped_edits[0].new_value == 16.0  # boost edits are not VE-rate-limited
