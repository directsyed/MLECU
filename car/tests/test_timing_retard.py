"""The ignition-timing stage, its clamp, and the five blockers this arc had to clear first.

The plan (`docs/PLAN-timing-stage-2026-08-30.md`) found five defects that would each have made
the timing stage silently wrong rather than loudly broken. Each has a test here named after it,
because "we fixed it" is not a property — "it stays fixed" is.
"""
from __future__ import annotations

import pathlib

import numpy as np
import pytest

from ecutune.algorithms import (TimingState, ceiling_grid, grid_spec_for_timing,
                                iam_deficit_degrees, propose_timing_retard)
from ecutune.core.config import load_config
from ecutune.core.models import (CellEdit, ClampContext, Proposal, Table, TableAxis, TableSet)
from ecutune.core.tables import IGNITION_BASE_TIMING
from ecutune.logparse.binning import bin_log
from ecutune.logparse.romraider_csv import LogTable
from ecutune.platforms.subaru_ecuflash import TO_PLATFORM, VARIANTS
from ecutune.romread import EcuFlashDefs, RomImage, read_semantic_tables
from ecutune.safety import apply_clamps, apply_proposal, clamps
from ecutune.safety.romwrite import patch
from ecutune.safety.romwrite.encoder import encode
from ecutune.simulation.rom_seed import DEFAULT_DEFS, SIBLING_DEFS

CFG = load_config()
ROM_DIR = pathlib.Path(__file__).resolve().parents[1] / "ecu" / "rom read"

# The Base Timing load axis AS THE ROM ACTUALLY STORES IT — float32, so the decimal literals in
# config.yaml are NOT these numbers. Hardcoded on purpose: this is the regression pin for
# blocker 1, and reading them from the ROM would let the test drift with the ROM.
ROM_LOAD_BREAKS = (0.25, 0.3999999761581421, 0.5499999523162842, 0.699999988079071,
                   0.8499999642372131, 0.8999999761581421, 1.0, 1.149999976158142)
ROM_RPM_BREAKS = tuple(800.0 + 400.0 * i for i in range(18))


def _map(values, loads=ROM_LOAD_BREAKS, rpms=None):
    a = np.asarray(values, dtype=float)
    rpms = rpms if rpms is not None else ROM_RPM_BREAKS[:a.shape[0]]
    return Table(IGNITION_BASE_TIMING, "map_2d", a, units="deg",
                 x_axis=TableAxis("Engine Load", tuple(loads[:a.shape[1]]), "g/rev"),
                 y_axis=TableAxis("Engine Speed", tuple(rpms), "rpm"))


def _ts(values, **kw):
    return TableSet({IGNITION_BASE_TIMING: _map(values, **kw)})


def _prop(edits, kind="timing"):
    return Proposal("t", "timing_retard", tuple(edits), kind, "algorithm:test")


def _ctx(ts, **kw):
    kw.setdefault("fuel_trims_converged", True)
    return ClampContext(ts, CFG.safety, **kw)


# ============================================ blocker 1: ceilings that never fired

def test_load_ceilings_fire_at_the_ROMs_real_float32_breakpoints():
    """THE blocker-1 regression pin.

    config.yaml ratifies bands at load >= 0.55 and >= 0.85. The ROM stores those breakpoints as
    float32: 0.5499999523162842 and 0.8499999642372131. A bare `load >= 0.55` is FALSE at both,
    so BOTH ratified bands silently started one column late — col 2 got the 45 deg cruise
    ceiling instead of 30, and col 4, where this car makes boost, got 30 instead of 22.

    Asserted against the stored breakpoints, never against the decimal literals.
    """
    # Values track the ratified timing_ceiling_map; what this test pins is that the ROM's
    # float32 breakpoints SELECT THE INTENDED COLUMN. 0.5499999523 must land in the 0.55 band
    # and 0.8499999642 in the 0.85 band -- a bare `>=` puts both one column late.
    ceilings = [CFG.safety.timing_ceiling_for(3200.0, b) for b in ROM_LOAD_BREAKS]
    m = CFG.safety.timing_ceiling_map
    row = m.ceilings[[i for i, r in enumerate(m.rpm_breaks) if 3200.0 >= r][-1]]
    want = [row[max(j for j, l in enumerate(m.load_breaks) if b >= l - 1e-6)]
            for b in ROM_LOAD_BREAKS]
    assert ceilings == want
    assert ceilings[2] == row[1] and ceilings[4] == row[2], "a band started one column late"
    assert ceilings[2] != ceilings[1], "the 0.55 band must differ from the cruise band"


