"""`boost_load_threshold` must match the load at which THIS CAR actually makes boost.

The number decides one thing only (`clamps.py:160`): which fuel-target cells `clamp_afr_floor`
bothers to check. It is not a boost limit and it does not keep the car out of boost. But
`clamp_afr_floor` is the last and strongest clamp in the pipeline — it will richen a cell past
the rate limit, because commanding lean under boost is the engine-grenade case — and its
guarantee is only as good as the region it is pointed at.

It shipped at 1.5 g/rev as a pre-data placeholder. The six vacuum drives show this car crossing
atmospheric MAP at roughly 0.6 g/rev, which left every cell between 0.6 and 1.5 — real boost on
this engine, and where all 31 knock events happened — classified as not-boost and skipped.

This test recomputes the crossing point from the committed logs, so the threshold cannot drift
back above what the car measurably does. It is a regression test against a *physical* fact.
"""
from __future__ import annotations

import pathlib

import numpy as np
import pytest

from ecutune.core.config import load_config
from ecutune.core.models import CellEdit, ClampContext, Proposal, Table, TableAxis, TableSet
from ecutune.logparse.romraider_csv import parse_romraider_csv
from ecutune.safety import apply_clamps

DRIVE_DIR = pathlib.Path(__file__).resolve().parents[1] / "logging" / "drive"
SAFETY = load_config().safety


def _measured_boost_onset() -> float:
    """Lowest binned load at which mean MAP reaches atmospheric, from the real drive logs."""
    load, mapp, baro = [], [], []
    for f in sorted(DRIVE_DIR.glob("drive-2026*.csv")):
        lt = parse_romraider_csv(str(f))
        ch = lt.channels
        raw = lt.raw_headers
        i_map = next((h for h in raw if "Manifold Absolute Pressure" in h), None)
        i_atm = next((h for h in raw if "Atmospheric Pressure" in h), None)
        if i_map is None or i_atm is None or "load" not in ch:
            continue
        # MAP/atmospheric are not canonical roles, so pull them straight from the CSV
        import csv as _csv
        with open(f, newline="") as fh:
            rows = list(_csv.reader(fh))
        hdr = [h.strip() for h in rows[0]]
        mi, ai = hdr.index(i_map), hdr.index(i_atm)
        li = next(k for k, h in enumerate(hdr) if h.strip().startswith("Engine Load (4-Byte)"))
        for r in rows[1:]:
            try:
                load.append(float(r[li])); mapp.append(float(r[mi])); baro.append(float(r[ai]))
            except (ValueError, IndexError):
                continue
    if not load:
        pytest.skip("no drive logs with MAP + atmospheric channels")
    load, mapp, baro = np.array(load), np.array(mapp), np.array(baro)
    atm = float(np.nanmedian(baro))
    for lo in np.arange(0.2, 1.5, 0.05):
        k = (load >= lo) & (load < lo + 0.05)
        if k.sum() >= 100 and np.nanmean(mapp[k]) >= atm:
            return float(lo)
    return float("nan")


def test_threshold_is_at_or_below_the_measured_boost_onset():
    onset = _measured_boost_onset()
    assert np.isfinite(onset), "could not measure a boost onset from the logs"
    assert SAFETY.boost_load_threshold <= onset + 1e-9, (
        f"boost_load_threshold={SAFETY.boost_load_threshold} g/rev is ABOVE the measured "
        f"boost onset of {onset:.2f} g/rev — clamp_afr_floor would skip real boost cells")


def test_afr_floor_now_protects_the_cells_where_this_car_knocked():
    """All 31 knock events sat at 0.58-0.79 g/rev. A lean target there must be floored."""
    for load in (0.60, 0.65, 0.79):
        t = Table("fuel.target_afr_primary_a", "map_2d", np.array([[14.7]]), units="AFR",
                  x_axis=TableAxis("load", (load,), "g/rev"),
                  y_axis=TableAxis("rpm", (2200.0,), "rpm"))
        ts = TableSet({t.table_id: t})
        prop = Proposal("p", "s", (CellEdit(t.table_id, 0, 0, 14.7),), "fuel", "algorithm:test")
        res = apply_clamps(prop, ClampContext(ts, SAFETY))
        assert res.clamped_edits[0].new_value == pytest.approx(SAFETY.afr_floor), (
            f"a 14.7 target at {load} g/rev was NOT floored — this car makes boost here")


def test_vacuum_cells_are_untouched_by_the_lower_threshold():
    """Lowering the threshold costs nothing: a 14.7 cruise target is nowhere near the floor,
    so the clamp still never fires below where boost actually starts."""
    t = Table("fuel.target_afr_primary_a", "map_2d", np.array([[14.7]]), units="AFR",
              x_axis=TableAxis("load", (0.35,), "g/rev"),
              y_axis=TableAxis("rpm", (1800.0,), "rpm"))
    ts = TableSet({t.table_id: t})
    prop = Proposal("p", "s", (CellEdit(t.table_id, 0, 0, 14.7),), "fuel", "algorithm:test")
    res = apply_clamps(prop, ClampContext(ts, SAFETY))
    assert res.clamped_edits[0].new_value == pytest.approx(14.7)
    assert res.violations == ()
