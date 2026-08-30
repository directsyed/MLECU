"""Property-based (hypothesis) tests — the PROVABLE bounds of the safety layer. These are the
mathematical heart of "deterministic clamps give provable bounds": they assert the invariants
hold for *any* input, not just hand-picked cases."""
from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ecutune.core.config import load_config
from ecutune.core.models import CellEdit, ClampContext, Proposal, Table, TableAxis, TableSet
from ecutune.safety import apply_clamps

SAFETY = load_config().safety


def _fuel_scalar(val):
    return Table("fuel.injector_flow", "scalar", np.array(float(val)), units="cc/min")


def _ctx(ts, **kw):
    return ClampContext(ts, SAFETY, **kw)


def _fuel_prop(new):
    return Proposal("p", "idle_stage2", (CellEdit("fuel.injector_flow", 0, 0, new),),
                    "fuel", "algorithm:test")


@settings(deadline=None, max_examples=300)
@given(cur=st.floats(1.0, 1e4), new=st.floats(-1e4, 1e4))
def test_ve_rate_bound_always(cur, new):
    """For ANY current value and ANY requested value, the clamped fuel change is <= 3% of
    current AND never flips the sign of the requested correction (never overshoots, never
    inverts). This is THE provable bound the whole safety story rests on."""
    ts = TableSet({"fuel.injector_flow": _fuel_scalar(cur)})
    clamped = apply_clamps(_fuel_prop(new), _ctx(ts)).clamped_edits[0].new_value
    assert abs(clamped - cur) <= 0.03 * abs(cur) + 1e-6
    if new > cur:
        assert cur - 1e-9 <= clamped <= new + 1e-9
    elif new < cur:
        assert new - 1e-9 <= clamped <= cur + 1e-9


@settings(deadline=None, max_examples=300)
@given(cur=st.floats(1.0, 1e4), new=st.floats(-1e4, 1e4))
def test_ve_rate_idempotent(cur, new):
    """clamp(clamp(x)) == clamp(x): a clamped proposal re-clamps to itself. Without this, the
    iterative loop could ratchet past the bound across re-evaluations."""
    ts = TableSet({"fuel.injector_flow": _fuel_scalar(cur)})
    v1 = apply_clamps(_fuel_prop(new), _ctx(ts)).clamped_edits[0].new_value
    v2 = apply_clamps(_fuel_prop(v1), _ctx(ts)).clamped_edits[0].new_value
    assert abs(v2 - v1) <= 1e-9


@settings(deadline=None, max_examples=100)
@given(new=st.floats(-1e4, 1e4))
def test_knock_empties_always(new):
    """knock_active => NO edit ever survives, for any proposal."""
    ts = TableSet({"fuel.injector_flow": _fuel_scalar(750.0)})
    res = apply_clamps(_fuel_prop(new), _ctx(ts, knock_active=True))
    assert res.clamped_edits == ()
    assert res.ok is False


@settings(deadline=None, max_examples=300)
@given(target=st.floats(8.0, 20.0), cur=st.floats(9.0, 16.0))
def test_afr_floor_never_lean_at_boost(target, cur):
    """No surviving in-boost AFR edit is ever leaner than the floor, for any current/target."""
    t = Table("fuel.target_afr_primary_a", "map_2d", np.array([[cur]]), units="AFR",
              x_axis=TableAxis("load", (2.0,), "g/rev"), y_axis=TableAxis("rpm", (3000.0,), "rpm"))
    ts = TableSet({t.table_id: t})
    prop = Proposal("p", "s", (CellEdit("fuel.target_afr_primary_a", 0, 0, target),),
                    "fuel", "algorithm:test")
    final = apply_clamps(prop, ClampContext(ts, SAFETY)).clamped_edits[0].new_value
    assert final <= SAFETY.afr_floor + 1e-9


# --- sensor recalibration (clamp_sensor_calibration, 2026-08-27) --------------------------
#
# The sensor clamp trades the fuel clamps' VELOCITY bound for a DISPLACEMENT bound, so it owes
# the same standard of proof: the cap must hold for ANY requested value, the clamp must be
# idempotent, and it must not perturb the fuel path it deliberately bypasses.

