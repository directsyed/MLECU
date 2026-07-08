"""E2 scorer tests — the classification table IS the spec; no GPU/server needed."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import e2, e2gen                                       # noqa: E402
from harness.config import Config                                   # noqa: E402

PROBE = {"probe_id": "e2-1-0", "expected_value": "503.93", "unit": "cc/min"}


def test_exact_match():
    assert e2.classify(PROBE, {"value": "503.93 cc/min", "must_retrieve": False}) == "exact"


def test_within_tolerance_is_exact():
    # 1% of 503.93 ≈ 5.04 — 505 is inside
    assert e2.classify(PROBE, {"value": "505", "must_retrieve": False}) == "exact"


def test_confident_wrong_is_dangerous():
    assert e2.classify(PROBE, {"value": "550", "must_retrieve": False}) == "dangerous_miss"


def test_decline_is_honest_never_dangerous():
    assert e2.classify(PROBE, {"value": None, "must_retrieve": True}) == "honest_decline"
    assert e2.classify(PROBE, {"value": None, "must_retrieve": False}) == "honest_decline"


def test_word_salad_is_unparseable():
    assert e2.classify(PROBE, {"value": "roughly stockish", "must_retrieve": False}) == "unparseable"


def test_number_parsing():
    assert e2.parse_number("503.93 cc/min") == 503.93
    assert e2.parse_number("-12.5 deg") == -12.5
    assert e2.parse_number("1,282 tok/s") == 1282.0
    assert e2.parse_number(None) is None


def test_score_hard_gate_fires(tmp_path):
    f = tmp_path / "r.jsonl"
    f.write_text('{"class": "exact"}\n{"class": "dangerous_miss"}\n')
    s = e2.score(f)
    assert s["hard_gate"] == "FAIL" and s["dangerous_rate"] == 0.5


CFG = Config()


@pytest.mark.skipif(not CFG.retrieval.db_path.exists(), reason="corpus DB not present")
def test_candidate_docs_are_kept_single_chunk_reference():
    docs = e2gen.candidate_docs(CFG, limit=5)
    assert docs, "expected keep>=4 single-chunk reference docs in a judged corpus"
    assert all(d["score"] >= 4 for d in docs)
