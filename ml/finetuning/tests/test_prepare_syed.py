"""Acceptance tests for Syed's prepare.py build (QLoRA night, 2026-07-22).
Green here = the formatter is correct; then run prepare.py for real.

Run: car/.venv/bin/python -m pytest ml/finetuning/tests/test_prepare_syed.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "prepare", Path(__file__).resolve().parents[1] / "prepare.py")
prepare = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = prepare
_spec.loader.exec_module(prepare)


def _pair(symptoms="idle hunts 600-900rpm", diagnosis="idle re-arm oscillation",
          change="raise ramp time 0.5s", outcome="idle steady at 750rpm"):
    return {"symptoms": symptoms, "diagnosis": diagnosis,
            "change": change, "outcome": outcome}


# ---- TODO #1: format_assistant ----

def test_assistant_structure_and_order():
    out = prepare.format_assistant(_pair())
    lines = out.split("\n")
    assert lines[0] == "Diagnosis: idle re-arm oscillation"
    assert lines[1] == "Change: raise ramp time 0.5s"
    assert lines[2] == "Expected result: idle steady at 750rpm"


def test_assistant_strips_field_whitespace():
    out = prepare.format_assistant(_pair(diagnosis="  padded  ", outcome="ok\n"))
    assert "Diagnosis: padded" in out
    assert out.endswith("Expected result: ok")


# ---- TODO #2: to_example (the structural gate) ----

def test_gate_blank_symptoms_returns_none():
    assert prepare.to_example(_pair(symptoms="")) is None
    assert prepare.to_example(_pair(symptoms="   \n ")) is None


def test_gate_missing_symptoms_key_returns_none():
    p = _pair()
    del p["symptoms"]
    assert prepare.to_example(p) is None


def test_example_shape_and_system_match():
    ex = prepare.to_example(_pair(symptoms="  trims +8% at idle  "))
    roles = [m["role"] for m in ex["messages"]]
    assert roles == ["system", "user", "assistant"]
    assert ex["messages"][0]["content"] == prepare.SYSTEM
    assert ex["messages"][1]["content"] == "trims +8% at idle"   # stripped
    assert ex["messages"][2]["content"] == prepare.format_assistant(_pair())


# ---- TODO #3: stratified_split ----

def _items(n_per, strata=("syn:idle", "syn:maf", "organic")):
    out = []
    for s in strata:
        out += [(s, {"id": f"{s}-{i}"}) for i in range(n_per)]
    return out


def test_split_sizes_per_stratum():
    train, val = prepare.stratified_split(_items(20), val_frac=0.10, seed=0)
    assert len(val) == 6 and len(train) == 54          # 2 of each 20, three strata
    for s in ("syn:idle", "syn:maf", "organic"):
        assert sum(1 for e in val if e["id"].startswith(s)) == 2


def test_split_loses_and_duplicates_nothing():
    items = _items(17)                                  # non-round sizes too
    train, val = prepare.stratified_split(items, val_frac=0.10, seed=0)
    ids = sorted(e["id"] for e in train + val)
    assert ids == sorted(e["id"] for _, e in items)


def test_split_deterministic_same_seed():
    a = prepare.stratified_split(_items(20), val_frac=0.10, seed=7)
    b = prepare.stratified_split(_items(20), val_frac=0.10, seed=7)
    assert a == b


def test_split_changes_with_seed():
    a = prepare.stratified_split(_items(50), val_frac=0.10, seed=1)
    b = prepare.stratified_split(_items(50), val_frac=0.10, seed=2)
    assert [e["id"] for e in a[1]] != [e["id"] for e in b[1]]


def test_tiny_stratum_rounds_to_zero_val():
    train, val = prepare.stratified_split(_items(2), val_frac=0.10, seed=0)
    assert len(val) == 0 and len(train) == 6            # round(0.2) == 0 per stratum


def test_gate_blank_diagnosis_returns_none():
    # gate extension (Claude 2026-07-22): all four fields required, not just symptoms
    assert prepare.to_example(_pair(diagnosis="")) is None
    assert prepare.to_example(_pair(diagnosis="  \n")) is None
