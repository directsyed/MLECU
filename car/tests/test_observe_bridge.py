"""The log→layer bridge: real RomRaider CSV holds → Observations → identify().

This is the real-car analog of `simulation.harness.collect_observations` that
`car/logging/CAPTURE-PROTOCOL.md` always specified but was never built. These tests pin two
things: (1) the bridge transforms the THREE COMMITTED REAL HOLDS into the diagnosis Claude read
by hand (no leak; ~5% rich bias that the layer honestly refuses to pin to MAF-vs-flow from a
self-referential baseline); (2) a leak-shaped capture still makes the layer flag a leak — the
capability is intact, not tuned away.
"""
from __future__ import annotations

import numpy as np
import pytest

from ecutune.algorithms.identify import identify
from ecutune.logparse.observe import observations_from_logs
from ecutune.logparse.romraider_csv import LogTable
from ecutune.simulation.mvem import (MEASURED_MAF_BASELINE_20260816 as BASE, EngineParams,
                                     MafBaseline)
from ecutune.simulation.rom_seed import fxt_rom_into_ej20x

HOLDS = ["logging/warm idle.csv", "logging/fast idle.csv", "logging/loaded idle.csv"]


# ------------------------------------------------------------- the bridge transforms correctly

def test_bridge_builds_observations_from_the_real_holds():
    obs = observations_from_logs(HOLDS, BASE, maf_term=True)
    assert len(obs) == 3
    warm, fast, loaded = obs
    assert warm.air_scale == pytest.approx(1.0)                 # warm is the reference
    assert fast.air_scale == pytest.approx(2.12, abs=0.05)     # MEASURED ratio, not an assumed 2.0
    # trims come through the binner's steady filter and match the by-hand read
    assert warm.trim == pytest.approx(-0.0086, abs=0.003)
    assert fast.trim == pytest.approx(-0.0512, abs=0.003)
    # the low-voltage (loaded) hold is the LATENCY probe: no MAF-reading term (idle-up moved its
    # airflow off the no-load baseline)
    assert loaded.voltage < warm.voltage - 0.5
    assert np.isnan(loaded.nominal_maf)
    assert not np.isnan(warm.nominal_maf) and not np.isnan(fast.nominal_maf)
    # provenance flows from the baseline, not hardcoded
    assert all(o.nominal_validated is True for o in obs)   # BASE is a validated capture


# ------------------------------------------------------------- the layer's HONEST verdict

def test_layer_diagnoses_no_leak_and_refuses_to_guess_maf_vs_flow():
    believed, _t, _o, _r = fxt_rom_into_ej20x()
    obs = observations_from_logs(HOLDS, BASE, maf_term=False)   # self-referential default
    est = identify(believed, obs, EngineParams())
    # THE leak is ruled out — the whole point of the fast-idle probe (a leak's trim would shrink
    # with airflow; ours went the other way).
    assert est.fault_id != "vacuum_leak"
    assert "vacuum_leak" not in [k for k, _ in
                                 sorted(est.residuals.items(), key=lambda kv: kv[1])[:2]]
    # with a self-derived baseline, MAF and injector-flow are degenerate → the layer refuses to
    # guess (exactly the E4 masking failure it was built to prevent). NOT a confident table fault.
    assert est.identifiable is False
    assert {"maf_high", "injector_flow_rich"} >= {est.fault_id} or est.fault_id in (
        "maf_high", "injector_flow_rich")


def test_an_independent_baseline_breaks_the_degeneracy():
    """The MAF-reading term is what separates MAF from injector-flow. With an INDEPENDENT baseline
    (maf_term=True) the layer can resolve; the term is real, not decorative."""
    believed, _t, _o, _r = fxt_rom_into_ej20x()
    self_ref = identify(believed, observations_from_logs(HOLDS, BASE, maf_term=False), EngineParams())
    independent = identify(believed, observations_from_logs(HOLDS, BASE, maf_term=True), EngineParams())
    assert self_ref.identifiable is False           # can't separate without the term
    assert independent.identifiable is True          # can, with it


# ------------------------------------------------------------- capability intact: a leak IS caught

def _hold(maf, rpm, volts, trim_pct, n=60):
    """A minimal steady real-format LogTable: trim split arbitrarily across corr/learn."""
    return LogTable(channels={
        "rpm": np.full(n, rpm), "maf_gs": np.full(n, maf), "battery_v": np.full(n, volts),
        "af_correction": np.full(n, trim_pct), "af_learning": np.zeros(n),
        "wideband_afr": np.full(n, 14.7), "tps": np.full(n, 3.0), "knock_retard": np.zeros(n)})


def test_bridge_plus_layer_still_flags_a_real_leak():
    """A vacuum leak's signature: positive trim that HALVES as metered airflow doubles, and is
    voltage-invariant. Fed through the bridge as real-format holds, the layer must call it a leak."""
    believed, _t, _o, _r = fxt_rom_into_ej20x()
    # warm +8% ; fast (2x air) +4% (halved) ; loaded (low V, 1x air) +8% (voltage-invariant)
    holds = [_hold(3.0, 700, 14.0, 8.0), _hold(6.0, 1500, 14.0, 4.0), _hold(3.0, 700, 12.0, 8.0)]
    base = MafBaseline.from_capture([(700, 3.0), (1500, 6.0)], provenance="test")
    obs = observations_from_logs(holds, base, maf_term=True)
    est = identify(believed, obs, EngineParams())
    assert est.fault_id == "vacuum_leak" and est.identifiable


def test_bridge_needs_a_warm_baseline_hold():
    with pytest.raises(ValueError):
        observations_from_logs([HOLDS[0]], BASE)   # a single hold is not identifiable
