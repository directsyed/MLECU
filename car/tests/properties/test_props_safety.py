"""Property-based (hypothesis) tests — the PROVABLE bounds of the safety layer. These are the
mathematical heart of "deterministic clamps give provable bounds": they assert the invariants
hold for *any* input, not just hand-picked cases."""
from __future__ import annotations

import numpy as np
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
