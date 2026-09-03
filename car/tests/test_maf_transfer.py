"""The MAF transfer stage + its clamp, the first CURVE tuner in the layer.

These pin the two rules the stage exists to honour (never extrapolate, only confident bins) and
the three bounds the clamp exists to enforce (evidence, displacement, monotonicity).
"""
from __future__ import annotations

import numpy as np
import pytest

from ecutune.algorithms import MafState, grid_spec_for, propose_maf_correction
from ecutune.core.config import load_config
from ecutune.core.models import CellEdit, ClampContext, Proposal, Table, TableAxis, TableSet
from ecutune.core.tables import SENSOR_MAF_TRANSFER
from ecutune.logparse.binning import bin_log
from ecutune.logparse.romraider_csv import LogTable
from ecutune.safety import apply_clamps, apply_proposal

CFG = load_config()
STOCK = np.array([1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0])


def _tables(values=STOCK):
    t = Table(SENSOR_MAF_TRANSFER, "curve_1d", np.array(values, dtype=float), units="g/s",
              x_axis=TableAxis("MAF sensor", tuple(0.5 + 0.5 * i for i in range(len(values))), "V"))
    return TableSet({SENSOR_MAF_TRANSFER: t})


def _log(maf_vals, trim_pct, n_each=40):
    """A synthetic steady log: n_each samples at each named airflow, all with the same trim."""
    maf, trim = [], []
    for m, t in zip(maf_vals, trim_pct):
        maf += [m] * n_each
        trim += [t] * n_each
    n = len(maf)
    return LogTable({"maf_gs": np.array(maf, float), "rpm": np.full(n, 2000.0),
                     "tps": np.full(n, 15.0), "af_correction": np.array(trim, float),
                     "af_learning": np.zeros(n)})


def _grid(tables, maf_vals, trim_pct, n_each=40):
    tbl = tables.get(SENSOR_MAF_TRANSFER)
    return bin_log(_log(maf_vals, trim_pct, n_each), grid_spec_for(tbl))


def _ctx(tables, counts=None):
    return ClampContext(tables, CFG.safety, sensor_sample_counts=counts)


# ------------------------------------------------------------------ the stage

def test_correction_is_direct_and_proportional_to_trim():
    """+20% trim at a breakpoint => that breakpoint's airflow estimate moves UP ~20%*damping."""
    tables = _tables()
    grid = _grid(tables, [4.0], [20.0])
    prop, st = propose_maf_correction(grid, tables, MafState(), CFG.algo)
    assert prop.targets_kind == "sensor"          # routes to the sensor clamp, not the fuel ones
    assert st.iterations == 1
    edit = next(e for e in prop.edits if e.col == 2)   # STOCK[2] == 4.0
    assert edit.new_value == pytest.approx(4.0 * (1 + 0.20 * CFG.algo.damping))


def test_never_extrapolates_past_the_measured_span():
    """Breakpoints outside the measured airflow range keep their stock value, untouched.

    This is the rule that keeps a vacuum-only dataset from inventing a boost-region correction -
    the measured curve is non-monotonic at the top, so extrapolating would be actively wrong.
    """
    tables = _tables()
    grid = _grid(tables, [4.0, 8.0], [20.0, 25.0])
    prop, _ = propose_maf_correction(grid, tables, MafState(), CFG.algo)
    touched = {e.col for e in prop.edits}
    assert touched == {2, 3}                        # only the two measured breakpoints
    assert 0 not in touched and 7 not in touched    # nothing below or above the span


def test_gap_between_measured_points_is_interpolated_not_skipped():
    """A breakpoint BETWEEN two measured anchors is corrected, the physical error is smooth in
    airflow, so an interior gap is genuinely known even without its own samples."""
    tables = _tables()
    grid = _grid(tables, [2.0, 16.0], [10.0, 30.0])
    prop, _ = propose_maf_correction(grid, tables, MafState(), CFG.algo)
    cols = sorted(e.col for e in prop.edits)
    assert cols == [1, 2, 3, 4]                     # interior 4.0 and 8.0 filled in
    mid = next(e for e in prop.edits if e.col == 2)
    assert 4.0 * (1 + 0.10 * CFG.algo.damping) < mid.new_value < 4.0 * (1 + 0.30 * CFG.algo.damping)


