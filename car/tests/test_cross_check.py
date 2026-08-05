"""The cross-check gate and the disagreement report.

These are the tests that decide whether "the LLM points, it does not command" is enforced by
code or merely written down. The gate must abort on every disagreement shape, stay inert when
it has no second opinion to offer, and never quietly let an edit through.
"""
from __future__ import annotations

import numpy as np
import pytest

from ecutune.algorithms.identify import FaultEstimate, identify
from ecutune.core.config import load_config
from ecutune.core.models import CellEdit, ClampContext, Proposal, Table, TableSet
from ecutune.core.tables import (FUEL_INJECTOR_FLOW, FUEL_INJECTOR_LATENCY,
                                 SENSOR_MAF_TRANSFER)
from ecutune.evals.faults import FAULTS_V2, build_case_world
from ecutune.safety import apply_proposal
from ecutune.safety.report import disagreement_report, to_markdown
from ecutune.simulation.harness import collect_observations
from ecutune.simulation.mvem import OperatingPoint

SAFETY = load_config().safety


def _tables(flow=500.0, lat=1.0, maf=1.0) -> TableSet:
    return TableSet({
        FUEL_INJECTOR_FLOW: Table(FUEL_INJECTOR_FLOW, "scalar", np.array(flow), units="cc/min"),
        FUEL_INJECTOR_LATENCY: Table(FUEL_INJECTOR_LATENCY, "scalar", np.array(lat), units="ms"),
        SENSOR_MAF_TRANSFER: Table(SENSOR_MAF_TRANSFER, "scalar", np.array(maf), units="scale"),
    })


def _prop(table_id: str, new: float) -> Proposal:
    return Proposal("p", "idle_stage2", (CellEdit(table_id, 0, 0, new),), "fuel", "llm:test")


def _est(fault_id: str, identifiable: bool = True) -> FaultEstimate:
    return FaultEstimate(fault_id, 1.1, {"a": 1e-6, "b": 1e-3}, 1000.0, identifiable, "", 3)


# ---------------------------------------------------------------- the gate

def test_agreement_lets_the_edit_through():
    ts = _tables()
    ctx = ClampContext(ts, SAFETY, fault_estimate=_est("injector_flow_lean"))
    new_ts, res = apply_proposal(ts, _prop(FUEL_INJECTOR_FLOW, 505.0), ctx)
    assert res.ok and float(new_ts.tables[FUEL_INJECTOR_FLOW].values) == 505.0


def test_knob_mismatch_aborts_and_writes_nothing():
    """The masking shape: the model says MAF, the layer says injector flow."""
    ts = _tables()
    ctx = ClampContext(ts, SAFETY, fault_estimate=_est("injector_flow_lean"))
    new_ts, res = apply_proposal(ts, _prop(SENSOR_MAF_TRANSFER, 1.02), ctx)
    assert res.ok is False
    assert res.aborted_by == "diagnosis_agreement:knob_mismatch"
    assert float(new_ts.tables[SENSOR_MAF_TRANSFER].values) == 1.0     # untouched


def test_layer_saying_NO_TABLE_EDIT_aborts_any_edit():
    """The engine-relevant one: a vacuum leak is not in any table, so ANY edit masks it."""
    ts = _tables()
    ctx = ClampContext(ts, SAFETY, fault_estimate=_est("vacuum_leak"))
    _, res = apply_proposal(ts, _prop(FUEL_INJECTOR_LATENCY, 1.029), ctx)
    assert res.ok is False
    assert res.aborted_by == "diagnosis_agreement:layer_says_no_table_edit"


def test_unidentifiable_aborts():
    ts = _tables()
    ctx = ClampContext(ts, SAFETY, fault_estimate=_est("injector_flow_lean", identifiable=False))
    _, res = apply_proposal(ts, _prop(FUEL_INJECTOR_FLOW, 505.0), ctx)
    assert res.ok is False
    assert res.aborted_by == "diagnosis_agreement:not_identifiable"


def test_gate_is_INERT_without_an_estimate():
    """It must not manufacture a second opinion it does not have — otherwise every legacy
    single-point path would abort. Absence is visible in the audit trail, not treated as
    agreement."""
    ts = _tables()
    new_ts, res = apply_proposal(ts, _prop(FUEL_INJECTOR_FLOW, 505.0), ClampContext(ts, SAFETY))
    assert res.ok and float(new_ts.tables[FUEL_INJECTOR_FLOW].values) == 505.0