def test_the_epsilon_does_not_reach_the_neighbouring_breakpoint():
    """Tolerance must be small enough that it cannot pull in the column BELOW the band.

    The gap between real breakpoints is ~0.15 g/rev; float32 error is ~1e-7. A tolerance that
    split the difference would be a silent widening of a ratified safety limit.
    """
    below = 0.3999999761581421      # the column under the 0.55 band
    assert CFG.safety.timing_ceiling_for(3200.0, below) == 45.0
    assert CFG.safety.timing_ceiling_for(3200.0, 0.5499) == 45.0   # genuinely below, not float32


# ============================================ blocker 4: the bounds timing never had

def test_rate_limit_bounds_any_step():
    ts = _ts([[40.0]])
    res = apply_clamps(_prop([CellEdit(IGNITION_BASE_TIMING, 0, 0, 5.0)]), _ctx(ts))
    assert res.clamped_edits[0].new_value == pytest.approx(40.0 - CFG.safety.max_timing_step)
    assert "rate_limited" in {v.action for v in res.violations}


def test_advance_is_refused_outright():
    """Nothing in this stage should ever add advance, so an advancing edit is held at current."""
    ts = _ts([[30.0]])
    res = apply_clamps(_prop([CellEdit(IGNITION_BASE_TIMING, 0, 0, 33.0)]), _ctx(ts))
    assert res.clamped_edits[0].new_value == 30.0
    assert any("advance_refused" in v.action for v in res.violations)


def test_cumulative_retard_floor_against_the_stock_rom():
    """The ceiling bounds how much ADVANCE a cell may carry; nothing bounded how much RETARD
    could accumulate. At 6 deg/iteration a sustained wrong diagnosis walks the map to zero."""
    stock = _ts([[40.0]])
    already = _ts([[40.0 - CFG.safety.max_timing_retard + 1.0]])    # 1 deg of headroom left
    res = apply_clamps(_prop([CellEdit(IGNITION_BASE_TIMING, 0, 0, 0.0)]),
                       _ctx(already, baseline_tables=stock))
    assert res.clamped_edits[0].new_value == pytest.approx(40.0 - CFG.safety.max_timing_retard)
    assert any("retard_envelope_limited" in v.action for v in res.violations)


def test_cumulative_floor_is_inert_without_a_baseline():
    ts = _ts([[40.0]])
    res = apply_clamps(_prop([CellEdit(IGNITION_BASE_TIMING, 0, 0, 0.0)]), _ctx(ts))
    assert res.clamped_edits[0].new_value == pytest.approx(34.0)   # rate limit only


def test_ceiling_then_rate_limit_compose():
    """The ordering that made Syed's 6 deg/iteration ruling real (D31).

    The ceiling floors a cell to an absolute value in ONE move — up to 18.12 deg on this ROM.
    Running it after the rate limit would let it override the ratified step. Running it BEFORE
    means the ceiling picks the destination and the rate limit paces the journey.
    """
    ts = _ts([[45.0] * 5], loads=ROM_LOAD_BREAKS[:5])
    res = apply_clamps(_prop([CellEdit(IGNITION_BASE_TIMING, 0, 4, 45.0)]), _ctx(ts))
    ceiling = CFG.safety.timing_ceiling_for(800.0, ROM_LOAD_BREAKS[4])
    assert ceiling < 45.0 - CFG.safety.max_timing_step, "test needs a ceiling beyond one step"
    assert res.clamped_edits[0].new_value == pytest.approx(45.0 - CFG.safety.max_timing_step)


