"""Acceptance suite for the deterministic fault estimator.

THE POINT: this validates the entire cross-check design with NO LLM and NO GPU. `build_case_world`
hands us ground truth, so we can ask the layer to recover a seeded fault from nothing but the
observations it will have on a real car, and check it against the answer.

If `identify()` cannot do this reliably here, the cross-check gate is worthless and we find out
for free — before spending a GPU-hour, and before trusting it with a table write.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from ecutune.algorithms.identify import (FAULT_KNOB, MIN_MARGIN_RATIO, FaultEstimate,
                                         Observation, identify, maf_belief_ratio)
from ecutune.evals.cases import FAST_AIR_SCALE, LOW_VOLTAGE, NOMINAL_MAF_IDLE
from ecutune.evals.faults import FAULTS_V2, build_case_world
from ecutune.simulation.mvem import EngineParams, steady_trim

SEEDS = (0, 1, 2, 3, 4)


def observe(believed, truth: EngineParams) -> list[Observation]:
    """The three probe points the real capture protocol specifies, computed from the world.

    Deliberately built the same way `evals/cases._one_case_v2` builds the LLM's prompt, so the
    estimator and the model are looking at the SAME engine — that is the whole basis on which
    their verdicts can be meaningfully compared.
    """
    maf_ratio = float(np.asarray(believed.get("sensor.maf_transfer").values).reshape(-1)[0]) \
        / truth.maf_scaling_true
    pts = ((1.0, truth.v_ref), (FAST_AIR_SCALE, truth.v_ref), (1.0, LOW_VOLTAGE))
    return [Observation(air_scale=a, voltage=v,
                        trim=steady_trim(believed, truth, air_scale=a, voltage=v),
                        maf_reading=NOMINAL_MAF_IDLE * a * maf_ratio,
                        nominal_maf=NOMINAL_MAF_IDLE * a)
            for a, v in pts]


# ---------------------------------------------------------------- the headline capability

@pytest.mark.parametrize("spec", FAULTS_V2, ids=lambda s: s.fault_id)
def test_recovers_every_seeded_fault_across_seeds(spec):
    """All 7 fault types x 5 seeds, recovered from three probe points with no model involved."""
    misses = []
    for seed in SEEDS:
        believed, truth, mag = build_case_world(spec, np.random.default_rng(seed))
        est = identify(believed, observe(believed, truth))
        if not (est.identifiable and est.fault_id == spec.fault_id):
            misses.append((seed, est.fault_id, round(est.margin, 2), est.reason[:60]))
    assert misses == [], f"{spec.fault_id}: {misses}"


@pytest.mark.parametrize("spec", [s for s in FAULTS_V2
                                  if s.fault_id not in ("healthy", "vacuum_leak")],
                         ids=lambda s: s.fault_id)
def test_fitted_magnitude_is_close_to_the_seeded_one(spec):
    """Identifying the right knob is necessary but not sufficient — the layer also has to get
    the SIZE roughly right, or its correction will be wrong even when its diagnosis is right."""
    for seed in SEEDS:
        believed, truth, mag = build_case_world(spec, np.random.default_rng(seed))
        est = identify(believed, observe(believed, truth))
        seeded_ratio = 1.0 + mag / 100.0          # build_case_world's magnitude_pct
        assert abs(est.magnitude - seeded_ratio) < 0.02, \
            f"{spec.fault_id} seed={seed}: fitted {est.magnitude:.4f} vs seeded {seeded_ratio:.4f}"


def test_vacuum_leak_magnitude_is_close():
    spec = next(s for s in FAULTS_V2 if s.fault_id == "vacuum_leak")
    for seed in SEEDS:
        believed, truth, _ = build_case_world(spec, np.random.default_rng(seed))
        est = identify(believed, observe(believed, truth))
        assert abs(est.magnitude - truth.leak_air_g) < 0.01, \
            f"seed={seed}: fitted leak {est.magnitude:.4f} vs true {truth.leak_air_g:.4f}"


# ---------------------------------------------------------------- the refusal paths

def test_a_single_probe_point_is_NOT_identifiable():
    """The whole premise: one operating point cannot separate three beliefs. If this ever
    passes, the degeneracy argument is wrong and the design needs revisiting."""
    spec = next(s for s in FAULTS_V2 if s.fault_id == "injector_latency_lean")
    believed, truth, _ = build_case_world(spec, np.random.default_rng(0))
    one = [observe(believed, truth)[0]]
    est = identify(believed, one)
    assert est.identifiable is False
    assert "probe points" in est.reason


def test_leak_and_latency_are_degenerate_WITHOUT_the_voltage_probe():
    """Both shrink with airflow; only voltage separates them. Dropping the low-voltage point
    must collapse the margin — this is the test that proves the third probe earns its place."""
    spec = next(s for s in FAULTS_V2 if s.fault_id == "vacuum_leak")
    believed, truth, _ = build_case_world(spec, np.random.default_rng(0))
    obs = observe(believed, truth)
    no_voltage = [o for o in obs if o.voltage == truth.v_ref]      # idle + fast idle only
    est_2pt = identify(believed, no_voltage)
    est_3pt = identify(believed, obs)
    assert est_3pt.identifiable, "three points must identify the leak"
    assert est_3pt.margin > est_2pt.margin, (
        f"the voltage probe must increase separation: 2pt margin {est_2pt.margin:.2f} "
        f"vs 3pt {est_3pt.margin:.2f}")


def test_two_simultaneous_faults_are_rejected_not_guessed():
    """No single-fault hypothesis fits -> escalate. The system has never had this capability;
    previously it would have confidently corrected one of them."""
    believed, truth, _ = build_case_world(
        next(s for s in FAULTS_V2 if s.fault_id == "injector_flow_lean"),
        np.random.default_rng(0))
    both = replace(truth, leak_air_g=0.05)         # flow belief wrong AND a vacuum leak
    est = identify(believed, observe(believed, both))
    assert est.identifiable is False
    assert "no single-fault hypothesis fits" in est.reason


def test_healthy_engine_is_identified_as_healthy():
    spec = next(s for s in FAULTS_V2 if s.fault_id == "healthy")
    believed, truth, _ = build_case_world(spec, np.random.default_rng(0))
    est = identify(believed, observe(believed, truth))
    assert est.fault_id == "healthy" and est.identifiable


# ---------------------------------------------------------------- contracts / plumbing

def test_the_direct_maf_observation_is_used():
    """maf_reading/nominal_maf reads MAF belief error straight off the log, no trim inference.
    The layer already receives maf_gs (it is the grid x-axis) and never used it."""
    spec = next(s for s in FAULTS_V2 if s.fault_id == "maf_low")
    believed, truth, _ = build_case_world(spec, np.random.default_rng(0))
    obs = observe(believed, truth)
    ratio = maf_belief_ratio(obs)
    expected = float(np.asarray(believed.get("sensor.maf_transfer").values).reshape(-1)[0]) \
        / truth.maf_scaling_true
    assert ratio is not None and abs(ratio - expected) < 1e-6


def test_estimator_knob_map_matches_the_e4_action_map():
    """identify.FAULT_KNOB mirrors ml/eval/harness/e4_map.DIAGNOSIS_KNOB. If they drift, the
    cross-check compares two different notions of 'which table' and silently misfires."""
    import importlib.util
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "ml/eval/harness/e4_map.py"
    spec = importlib.util.spec_from_file_location("e4_map", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert FAULT_KNOB == mod.DIAGNOSIS_KNOB


def test_identify_never_mutates_the_believed_tables():
    """Copy semantics, same invariant the write path enforces."""
    spec = next(s for s in FAULTS_V2 if s.fault_id == "injector_flow_lean")
    believed, truth, _ = build_case_world(spec, np.random.default_rng(0))
    before = {k: float(np.asarray(v.values).reshape(-1)[0]) for k, v in believed.tables.items()}
    identify(believed, observe(believed, truth))
    after = {k: float(np.asarray(v.values).reshape(-1)[0]) for k, v in believed.tables.items()}
    assert before == after
