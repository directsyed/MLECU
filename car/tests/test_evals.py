"""Sim-generated eval — generation determinism, fault signatures, scoring, baseline bracketing."""
from __future__ import annotations

import json

from ecutune.evals import generate_cases, score
from ecutune.evals.scoring import run_baseline


def _by_fault(cases):
    out: dict[str, list] = {}
    for c in cases:
        out.setdefault(c["fault"], []).append(c)
    return out


def test_generation_deterministic():
    a = generate_cases(3, seed=7)
    b = generate_cases(3, seed=7)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert len(a) == 3 * 7                                  # 7 faults


def test_healthy_cases_have_small_trims():
    for c in _by_fault(generate_cases(5, seed=1))["healthy"]:
        assert abs(c["features"]["trim_idle_pct"]) < 1.0


def test_fault_signatures_separate_constant_vs_shrinking():
    by = _by_fault(generate_cases(6, seed=2))
    for c in by["injector_flow_lean"]:                      # constant-fraction: ratio ~ 1
        f = c["features"]
        assert f["trim_fast_pct"] / f["trim_idle_pct"] > 0.85
    for c in by["vacuum_leak"]:                             # constant-absolute: ratio ~ 0.5
        f = c["features"]
        assert f["trim_fast_pct"] / f["trim_idle_pct"] < 0.65
    for c in by["maf_low"]:                                 # reading signature
        f = c["features"]
        assert f["maf_gs_idle"] / f["nominal_maf_idle"] < 0.95


def test_scoring_math():
    cases = [{"case_id": "a", "fault": "x", "acceptable": ["x", "y"], "choices": ["x", "y"]},
             {"case_id": "b", "fault": "y", "acceptable": ["y"], "choices": ["x", "y"]}]
    r = score(cases, {"a": "y", "b": "y"})                  # a: acceptable-only; b: top1
    assert r.top1 == 0.5
    assert r.acceptable == 1.0


def test_baselines_bracket_the_eval():
    cases = generate_cases(10, seed=0)
    rules = run_baseline(cases, "rules")
    rand = run_baseline(cases, "random")
    assert rules.acceptable >= 0.95        # the two-point signatures are separable by design
    assert rules.top1 >= 0.80              # latency cases scored as leak cost only top1
    assert rand.acceptable < 0.5           # chance-level floor
    assert rules.acceptable > rand.acceptable + 0.3