def test_fuel_clamps_are_untouched_by_the_timing_clamp():
    """Disjoint routing, the same property clamp_sensor_calibration was built to hold."""
    ts = _ts([[40.0]])
    res = apply_clamps(_prop([CellEdit(IGNITION_BASE_TIMING, 0, 0, 20.0)], kind="fuel"),
                       _ctx(ts))
    assert res.clamped_edits[0].new_value == pytest.approx(40.0 * (1 - CFG.safety.max_ve_step))
    assert "ve_rate_limit" in {v.clamp for v in res.violations}


# ============================================ blocker 2: the gates that were inert

def test_knock_abort_still_kills_a_fuel_proposal():
    ts = TableSet({"fuel.injector_flow": Table("fuel.injector_flow", "scalar",
                                               np.array(750.0), units="cc/min")})
    res = apply_clamps(Proposal("p", "s", (CellEdit("fuel.injector_flow", 0, 0, 740.0),),
                                "fuel", "algorithm:test"), _ctx(ts, knock_active=True))
    assert res.ok is False and res.aborted_by == "knock_auto_abort"


def test_knock_abort_exempts_a_verified_retard_only_timing_proposal():
    """The car knocks — that is why this stage exists. Without the exemption the clamp aborts
    the one change that reduces the hazard it is reacting to."""
    ts = _ts([[40.0]])
    res = apply_clamps(_prop([CellEdit(IGNITION_BASE_TIMING, 0, 0, 36.0)]),
                       _ctx(ts, knock_active=True))
    assert res.ok
    assert res.clamped_edits[0].new_value == pytest.approx(36.0)
    assert "knock_retard_exemption" in {v.action for v in res.violations}


def test_knock_exemption_is_void_if_ANY_cell_advances():
    ts = _ts([[40.0, 30.0]])
    res = apply_clamps(_prop([CellEdit(IGNITION_BASE_TIMING, 0, 0, 36.0),
                              CellEdit(IGNITION_BASE_TIMING, 0, 1, 31.0)]),
                       _ctx(ts, knock_active=True))
    assert res.ok is False and res.aborted_by == "knock_auto_abort"


def test_knock_exemption_cannot_be_unlocked_by_metadata():
    """The future LLM is a Proposal producer, so a metadata flag would be a safety gate an
    untrusted party could open for itself. Only the live tables are consulted."""
    ts = _ts([[40.0]])
    lying = Proposal("p", "timing_retard", (CellEdit(IGNITION_BASE_TIMING, 0, 0, 44.0),),
                     "timing", "llm:v1", {"retard_only": True, "safe": True})
    res = apply_clamps(lying, _ctx(ts, knock_active=True))
    assert res.ok is False and res.aborted_by == "knock_auto_abort"


def test_fuel_before_timing_still_defers_a_proposal_that_advances():
    ts = _ts([[30.0]])
    res = apply_clamps(_prop([CellEdit(IGNITION_BASE_TIMING, 0, 0, 34.0)]),
                       _ctx(ts, fuel_trims_converged=False))
    assert res.ok is False
    assert res.violations[0].action == "deferred"


def test_fuel_before_timing_exempts_retard_only():
    ts = _ts([[40.0]])
    res = apply_clamps(_prop([CellEdit(IGNITION_BASE_TIMING, 0, 0, 36.0)]),
                       _ctx(ts, fuel_trims_converged=False))
    assert res.ok
    assert "retard_only_exemption" in {v.action for v in res.violations}


# ============================================ the stage

def _log(cells, n_each=40, iam=0.5, knock=0.0, fine=0.0):
    """A synthetic steady log visiting each (rpm, load) cell n_each times."""
    rpm, load, kn, fk = [], [], [], []
    for r, l in cells:
        rpm += [r] * n_each
        load += [l] * n_each
        kn += [knock] * n_each
        fk += [fine] * n_each
    n = len(rpm)
    return LogTable({"rpm": np.array(rpm, float), "load": np.array(load, float),
                     "tps": np.full(n, 20.0), "knock_retard": np.array(kn, float),
                     "fine_knock_learn": np.array(fk, float), "iam": np.full(n, iam),
                     "af_correction": np.zeros(n), "af_learning": np.zeros(n)})