from ecutune.core.tables import SENSOR_MAF_TRANSFER   # noqa: E402


def _maf_curve(vals):
    return Table(SENSOR_MAF_TRANSFER, "curve_1d", np.array(vals, dtype=float), units="g/s")


def _sensor_prop(col, new):
    return Proposal("s", "maf_transfer", (CellEdit(SENSOR_MAF_TRANSFER, 0, col, new),),
                    "sensor", "algorithm:test")


# A doubling curve: neighbours are 100% apart, so the 40% cap always binds before monotonicity
# does. That isolates the displacement bound, which is what this property is about.
_CURVE = (1.0, 2.0, 4.0, 8.0, 16.0)


@settings(deadline=None, max_examples=400)
@given(new=st.floats(-1e5, 1e5), col=st.integers(1, 3))
def test_sensor_recal_never_exceeds_the_cap(new, col):
    """|final/stock - 1| <= max_sensor_recal, for ANY requested value including negative ones."""
    ts = TableSet({SENSOR_MAF_TRANSFER: _maf_curve(_CURVE)})
    final = apply_clamps(_sensor_prop(col, new), _ctx(ts)).clamped_edits[0].new_value
    stock = _CURVE[col]
    assert abs(final / stock - 1.0) <= SAFETY.max_sensor_recal + 1e-9


@settings(deadline=None, max_examples=300)
@given(new=st.floats(-1e5, 1e5), col=st.integers(1, 3))
def test_sensor_recal_idempotent(new, col):
    """clamp(clamp(x)) == clamp(x) — the invariant that stops an iterative loop ratcheting."""
    ts = TableSet({SENSOR_MAF_TRANSFER: _maf_curve(_CURVE)})
    v1 = apply_clamps(_sensor_prop(col, new), _ctx(ts)).clamped_edits[0].new_value
    v2 = apply_clamps(_sensor_prop(col, v1), _ctx(ts)).clamped_edits[0].new_value
    assert abs(v2 - v1) <= 1e-9


@settings(deadline=None, max_examples=300)
@given(new=st.floats(-1e5, 1e5), col=st.integers(1, 3))
def test_sensor_clamp_leaves_the_fuel_path_byte_identical(new, col):
    """A 'fuel' proposal is bounded EXACTLY as it was before this clamp existed.

    Proves the new category is additive: the +/-3% velocity limit still governs fuel, and the
    sensor clamp cannot loosen it. Run against the same table id the sensor clamp owns, so the
    only thing separating the two paths is targets_kind.
    """
    ts = TableSet({SENSOR_MAF_TRANSFER: _maf_curve(_CURVE)})
    fuel = Proposal("f", "idle_stage2", (CellEdit(SENSOR_MAF_TRANSFER, 0, col, new),),
                    "fuel", "algorithm:test")
    final = apply_clamps(fuel, _ctx(ts)).clamped_edits[0].new_value
    stock = _CURVE[col]
    assert abs(final - stock) <= SAFETY.max_ve_step * abs(stock) + 1e-9


@settings(deadline=None, max_examples=300)
@given(vals=st.lists(st.floats(1.0, 50.0), min_size=4, max_size=8, unique=True),
       new=st.floats(-1e3, 1e3))
def test_sensor_corrected_curve_never_breaks_a_sound_ordering(vals, new):
    """If the stock curve is strictly ascending, the corrected curve still is — for any request.

    This is the bound that keeps output flashable: romread.plausible() rejects a non-monotonic
    axis, so a curve that doubles back could never be written anyway.
    """
    curve = tuple(sorted(vals))
    ts = TableSet({SENSOR_MAF_TRANSFER: _maf_curve(curve)})
    col = len(curve) // 2
    res = apply_clamps(_sensor_prop(col, new), _ctx(ts))
    out = list(curve)
    out[col] = res.clamped_edits[0].new_value
    assert all(b > a for a, b in zip(out, out[1:])), f"ordering broken: {out}"


# --- ignition timing (clamp_timing_rate_limit, 2026-08-30) --------------------------------
# Timing was bounded by exactly ONE clamp before this: the row ceiling. These are the bounds
# that make "deterministic clamps give provable bounds" true for the category where the only
# direction we ever move is retard — and where over-retard is silent on this car, which is
# fully catless with no EGT sensor.