def test_low_sample_bins_are_not_confident_and_do_not_move():
    tables = _tables()
    grid = _grid(tables, [4.0], [20.0], n_each=5)    # below GridSpec.min_samples
    prop, _ = propose_maf_correction(grid, tables, MafState(), CFG.algo)
    assert prop.edits == ()


def test_stage_never_mutates_its_inputs():
    tables = _tables()
    before = tables.get(SENSOR_MAF_TRANSFER).values.copy()
    grid = _grid(tables, [4.0, 8.0], [20.0, 25.0])
    propose_maf_correction(grid, tables, MafState(), CFG.algo)
    assert np.array_equal(tables.get(SENSOR_MAF_TRANSFER).values, before)


def test_grid_spec_must_come_from_the_same_table():
    tables = _tables()
    grid = _grid(_tables(STOCK[:4]), [2.0], [10.0])   # 4 breakpoints vs the table's 8
    with pytest.raises(ValueError, match="grid_spec_for"):
        propose_maf_correction(grid, tables, MafState(), CFG.algo)


# ------------------------------------------------------------------ the clamp

def _prop(edits):
    return Proposal("p", "maf_transfer", tuple(edits), "sensor", "algorithm:test")


def test_clamp_caps_displacement_at_max_sensor_recal():
    tables = _tables()
    over = STOCK[2] * 2.0                            # +100%, way past the 40% cap
    res = apply_clamps(_prop([CellEdit(SENSOR_MAF_TRANSFER, 0, 2, over)]), _ctx(tables))
    assert res.ok
    assert res.clamped_edits[0].new_value == pytest.approx(STOCK[2] * (1 + CFG.safety.max_sensor_recal))
    assert [v.action for v in res.violations] == ["recal_limited"]


def test_clamp_allows_a_correction_the_fuel_rate_limit_would_have_blocked():
    """The whole point of the new category: +30% is legal for a sensor, illegal for a fuel cell."""
    tables = _tables()
    want = STOCK[2] * 1.30
    res = apply_clamps(_prop([CellEdit(SENSOR_MAF_TRANSFER, 0, 2, want)]), _ctx(tables))
    assert res.clamped_edits[0].new_value == pytest.approx(want)
    assert res.violations == ()


def test_fuel_proposals_are_untouched_by_the_sensor_clamp():
    """Disjoint routing: a fuel proposal still gets the 3% rate limit and nothing else changes."""
    tables = _tables()
    fuel = Proposal("f", "idle_stage2", (CellEdit(SENSOR_MAF_TRANSFER, 0, 2, STOCK[2] * 1.30),),
                    "fuel", "algorithm:test")
    res = apply_clamps(fuel, _ctx(tables))
    assert res.clamped_edits[0].new_value == pytest.approx(STOCK[2] * (1 + CFG.safety.max_ve_step))
    assert "ve_rate_limit" in {v.clamp for v in res.violations}


def test_clamp_refuses_a_breakpoint_with_no_evidence():
    tables = _tables()
    counts = {SENSOR_MAF_TRANSFER: tuple([0] * len(STOCK))}
    res = apply_clamps(_prop([CellEdit(SENSOR_MAF_TRANSFER, 0, 2, STOCK[2] * 1.2)]),
                       _ctx(tables, counts))
    assert res.clamped_edits[0].new_value == pytest.approx(STOCK[2])     # held at stock
    assert [v.action for v in res.violations] == ["insufficient_evidence"]


def test_evidence_check_is_inert_without_counts():
    tables = _tables()
    res = apply_clamps(_prop([CellEdit(SENSOR_MAF_TRANSFER, 0, 2, STOCK[2] * 1.2)]), _ctx(tables))
    assert res.clamped_edits[0].new_value == pytest.approx(STOCK[2] * 1.2)