def _grid_for(tables, log):
    return bin_log(log, grid_spec_for_timing(tables.get(IGNITION_BASE_TIMING)))


def test_undriven_cells_get_the_ceiling_and_nothing_else():
    """Syed's ruling: apply the ceiling to undriven cells — it is an octane/compression limit,
    not a measurement, and the drive to the shop is a highway."""
    ts = _ts([[40.0] * 5], loads=ROM_LOAD_BREAKS[:5], rpms=(800.0,))
    prop, _ = propose_timing_retard(_grid_for(ts, _log([(800.0, 0.25)])), ts, TimingState(),
                                    CFG.algo, CFG.safety)
    by_col = {e.col: e.new_value for e in prop.edits}
    for col in (2, 4):
        assert by_col[col] == pytest.approx(
            CFG.safety.timing_ceiling_for(800.0, ROM_LOAD_BREAKS[col]))
    assert by_col[4] < by_col[2], "the boost column must be held tighter than the cruise column"
    assert 0 not in by_col and 1 not in by_col   # 40 deg is under the 45 deg cruise ceiling


def test_measured_knock_retards_beyond_the_ceiling_requirement():
    ts = _ts([[40.0]], loads=(0.25,), rpms=(800.0,))
    log = _log([(800.0, 0.25)], knock=-3.0, iam=CFG.safety.iam_reference)
    prop, _ = propose_timing_retard(_grid_for(ts, log), ts, TimingState(), CFG.algo, CFG.safety)
    assert prop.edits[0].new_value == pytest.approx(37.0)   # 40 - 3, ceiling is 45
    assert prop.targets_kind == "timing"


def test_learned_ADVANCE_is_not_evidence_for_retarding():
    """Fine Learning Knock Correction reached +0.35 deg on the real log — the ECU had learned it
    could give a little advance back. Only the retard half of the channel is evidence."""
    ts = _ts([[40.0]], loads=(0.25,), rpms=(800.0,))
    log = _log([(800.0, 0.25)], fine=+2.0, iam=CFG.safety.iam_reference)
    prop, _ = propose_timing_retard(_grid_for(ts, log), ts, TimingState(), CFG.algo, CFG.safety)
    assert prop.edits == ()


def test_iam_deficit_is_measured_from_the_worst_sample_and_falls_back_cleanly():
    """Without the ROM's advance map, the deficit is the configured scalar fallback."""
    assert iam_deficit_degrees(None, CFG.safety)[0] == 0.0
    assert iam_deficit_degrees(np.array([np.nan, np.nan]), CFG.safety)[0] == 0.0
    assert iam_deficit_degrees(np.array([1.0, 1.0]), CFG.safety)[0] == 0.0
    got, info = iam_deficit_degrees(np.array([1.0, 0.5, 0.0]), CFG.safety)
    assert got == pytest.approx(CFG.safety.iam_reference *
                                CFG.safety.iam_advance_authority_deg)
    assert info["iam_authority_source"] == "config"


def test_iam_reference_and_authority_come_from_the_ROM_when_available():
    """Two ROM-derived facts replace two guesses.

    `Advance Multiplier (Initial)` on this ROM is 0.5, NOT 1.0 — so an observed IAM of 0.500 is
    the factory value and the deficit at IAM 0 is half the advance map, not all of it. And
    `Knock Correction Advance Max` is 0.0 across the entire idle/cruise region, so IAM
    collapsing costs those cells NOTHING: a flat constant was retarding a band the project has
    independently validated as knock-free.
    """
    data = _rom_paths()[0].read_bytes()
    defs = EcuFlashDefs(DEFAULT_DEFS)
    raw, _ = read_semantic_tables(RomImage(data), defs, list(SIBLING_DEFS),
                                  TO_PLATFORM, VARIANTS)
    tables = TableSet(raw)
    target = tables.get(IGNITION_BASE_TIMING)
    got, info = iam_deficit_degrees(np.array([0.5, 0.0]), CFG.safety, tables, target)

    assert info["iam_reference"] == pytest.approx(0.5)
    assert info["iam_reference_source"].startswith("ROM:")
    assert info["iam_authority_source"].startswith("ROM:")
    assert np.asarray(got).shape == np.asarray(target.values).shape
    # idle / cruise: the advance map is zero there, so there is no advance to lose
    assert np.all(np.asarray(got)[:, :3] == 0.0)
    # boost region: real, and larger than the 2.0 deg constant it replaced
    assert np.max(np.asarray(got)) > CFG.safety.iam_advance_authority_deg