_TIMING = "ignition.base_timing"
# The Base Timing load axis as the ROM STORES it (float32). Using the decimal literals here
# would test a ceiling the real map never selects — that was blocker 1.
_ROM_LOADS = (0.25, 0.3999999761581421, 0.5499999523162842, 0.699999988079071,
              0.8499999642372131, 0.8999999761581421, 1.0)
_LSB = 0.3515625        # Base Timing is uint8 at 0.3516 deg/step


def _timing_map(cur, load, rpm=2400.0):
    return Table(_TIMING, "map_2d", np.array([[float(cur)]]), units="deg",
                 x_axis=TableAxis("Engine Load", (load,), "g/rev"),
                 y_axis=TableAxis("Engine Speed", (rpm,), "rpm"))


def _timing_prop(new):
    return Proposal("t", "timing_retard", (CellEdit(_TIMING, 0, 0, new),),
                    "timing", "algorithm:test")


def _clamped(cur, new, load, **ctxkw):
    ts = TableSet({_TIMING: _timing_map(cur, load)})
    ctxkw.setdefault("fuel_trims_converged", True)
    res = apply_clamps(_timing_prop(new), ClampContext(ts, SAFETY, **ctxkw))
    return res.clamped_edits[0].new_value if res.clamped_edits else None


@settings(deadline=None, max_examples=400)
@given(cur=st.floats(2.0, 45.0), new=st.floats(-50.0, 90.0),
       load=st.sampled_from(_ROM_LOADS))
def test_timing_never_advances_and_never_outruns_the_step(cur, new, load):
    """For ANY current value and ANY requested value: the surviving timing edit is never more
    advanced than the cell already is, and never moves further than max_timing_step.

    The first half is the property clamp_knock_auto_abort and clamp_fuel_before_timing grant
    their exemptions on, so it has to hold for arbitrary input, not just for what the stage
    happens to emit."""
    got = _clamped(cur, new, load)
    assert got <= cur + 1e-9, "a timing edit ADVANCED the cell"
    assert cur - got <= SAFETY.max_timing_step + 1e-9


@settings(deadline=None, max_examples=400)
@given(cur=st.floats(2.0, 45.0), new=st.floats(-50.0, 90.0),
       load=st.sampled_from(_ROM_LOADS))
def test_timing_respects_the_ceiling_as_far_as_one_step_allows(cur, new, load):
    """A surviving edit sits at or below its ceiling UNLESS the 6 deg/iteration rate limit is
    what stopped it. The ceiling picks the destination; the rate limit paces the journey (D31),
    so the reachable bound in one pass is max(ceiling, cur - step)."""
    got = _clamped(cur, new, load)
    ceiling = SAFETY.timing_ceiling_for(2400.0, load)
    assert got <= max(ceiling, cur - SAFETY.max_timing_step) + 1e-9


@settings(deadline=None, max_examples=300)
@given(cur=st.floats(2.0, 45.0), new=st.floats(-50.0, 90.0),
       load=st.sampled_from(_ROM_LOADS))
def test_timing_clamp_is_idempotent(cur, new, load):
    """clamp(clamp(x)) == clamp(x) against an unchanged table. Without this the loop could
    ratchet past the bound across re-evaluations of the same proposal."""
    v1 = _clamped(cur, new, load)
    v2 = _clamped(cur, v1, load)
    assert abs(v2 - v1) <= 1e-9


@settings(deadline=None, max_examples=200)
@given(cur=st.floats(2.0, 45.0), new=st.floats(-50.0, 90.0),
       load=st.sampled_from(_ROM_LOADS))
