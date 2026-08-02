"""Probe-file acceptance suite (2026-08-02, bench-integrity Phase 2).

The probe file is measurement apparatus. When it is wrong, every model is graded against a
faulty ruler and the error is invisible in the results — that is exactly how the showdown
convicted three models for quoting evidence our own snippet code had mangled. These tests are
the ruler's calibration certificate, and they run in CI alongside the scorer's.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import e2                                              # noqa: E402
from harness.config import RetrievalCfg                             # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
V2 = DATA / "e2_probes_v2.jsonl"
CFG = RetrievalCfg()

pytestmark = pytest.mark.skipif(not V2.exists(), reason="probe file v2 not built yet")


def probes() -> list[dict]:
    return [json.loads(l) for l in V2.read_text().splitlines() if l.strip()]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").replace("­", "").strip()


def test_every_probe_is_self_consistent():
    """Answer each probe with its OWN expected value: it must score `exact`. A probe that
    cannot be answered correctly by quoting its own answer key is a broken ruler. This caught
    e2-3694-2, whose "30 000" tripped the scorer's ambiguity rule."""
    bad = [(p["probe_id"],
            e2.classify(p, {"value": f"{p['expected_value']} {p['unit']}",
                            "must_retrieve": False}))
           for p in probes()]
    assert [b for b in bad if b[1] != "exact"] == []


def test_expected_value_bare_also_scores_exact():
    bad = [(p["probe_id"], e2.classify(p, {"value": p["expected_value"],
                                           "must_retrieve": False}))
           for p in probes()]
    assert [b for b in bad if b[1] != "exact"] == []


def test_a_wildly_wrong_answer_is_still_dangerous_on_every_probe():
    """The mirror image: the gate must still fire. If probe-v2 handling had gone soft, this
    would be where it showed."""
    soft = []
    for p in probes():
        m = re.search(r"-?\d+(?:[.,]\d+)?(?![.\d])", p["expected_value"])
        if not m:
            continue
        wrong = str(float(m.group().replace(",", "")) * 37 + 977)
        cls = e2.classify(p, {"value": f"{wrong} {p['unit']}", "must_retrieve": False})
        if cls not in ("dangerous_miss", "unit_mismatch"):
            soft.append((p["probe_id"], cls, wrong))
    assert soft == []


def test_no_probe_carries_a_kind_that_escapes_the_gate_without_justification():
    """`derived` probes are excluded from the fabrication hard gate. Checked against source,
    0 of 69 probes have a value absent from their source doc, so none qualifies — the audit's
    proposal to exclude 8-9 of them would have softened the gate on an unsupported premise."""
    assert [p["probe_id"] for p in probes() if p.get("kind") == "derived"] == []


@pytest.mark.skipif(not CFG.db_path.exists(), reason="corpus DB not present")
def test_every_expected_value_appears_in_its_source_document():
    conn = sqlite3.connect(f"file:{CFG.db_path}?mode=ro", uri=True)
    missing = []
    try:
        for p in probes():
            row = conn.execute("SELECT text FROM ref_fts WHERE rowid=?",
                               (p["source"]["doc_id"],)).fetchone()
            if row is None:
                missing.append((p["probe_id"], "source doc not in ref_fts"))
                continue
            full = norm(row[0])
            for v in re.findall(r"-?\d[\d.,]*", p["expected_value"]):
                if v not in full and v.replace(",", "") not in full.replace(",", ""):
                    missing.append((p["probe_id"], v))
    finally:
        conn.close()
    assert missing == []


def test_v1_is_preserved_untouched():
    """The rerun publishes old numbers beside new; v1 must stay reproducible."""
    assert (DATA / "e2_probes_v1.jsonl").exists()
    assert len(probes()) == len([
        l for l in (DATA / "e2_probes_v1.jsonl").read_text().splitlines() if l.strip()])


def test_the_one_question_edit_is_recorded_with_its_original():
    fixed = [p for p in probes() if "question_v1" in p]
    assert len(fixed) == 1 and fixed[0]["probe_id"] == "e2-3927-1"
    assert fixed[0]["question"] != fixed[0]["question_v1"]
    assert fixed[0]["expected_value"] == "300"      # value unchanged, only the question
