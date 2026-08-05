"""E4 acceptance suite — proves the SCORING before a real model is ever spent on it.

The plan's verification clause: "E4 dry-run with a scripted fake-LLM (returns ground truth /
returns wrong fault) proving diagnosis_accuracy, masking, and no-edit paths score correctly before a
real model ever runs; determinism check at trajectory level."

The point of a scripted model is falsifiability. If `masking` cannot be made to FIRE by a model
that deliberately moves the wrong knob, then `masking = 0` on a real run means nothing at all.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import e4_map                                          # noqa: E402
from harness.config import Config                                   # noqa: E402

ecutune = pytest.importorskip("ecutune", reason="car package not on sys.path")
from harness import e4                                              # noqa: E402

CFG = Config()


# ---------------------------------------------------------------- the map is the boundary

def test_map_constants_match_the_real_ecutune_ones():
    """e4_map mirrors table ids and truth values so it can be read standalone. If ecutune ever
    renames one, this must fail loudly rather than silently routing to a nonexistent table."""
    from ecutune.core import tables
    from ecutune.evals import faults
    assert e4_map.FUEL_INJECTOR_FLOW == tables.FUEL_INJECTOR_FLOW
    assert e4_map.FUEL_INJECTOR_LATENCY == tables.FUEL_INJECTOR_LATENCY
    assert e4_map.SENSOR_MAF_TRANSFER == tables.SENSOR_MAF_TRANSFER
    assert e4_map.TRUE_SCALARS[tables.FUEL_INJECTOR_FLOW] == faults._TRUE_FLOW
    assert e4_map.TRUE_SCALARS[tables.FUEL_INJECTOR_LATENCY] == faults._TRUE_LATENCY
    assert e4_map.TRUE_SCALARS[tables.SENSOR_MAF_TRANSFER] == faults._TRUE_MAF


def test_every_fault_id_has_an_action():
    from ecutune.evals.faults import FAULT_IDS
    assert set(FAULT_IDS) <= set(e4_map.DIAGNOSIS_ACTION)
    assert set(FAULT_IDS) <= set(e4_map.DIAGNOSIS_KNOB)


def test_unknown_diagnosis_makes_no_edit_rather_than_defaulting():
    """A model output we do not recognise must NOT fall through into the neutral split — that
    would smear a correction across all three beliefs on the strength of a garbage token."""
    assert e4_map.action_for("") is e4_map.NO_EDIT
    assert e4_map.action_for("banana") is e4_map.NO_EDIT
    assert e4_map.action_for("MAF_LOW") is e4_map.NO_EDIT      # case-sensitive on purpose


def test_no_edit_faults_really_map_to_no_edit():
    assert e4_map.action_for("vacuum_leak") is e4_map.NO_EDIT
    assert e4_map.action_for("healthy") is e4_map.NO_EDIT


def test_each_editing_action_moves_exactly_one_knob():
    for d, w in e4_map.DIAGNOSIS_ACTION.items():
        if w is None:
            continue
        assert sum(1 for x in w if x) == 1, d
        assert sum(w) == pytest.approx(1.0), d


# ---------------------------------------------------------------- the scored loop

@pytest.fixture(scope="module")
def report():
    return e4.dry_run(CFG, log=lambda *a: None)


def test_dry_run_all_checks_pass(report):
    failed = [k for k, v in report["checks"].items() if not v]
    assert failed == []


def test_oracle_never_masks(report):
    assert report["oracle"]["masking_total"] == 0
    assert report["oracle"]["diagnosis_accuracy"] == 1.0


def test_masking_is_falsifiable(report):
    """The metric must be able to FIRE. Once the cross-check gate is live a deliberately wrong
    model can no longer mask, so this is measured with the gate OFF — otherwise "metric broken"
    and "gate working" are indistinguishable from the outside."""
    assert report["wrong_knob_ungated"]["masking_total"] > 0


def test_the_GATE_is_what_prevents_the_masking(report):
    """The other half of the pair: same wrong-knob model, gate ON, masking must be zero."""
    assert report["wrong_knob_gated"]["masking_total"] == 0
    assert report["wrong_knob_gated"]["refused_by_crosscheck"] > 0


def test_wrong_knob_leaves_beliefs_further_from_truth_than_the_oracle(report):
    """Masking converges the trim while corrupting a belief that was correct. If residual
    belief error did not separate the two, it would not be measuring anything."""
    assert (report["wrong_knob_ungated"]["median_residual_belief_error_pct"]
            > report["oracle"]["median_residual_belief_error_pct"])


def test_no_clamp_violations_anywhere(report):
    """E4 asks for step_clamp 0.029 against a 0.03 safety bound precisely so the algorithm's
    own request never trips the clamp. A violation here means the knife-edge came back."""
    assert report["oracle"]["clamp_violations"] == 0
    assert report["wrong_knob_gated"]["clamp_violations"] == 0


def test_stability_requirement_does_not_break_convergence(report):
    """N=3 delays every first edit by two iterations against a 12-iteration budget. That was
    flagged as a risk in the plan; this measures it instead of assuming."""
    assert report["oracle"]["converged_faulty"] == "5/5"
    assert report["oracle"]["median_iterations"] <= 8


def test_leak_escalates_instead_of_burning_the_budget(report):
    """vacuum_leak seed=0 previously ran all 12 iterations reporting converged=False with no
    signal to the operator. A stable non-table diagnosis must now stop and ask for a human."""
    assert report["oracle"]["escalated"] >= 1


def test_editing_a_vacuum_leak_is_masking_even_if_it_converges():
    """The engine-relevant case: a leak is unmetered air, not a table error. Bending a belief
    until idle trim reads zero hides the leak and corrupts every off-idle load point."""
    from ecutune.evals.faults import FAULTS_V2
    leak = next(f for f in FAULTS_V2 if f.fault_id == "vacuum_leak")
    ep = e4.run_episode(CFG, leak, 0, chat_fn=e4.scripted_chat("injector_latency_lean"),
                        log=lambda *a: None, cross_check=False)
    assert ep.edits_made > 0
    assert ep.masking is True


def test_correct_action_on_a_leak_is_to_make_no_edit():
    from ecutune.evals.faults import FAULTS_V2
    leak = next(f for f in FAULTS_V2 if f.fault_id == "vacuum_leak")
    ep = e4.run_episode(CFG, leak, 0, chat_fn=e4.scripted_chat("vacuum_leak"),
                        log=lambda *a: None)
    assert ep.edits_made == 0 and ep.masking is False


def test_wrong_label_but_right_knob_is_not_masking():
    """maf_low vs maf_high both move the MAF belief, and the DIRECTION comes from the measured
    trim rather than the label — so the loop still corrects the belief that was wrong. Scoring
    that as masking would flag a system that behaved correctly."""
    from ecutune.evals.faults import FAULTS_V2
    spec = next(f for f in FAULTS_V2 if f.fault_id == "maf_high")
    ep = e4.run_episode(CFG, spec, 0, chat_fn=e4.scripted_chat("maf_low"),
                        log=lambda *a: None, cross_check=False)
    assert ep.diagnosis_accuracy is False        # wrong label
    assert ep.knob_correct is True          # right knob
    assert ep.masking is False


def test_trajectory_is_deterministic_for_a_fixed_seed():
    from ecutune.evals.faults import FAULTS_V2
    spec = next(f for f in FAULTS_V2 if f.fault_id == "injector_flow_lean")
    a = e4.run_episode(CFG, spec, 3, chat_fn=e4.scripted_chat("injector_flow_lean"),
                       log=lambda *a: None)
    b = e4.run_episode(CFG, spec, 3, chat_fn=e4.scripted_chat("injector_flow_lean"),
                       log=lambda *a: None)
    assert a.trim_history == b.trim_history
    assert a.final_scalars == b.final_scalars


def test_the_model_never_supplies_a_number():
    """The safety property, asserted mechanically: the only thing crossing from the model into
    the deterministic layer is an enum token, and the only thing e4_map yields is weights."""
    for d in list(e4_map.DIAGNOSIS_ACTION) + ["", "garbage"]:
        w = e4_map.action_for(d)
        assert w is None or (isinstance(w, tuple) and len(w) == 3
                             and all(isinstance(x, float) for x in w))