def test_idle_cells_are_not_retarded_by_the_iam_term():
    """The regression that motivated reading the ROM: with a flat 2 deg IAM constant, cell
    (0,0) — 800 rpm, 0.25 g/rev, the validated knock-free idle band — was pulled 2.11 deg."""
    data = _rom_paths()[0].read_bytes()
    defs = EcuFlashDefs(DEFAULT_DEFS)
    raw, _ = read_semantic_tables(RomImage(data), defs, list(SIBLING_DEFS),
                                  TO_PLATFORM, VARIANTS)
    tables = TableSet(raw)
    target = tables.get(IGNITION_BASE_TIMING)
    log = _log([(800.0, 0.25)], n_each=60, iam=0.0)          # IAM floored, but NO knock
    deficit, _ = iam_deficit_degrees(log.get("iam"), CFG.safety, tables, target)
    grid = bin_log(log, grid_spec_for_timing(target))
    prop, _ = propose_timing_retard(grid, tables, TimingState(), CFG.algo, CFG.safety,
                                    iam_deficit_deg=deficit)
    assert not [e for e in prop.edits if (e.row, e.col) == (0, 0)]


def test_stage_never_advances_a_cell_and_never_mutates_its_input():
    ts = _ts([[10.0] * 5], loads=ROM_LOAD_BREAKS[:5], rpms=(800.0,))
    before = ts.get(IGNITION_BASE_TIMING).values.copy()
    log = _log([(800.0, l) for l in ROM_LOAD_BREAKS[:5]], knock=-3.0)
    prop, st = propose_timing_retard(_grid_for(ts, log), ts, TimingState(), CFG.algo, CFG.safety)
    assert st.iterations == 1
    for e in prop.edits:
        assert e.new_value <= before[e.row, e.col] + 1e-12
    assert np.array_equal(ts.get(IGNITION_BASE_TIMING).values, before)


def test_stage_refuses_a_grid_built_from_a_different_table():
    ts = _ts([[40.0] * 5], loads=ROM_LOAD_BREAKS[:5], rpms=(800.0,))
    other = _ts([[40.0] * 3], loads=ROM_LOAD_BREAKS[:3], rpms=(800.0,))
    grid = _grid_for(other, _log([(800.0, 0.25)]))
    with pytest.raises(ValueError, match="grid_spec_for_timing"):
        propose_timing_retard(grid, ts, TimingState(), CFG.algo, CFG.safety)


def test_open_loop_samples_are_kept():
    """require_closed_loop=False, unlike the MAF stage: open loop is exactly where this car
    makes boost, and knock is measured identically in both."""
    ts = _ts([[40.0]], loads=(0.25,), rpms=(800.0,))
    spec = grid_spec_for_timing(ts.get(IGNITION_BASE_TIMING))
    assert spec.require_closed_loop is False
    log = _log([(800.0, 0.25)], knock=-3.0)
    log.channels["fuel_system_status"] = np.full(len(log), 10.0)     # all OPEN loop
    assert bin_log(log, spec).count.sum() > 0


# ============================================ blocker 5 / encoder: storage direction