def test_clamp_enforces_monotonicity_against_an_untouched_neighbour():
    """Raising one cell past its untouched successor is physically meaningless and unflashable
    (romread.plausible rejects non-monotonic axes), so the clamp holds it below.

    Uses a TIGHT curve on purpose: on a doubling curve the 40% displacement cap already makes
    monotonicity unreachable, so only closely-spaced breakpoints exercise this bound, and a
    real MAF curve is closely spaced exactly where our correction is largest.
    """
    tight = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
    tables = _tables(tight)
    # +40% of 12.0 is 16.8, well past the untouched neighbour at 13.0
    res = apply_clamps(_prop([CellEdit(SENSOR_MAF_TRANSFER, 0, 2, 16.8)]), _ctx(tables))
    assert res.clamped_edits[0].new_value < tight[3]
    assert "monotonicity_limited" in {v.action for v in res.violations}


def test_monotonicity_holds_a_cell_boxed_in_by_an_already_broken_curve():
    """If the STOCK curve is already non-monotonic, the boxed-in cell does not move at all.

    We refuse to quietly repair a pre-existing defect in cells we were not asked to touch -
    that would hide a bad ROM read or a bad definition behind our own edit.
    """
    broken = np.array([10.0, 12.0, 11.0, 11.5])      # col 1 already exceeds col 3
    tables = _tables(broken)
    res = apply_clamps(_prop([CellEdit(SENSOR_MAF_TRANSFER, 0, 2, 13.0)]), _ctx(tables))
    assert res.clamped_edits[0].new_value == pytest.approx(11.0)   # held at its current value
    assert "monotonicity_limited" in {v.action for v in res.violations}


def test_full_pipeline_applies_a_real_curve_correction():
    tables = _tables()
    grid = _grid(tables, [4.0, 8.0, 16.0], [15.0, 25.0, 30.0])
    prop, _ = propose_maf_correction(grid, tables, MafState(), CFG.algo)
    new_tables, res = apply_proposal(tables, prop, _ctx(tables))
    assert res.ok
    curve = new_tables.get(SENSOR_MAF_TRANSFER).values
    assert np.all(np.diff(curve) > 0), "corrected curve must stay strictly ascending"
    assert curve[2] > STOCK[2] and curve[3] > STOCK[3]
    assert curve[0] == STOCK[0] and curve[7] == STOCK[7]      # outside the span, untouched
    assert np.array_equal(tables.get(SENSOR_MAF_TRANSFER).values, STOCK)   # COPY semantics


# --- extrapolation above the measured span (opt-in, 2026-08-30) ---------------------------

def _baseline(values=STOCK):
    t = Table(SENSOR_MAF_TRANSFER, "curve_1d", np.array(values, dtype=float), units="g/s")
    return TableSet({SENSOR_MAF_TRANSFER: t})


def test_extrapolation_is_off_by_default():
    """Rule 1 of the module is still NEVER EXTRAPOLATE. Turning it on is a deliberate act."""
    tables = _tables()
    grid = _grid(tables, [4.0, 8.0], [20.0, 25.0])
    prop, _ = propose_maf_correction(grid, tables, MafState(), CFG.algo)
    assert max(e.col for e in prop.edits) == 3        # nothing above the measured span
    assert "extrapolated" not in prop.metadata


def test_extrapolation_holds_the_plateau_flat_rather_than_fitting_a_trend():
    """The measured error PLATEAUS at the top (~+32% across 42-59 g/s on the real car), so the
    honest continuation is flat. Fitting a slope through a plateau and projecting it invents a
    rise the data does not show, the exact mistake the no-extrapolation rule guards against."""
    tables = _tables()
    grid = _grid(tables, [4.0, 8.0, 16.0], [20.0, 20.0, 20.0])
    prop, _ = propose_maf_correction(grid, tables, MafState(), CFG.algo,
                                     baseline=_baseline(), extrapolate=True)
    assert prop.metadata["extrapolated"] is True
    extra = [e for e in prop.edits if "EXTRAPOLATED" in e.reason]
    assert extra, "expected cells above the measured span to move"
    ratio = prop.metadata["plateau_ratio"]
    for e in extra:
        assert e.new_value == pytest.approx(STOCK[e.col] * ratio)   # same ratio, every cell
    assert ratio <= prop.metadata["max_measured_ratio"] + 1e-9