def test_wrong_label_but_same_knob_is_NOT_a_disagreement():
    """maf_low vs maf_high move the same table; direction comes from the measured trim."""
    ts = _tables()
    ctx = ClampContext(ts, SAFETY, fault_estimate=_est("maf_high"))
    _, res = apply_proposal(ts, _prop(SENSOR_MAF_TRANSFER, 1.02), ctx)
    assert res.ok is True


# ---------------------------------------------------------------- the envelope

def test_belief_envelope_bounds_distance_from_the_stock_rom():
    """clamp_ve_rate_limit bounds velocity; this bounds displacement. 12 iterations at 3% each
    compounds to 43% without it."""
    ts = _tables(flow=500.0)
    base = _tables(flow=500.0)
    ctx = ClampContext(ts, SAFETY, baseline_tables=base)
    # ask for +40%; rate limit allows 3%/iteration, envelope allows 25% from baseline
    new_ts, res = apply_proposal(ts, _prop(FUEL_INJECTOR_FLOW, 700.0), ctx)
    assert res.ok
    assert float(new_ts.tables[FUEL_INJECTOR_FLOW].values) <= 500.0 * 1.25 + 1e-9


def test_envelope_records_a_violation_when_it_bites():
    ts = _tables(flow=620.0)          # already 24% above stock
    base = _tables(flow=500.0)
    ctx = ClampContext(ts, SAFETY, baseline_tables=base)
    _, res = apply_proposal(ts, _prop(FUEL_INJECTOR_FLOW, 638.0), ctx)   # +3%, but past +25%
    assert any(v.clamp == "belief_envelope" for v in res.violations)


def test_envelope_is_inert_without_a_baseline():
    ts = _tables()
    new_ts, res = apply_proposal(ts, _prop(FUEL_INJECTOR_FLOW, 505.0), ClampContext(ts, SAFETY))
    assert res.ok and float(new_ts.tables[FUEL_INJECTOR_FLOW].values) == 505.0


# ---------------------------------------------------------------- the report

def test_report_contains_BOTH_sides():
    """Syed's requirement: the human gets the model's evidence AND the layer's computations,
    not a verdict."""
    spec = next(s for s in FAULTS_V2 if s.fault_id == "vacuum_leak")
    believed, truth, _ = build_case_world(spec, np.random.default_rng(1))
    obs = collect_observations(believed, truth, OperatingPoint(), np.random.default_rng(1))
    est = identify(believed, obs)
    ctx = ClampContext(believed, SAFETY, fault_estimate=est)
    prop = _prop(FUEL_INJECTOR_LATENCY, 1.029)
    _, res = apply_proposal(believed, prop, ctx)
    assert res.ok is False

    llm_ctx = {"diagnosis": "injector_latency_lean", "model": "qwen27b-dense",
               "diagnosis_history": ["vacuum_leak"] * 5 + ["injector_latency_lean"],
               "prompt": "…datalog summary…", "finish_reason": "stop",
               "retrieved_doc_ids": [1309, 5490],
               "retrieved_excerpts": [{"ref_doc_id": 1309, "title": "T", "snippet": "…"}]}
    rep = disagreement_report(prop, ctx, res, llm_ctx)

    # deterministic side: the WHOLE ranking, not just the winner
    assert rep["deterministic_side"]["verdict"] == "vacuum_leak"
    assert len(rep["deterministic_side"]["hypothesis_ranking"]) >= 5
    assert rep["deterministic_side"]["n_observations"] == 3
    # llm side: its evidence survives into the report
    assert rep["llm_side"]["diagnosis"] == "injector_latency_lean"
    assert rep["llm_side"]["retrieved_doc_ids"] == [1309, 5490]

    md = to_markdown(rep)
    for needle in ("The two conclusions", "vacuum_leak", "injector_latency_lean",
                   "every hypothesis, ranked", "Nothing has been written"):
        assert needle in md, needle


def test_report_shouts_when_the_llm_side_is_missing():
    """A report that silently omits the model's reasoning would let a refusal look one-sided."""
    ts = _tables()
    ctx = ClampContext(ts, SAFETY, fault_estimate=_est("vacuum_leak"))
    prop = _prop(FUEL_INJECTOR_FLOW, 505.0)
    _, res = apply_proposal(ts, prop, ctx)
    rep = disagreement_report(prop, ctx, res)
    assert "WARNING" in rep["llm_side"]
    assert "not supplied" in to_markdown(rep)