def test_no_greater_rounding_never_stores_more_advance():
    """Base Timing is uint8 at 0.3516 deg/step and encode() rounds to NEAREST, so an approved
    value can land up to +0.176 deg ADVANCED. A ceiling the storage layer may exceed is not a
    ceiling."""
    from ecutune.romread.defs import Scaling
    from ecutune.romread.reader import _apply
    sc = Scaling(name="BaseTiming", storagetype="uint8", toexpr="(x*.3515625)-20",
                 frexpr="(x+20)/.3515625", units="deg", endian="big")
    for want in np.arange(2.0, 45.0, 0.037):
        blob, _ = encode(np.array([want]), sc, "no_greater")
        got = float(_apply(sc.toexpr, np.frombuffer(blob, dtype=">u1"))[0])
        assert got <= want + 1e-9, f"{want} stored as {got}"
        assert want - got < 0.3516 + 1e-9, "never further than one storage step"


# ============================================ blocker 3: the map-2D index bug

def _rom_paths():
    hits = sorted(ROM_DIR.glob("*.bin"))
    if not hits:
        pytest.skip("no archived ROM read available")
    return hits


def test_map_2d_write_round_trips_at_a_cell_with_row_ge_1():
    """THE blocker-3 regression pin, and the reason patch() now reads back every edited cell.

    `report.py` indexed a 2-D map as `row * a.shape[0] + col` on an ALREADY-RAVELED array, so
    shape[0] was 270 (the element count), not 15 (the column count). Never hit, because the only
    table ever written was a 1-D curve. This drives a real 2-D write through the real ROM and
    proves the value lands in the cell it was addressed to.
    """
    data = _rom_paths()[0].read_bytes()
    defs = EcuFlashDefs(DEFAULT_DEFS)
    raw, rep = read_semantic_tables(RomImage(data), defs, list(SIBLING_DEFS),
                                    TO_PLATFORM, VARIANTS)
    tbl = raw[IGNITION_BASE_TIMING]
    assert tbl.values.ndim == 2 and tbl.values.shape[0] > 1
    row, col = 7, 3                                  # row >= 1 is the whole point
    want = float(tbl.values[row, col]) - 4.21875      # 12 storage steps down: exactly representable
    from ecutune.core.models import ClampResult
    w = patch(data, ClampResult(True, (CellEdit(IGNITION_BASE_TIMING, row, col, want),)),
              raw, rep["resolved"], round_modes={IGNITION_BASE_TIMING: "no_greater"})
    back, _ = read_semantic_tables(RomImage(w.data), defs, list(SIBLING_DEFS),
                                   TO_PLATFORM, VARIANTS)
    after = back[IGNITION_BASE_TIMING].values
    assert after[row, col] == pytest.approx(want, abs=0.36)
    changed = np.argwhere(np.abs(after - tbl.values) > 1e-9)
    assert changed.tolist() == [[row, col]], "exactly one cell moved, and it is the one asked for"


def test_change_report_indexes_a_2d_cell_correctly():
    """The report is what Syed reads before deciding to flash; a wrong index there means the
    number he approves is not the number that changes."""
    from ecutune.core.models import ClampResult
    from ecutune.safety.romwrite.report import change_report
    data = _rom_paths()[0].read_bytes()
    defs = EcuFlashDefs(DEFAULT_DEFS)
    raw, rep = read_semantic_tables(RomImage(data), defs, list(SIBLING_DEFS),
                                    TO_PLATFORM, VARIANTS)
    row, col = 9, 6
    want = float(raw[IGNITION_BASE_TIMING].values[row, col]) - 3.515625
    edit = CellEdit(IGNITION_BASE_TIMING, row, col, want)
    res = ClampResult(True, (edit,))
    w = patch(data, res, raw, rep["resolved"],
              round_modes={IGNITION_BASE_TIMING: "no_greater"})
    back, _ = read_semantic_tables(RomImage(w.data), defs, list(SIBLING_DEFS),
                                   TO_PLATFORM, VARIANTS)
    md = change_report(_prop([edit]), res, w, raw, back)
    before_val = float(raw[IGNITION_BASE_TIMING].values[row, col])
    assert f"| {row},{col} |" in md
    line = next(l for l in md.splitlines() if l.startswith(f"| {row},{col} |"))
    assert f"{before_val:.4g}" in line, f"report shows the wrong 'before' value: {line}"


# ============================================ end to end on the real ROM