def test_extrapolation_only_extends_the_span_never_fills_a_hole_inside_it():
    tables = _tables()
    grid = _grid(tables, [4.0, 16.0], [20.0, 20.0])          # gap at cols 3 (8.0)
    prop, _ = propose_maf_correction(grid, tables, MafState(), CFG.algo,
                                     baseline=_baseline(), extrapolate=True)
    inside = [e for e in prop.edits if e.col == 3]
    assert inside and "EXTRAPOLATED" not in inside[0].reason, \
        "an interior gap is INTERPOLATED from its neighbours, not extrapolated"


def test_clamp_refuses_extrapolation_unless_a_HUMAN_enabled_it():
    """The evidence rule is waived only by ctx.sensor_extrapolation_ok, which the CLI sets from
    --extrapolate-maf. A proposal cannot vouch for itself."""
    tables = _tables()
    counts = {SENSOR_MAF_TRANSFER: tuple([40] * 4 + [0] * 4)}     # evidence only up to col 3
    edit = CellEdit(SENSOR_MAF_TRANSFER, 0, 5, STOCK[5] * 1.30)
    lying = Proposal("p", "maf_transfer", (edit,), "sensor", "llm:v1",
                     {"extrapolated": True, "sensor_extrapolation_ok": True})
    res = apply_clamps(lying, ClampContext(tables, CFG.safety, sensor_sample_counts=counts,
                                           baseline_tables=_baseline()))
    assert res.clamped_edits[0].new_value == pytest.approx(STOCK[5])   # held at stock
    assert "insufficient_evidence" in {v.action for v in res.violations}


def test_clamp_allows_extrapolation_above_the_span_when_enabled():
    """Mirrors the real car: the evidenced region is ALREADY corrected +35% against stock, so
    extending the plateau at +30% sits inside the largest measured correction."""
    corrected = np.where(np.arange(len(STOCK)) < 4, STOCK * 1.35, STOCK)
    tables = _tables(corrected)
    counts = {SENSOR_MAF_TRANSFER: tuple([40] * 4 + [0] * 4)}
    res = apply_clamps(_prop([CellEdit(SENSOR_MAF_TRANSFER, 0, 5, STOCK[5] * 1.30)]),
                       ClampContext(tables, CFG.safety, sensor_sample_counts=counts,
                                    baseline_tables=_baseline(),
                                    sensor_extrapolation_ok=True))
    assert res.clamped_edits[0].new_value == pytest.approx(STOCK[5] * 1.30)
    assert "extrapolation_allowed" in {v.action for v in res.violations}


def test_clamp_still_refuses_to_extrapolate_INSIDE_the_evidenced_span():
    """Above the span is an extension; inside it is a hole the neighbours already answer."""
    tables = _tables()
    counts = {SENSOR_MAF_TRANSFER: (40, 40, 0, 40, 40, 0, 0, 0)}   # col 2 is a hole
    res = apply_clamps(_prop([CellEdit(SENSOR_MAF_TRANSFER, 0, 2, STOCK[2] * 1.30)]),
                       ClampContext(tables, CFG.safety, sensor_sample_counts=counts,
                                    baseline_tables=_baseline(),
                                    sensor_extrapolation_ok=True))
    assert res.clamped_edits[0].new_value == pytest.approx(STOCK[2])
    assert "insufficient_evidence" in {v.action for v in res.violations}


def test_extrapolation_can_never_exceed_the_largest_correction_ever_MEASURED():
    """A bad plateau estimate cannot run away: the clamp caps an evidence-free cell at the
    biggest ratio-vs-stock among cells that actually have evidence."""
    tight = np.array([10.0, 12.0, 14.0, 16.0, 40.0, 60.0, 80.0, 100.0])
    tables = _tables(tight)                                    # current == 1.0x baseline here
    counts = {SENSOR_MAF_TRANSFER: tuple([40] * 4 + [0] * 4)}
    res = apply_clamps(_prop([CellEdit(SENSOR_MAF_TRANSFER, 0, 5, tight[5] * 1.30)]),
                       ClampContext(tables, CFG.safety, sensor_sample_counts=counts,
                                    baseline_tables=_tables(tight),
                                    sensor_extrapolation_ok=True))
    # every evidenced cell sits at exactly 1.0x its baseline, so no correction is permitted
    assert res.clamped_edits[0].new_value == pytest.approx(tight[5])
    assert "insufficient_evidence" in {v.action for v in res.violations}