def test_timing_bound_survives_uint8_storage(cur, new, load):
    """The bound has to hold in the FLASHED BYTES, not just in memory.

    This is the same class of defect as the float32 monotonicity collapse found on 2026-08-27:
    an in-memory guarantee that does not survive encoding is not a guarantee. Base Timing is
    uint8 at 0.3516 deg/step and the timing write uses round_mode='no_greater', so the stored
    value may be up to one LSB further RETARDED than approved — and never one LSB advanced."""
    from ecutune.romread.defs import Scaling
    from ecutune.romread.reader import _apply
    from ecutune.safety.romwrite.encoder import encode
    sc = Scaling(name="BaseTiming", storagetype="uint8", toexpr="(x*.3515625)-20",
                 frexpr="(x+20)/.3515625", units="deg", endian="big")
    got = _clamped(cur, new, load)
    blob, _ = encode(np.array([got]), sc, "no_greater")
    stored = float(_apply(sc.toexpr, np.frombuffer(blob, dtype=">u1"))[0])
    assert stored <= got + 1e-9, "encoding ADVANCED a value past what the clamp allowed"
    assert cur - stored <= SAFETY.max_timing_step + _LSB + 1e-9


def _converge(start, load, target, steps=40, **ctxkw):
    """Re-run the clamp with the table updated each pass, as the real multi-iteration loop
    does, and return where it settles."""
    cur = start
    for _ in range(steps):
        nxt = _clamped(cur, target, load, **ctxkw)
        assert nxt <= cur + 1e-9, "an iteration ADVANCED the cell"
        if abs(nxt - cur) <= 1e-9:
            return cur
        cur = nxt
    raise AssertionError(f"no fixed point after {steps} iterations (at {cur})")


@settings(deadline=None, max_examples=100)
@given(start=st.floats(23.0, 45.0), load=st.sampled_from(_ROM_LOADS))
def test_unbounded_retard_requests_settle_on_the_absolute_floor(start, load):
    """Asking for maximum retard, forever, settles at `min_timing_advance` — it does not walk.

    THIS TEST FOUND A REAL HOLE (2026-08-30). The cumulative floor goes inert without a
    baseline and the ceiling is a MAXIMUM, so before `min_timing_advance` existed this walked
    a cell past 0 deg and on into after-TDC indefinitely — 12 iterations reached -49 deg. A
    rate limit that bounds a single step does not bound a sequence.
    """
    settled = _converge(start, load, -100.0)
    assert settled == pytest.approx(SAFETY.min_timing_advance)


@settings(deadline=None, max_examples=100)
@given(start=st.floats(30.0, 45.0), load=st.sampled_from(_ROM_LOADS[2:]))
def test_iterations_converge_onto_the_ceiling_and_stop_there(start, load):
    """The multi-pass behaviour Syed's 6 deg/iteration ruling implies: with the ceiling as the
    target, the map walks DOWN to it over several passes, never below it, and then stops."""
    ceiling = SAFETY.timing_ceiling_for(2400.0, load)
    settled = _converge(start, load, ceiling)
    assert settled == pytest.approx(min(start, ceiling))


@settings(deadline=None, max_examples=100)
@given(base=st.floats(30.0, 45.0), load=st.sampled_from(_ROM_LOADS))
def test_iterations_settle_on_the_cumulative_floor_when_a_baseline_is_present(base, load):
    """With the archived stock ROM supplied, the sequence stops at `max_timing_retard` below
    stock — or at the absolute floor, whichever is reached first."""
    stock = TableSet({_TIMING: _timing_map(base, load)})
    settled = _converge(base, load, -100.0, baseline_tables=stock)
    assert settled == pytest.approx(max(base - SAFETY.max_timing_retard,
                                        SAFETY.min_timing_advance))


@settings(deadline=None, max_examples=200)
@given(base=st.floats(20.0, 45.0), cur_off=st.floats(0.0, 25.0), load=st.sampled_from(_ROM_LOADS))
def test_cumulative_retard_floor_holds_against_stock(base, cur_off, load):
    """No surviving edit ever sits more than max_timing_retard below the ARCHIVED STOCK ROM,
    for any starting point. Step bounds do not bound distance."""
    cur = base - cur_off
    ts = TableSet({_TIMING: _timing_map(cur, load)})
    stock = TableSet({_TIMING: _timing_map(base, load)})
    res = apply_clamps(_timing_prop(-100.0),
                       ClampContext(ts, SAFETY, baseline_tables=stock,
                                    fuel_trims_converged=True))
    got = res.clamped_edits[0].new_value
    assert got <= cur + 1e-9
    assert base - got <= SAFETY.max_timing_retard + 1e-9 or got == pytest.approx(cur)