def test_end_to_end_timing_candidate_on_the_real_rom():
    """ROM -> stage -> clamps -> romwrite, on the archived stock image. Asserts the properties
    the pre-flash audit asserts, so a break shows up in CI and not in a garage."""
    data = _rom_paths()[0].read_bytes()
    defs = EcuFlashDefs(DEFAULT_DEFS)
    raw, rep = read_semantic_tables(RomImage(data), defs, list(SIBLING_DEFS),
                                    TO_PLATFORM, VARIANTS)
    tables = TableSet(raw)
    tbl = tables.get(IGNITION_BASE_TIMING)
    log = _log([(2400.0, 0.8499999642372131), (2400.0, 0.699999988079071)],
               n_each=60, knock=-4.0, iam=0.0)
    grid = bin_log(log, grid_spec_for_timing(tbl))
    deficit, _ = iam_deficit_degrees(log.get("iam"), CFG.safety, tables, tbl)
    prop, _ = propose_timing_retard(grid, tables, TimingState(), CFG.algo, CFG.safety,
                                    iam_deficit_deg=deficit)
    ctx = ClampContext(tables, CFG.safety, baseline_tables=tables, knock_active=True,
                       fuel_trims_converged=False)
    res = apply_clamps(prop, ctx)
    assert res.ok, res.aborted_by
    w = patch(data, res, raw, rep["resolved"],
              round_modes={IGNITION_BASE_TIMING: "no_greater"})
    back, _ = read_semantic_tables(RomImage(w.data), defs, list(SIBLING_DEFS),
                                   TO_PLATFORM, VARIANTS)

    before = np.asarray(tbl.values, float)
    after = np.asarray(back[IGNITION_BASE_TIMING].values, float)
    step_slack = 0.3515625 + 1e-9
    assert np.all(after <= before + 1e-9), "a cell was ADVANCED through the write path"
    assert np.max(before - after) <= CFG.safety.max_timing_step + step_slack
    moved = [s for s in raw if s != IGNITION_BASE_TIMING
             and not np.array_equal(raw[s].values, back[s].values)]
    assert moved == [], f"unrelated tables moved: {moved}"


def test_verify_flash_returns_NO_GO_not_a_traceback_for_a_foreign_rom():
    """A ROM from ANOTHER CAR must produce a verdict, not an exception.

    Found 2026-08-30 by passing a real reference tune (AZ1E401A, an 08 WRX) in as a candidate
    against our A2WC411D. Every identity check fired correctly and then the run died inside
    read_semantic_tables -- reconciliation rightly refuses to guess on a foreign image, but the
    audit swallowed that as a crash. This is the last automated gate before a human touches an
    ECU; a person should not have to interpret a Python stack trace to learn the answer is
    "do not flash this".
    """
    from ecutune.cli import _verify_flash
    rom = _rom_paths()[0]
    foreign = bytearray(rom.read_bytes())
    foreign[0x2000:0x2010] = b"\xff\xff LAZ1E401A\x00ZR1"  # another car's calibration ID (16 B)
    foreign[0x100:0x200] = b"\x00" * 0x100                 # ...and a different boot region
    tmp = rom.parent.parent / "reference-roms-DO-NOT-FLASH" / "_pytest_foreign.bin"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_bytes(bytes(foreign))
    try:
        assert _verify_flash(str(tmp), str(rom)) == 2      # clean NO-GO, no exception
    finally:
        tmp.unlink()


def test_cumulative_retard_bound_can_actually_reach_the_ratified_ceiling():
    """`max_timing_retard` and the ceiling must not fight each other.

    The cumulative floor is measured against the archived stock ROM; the ceiling is an absolute
    cap. If the floor is tighter than the deepest cut the ceiling demands, those cells stall
    short of the ceiling FOREVER and no number of iterations closes the gap -- a standoff
    between two safety limits that each look correct alone.

    This bit for real on 2026-08-30: re-shaping the ceiling took the worst demand from 18.1 to
    27.1 deg while `max_timing_retard` was still 20.0, leaving 35 cells permanently unreachable.
    The relationship is what needs pinning, not either number.
    """
    data = _rom_paths()[0].read_bytes()
    defs = EcuFlashDefs(DEFAULT_DEFS)
    raw, _ = read_semantic_tables(RomImage(data), defs, list(SIBLING_DEFS),
                                  TO_PLATFORM, VARIANTS)
    t = raw[IGNITION_BASE_TIMING]
    stock = np.asarray(t.values, float)
    target = np.maximum(ceiling_grid(t, CFG.safety), CFG.safety.min_timing_advance)
    worst = float(np.max(np.maximum(stock - target, 0.0)))
    assert worst <= CFG.safety.max_timing_retard + 1e-9, (
        f"the ceiling demands {worst:.3f} deg of retard but max_timing_retard is "
        f"{CFG.safety.max_timing_retard} — cells would stall short of their own ceiling")


def test_undriven_cell_reaches_its_ceiling_in_one_pass():
    """Syed's ruling (2026-08-30): a cell the car has never visited is not rate limited.

    The rate limit exists so a step can be OBSERVED on the next drive. A cell with zero samples
    has nothing to observe, so staging it buys no information and leaves it dangerous meanwhile.
    """
    ts = _ts([[45.0] * 5], loads=ROM_LOAD_BREAKS[:5])
    ceiling = CFG.safety.timing_ceiling_for(800.0, ROM_LOAD_BREAKS[4])
    assert 45.0 - ceiling > CFG.safety.max_timing_step, "test needs a gap beyond one step"
    counts = {IGNITION_BASE_TIMING: np.zeros((1, 5))}          # never driven
    res = apply_clamps(_prop([CellEdit(IGNITION_BASE_TIMING, 0, 4, ceiling)]),
                       _ctx(ts, cell_sample_counts=counts))
    assert res.clamped_edits[0].new_value == pytest.approx(ceiling)
    assert "undriven_to_ceiling" in {v.action for v in res.violations}


def test_a_DRIVEN_cell_is_still_rate_limited():
    ts = _ts([[45.0] * 5], loads=ROM_LOAD_BREAKS[:5])
    ceiling = CFG.safety.timing_ceiling_for(800.0, ROM_LOAD_BREAKS[4])
    counts = {IGNITION_BASE_TIMING: np.full((1, 5), 40.0)}     # plenty of samples
    res = apply_clamps(_prop([CellEdit(IGNITION_BASE_TIMING, 0, 4, ceiling)]),
                       _ctx(ts, cell_sample_counts=counts))
    assert res.clamped_edits[0].new_value == pytest.approx(45.0 - CFG.safety.max_timing_step)
    assert "rate_limited" in {v.action for v in res.violations}


def test_the_undriven_exemption_cannot_go_below_the_ceiling():
    """It waives the STEP, never the ceiling. An undriven cell asked to go far below its own
    ceiling is still rate limited — otherwise the exemption would be an unbounded pull."""
    ts = _ts([[45.0] * 5], loads=ROM_LOAD_BREAKS[:5])
    counts = {IGNITION_BASE_TIMING: np.zeros((1, 5))}
    res = apply_clamps(_prop([CellEdit(IGNITION_BASE_TIMING, 0, 4, -50.0)]),
                       _ctx(ts, cell_sample_counts=counts))
    assert res.clamped_edits[0].new_value == pytest.approx(45.0 - CFG.safety.max_timing_step)


def test_the_undriven_exemption_ignores_proposal_metadata():
    """Same discipline as the knock and fuel-before-timing exemptions: anything that RELAXES a
    bound must come from context the proposal producer does not control."""
    ts = _ts([[45.0] * 5], loads=ROM_LOAD_BREAKS[:5])
    ceiling = CFG.safety.timing_ceiling_for(800.0, ROM_LOAD_BREAKS[4])
    lying = Proposal("p", "timing_retard", (CellEdit(IGNITION_BASE_TIMING, 0, 4, ceiling),),
                     "timing", "llm:v1", {"undriven": True, "cell_sample_counts": 0})
    res = apply_clamps(lying, _ctx(ts))                        # no counts in the CONTEXT
    assert res.clamped_edits[0].new_value == pytest.approx(45.0 - CFG.safety.max_timing_step)
