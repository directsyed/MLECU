"""Stage-B judge state layer: mark_judged atomicity, failed-parking, labels, migration."""
from __future__ import annotations

import sqlite3

import pytest

from corpus_pipeline.core.models import Document
from corpus_pipeline.core.state import State


@pytest.fixture()
def state(tmp_path):
    s = State(tmp_path / "t.sqlite")
    yield s
    s.close()


def _doc(i: int, tier: str = "community") -> Document:
    return Document(source="forum_x", source_id=f"t{i}", title=f"doc {i}",
                    text="MAF scaling was 7% off at idle, trims +12%.",
                    tier=tier, gate_status="kept")


def test_mark_judged_rolls_up_and_is_atomic(state):
    doc_id, _ = state.upsert_document(_doc(1))
    chunks = [
        {"chunk_index": 0, "n_chunks": 2, "score": 4, "rationale": "solid numbers",
         "pairs_json": "[]", "grounding_json": "[]", "prompt_tokens": 900, "completion_tokens": 120},
        {"chunk_index": 1, "n_chunks": 2, "score": 3, "rationale": "opinionated tail",
         "pairs_json": "[]", "grounding_json": "[]", "prompt_tokens": 700, "completion_tokens": 90},
    ]
    state.mark_judged(doc_id, score=3, judge_model="qwen-test", rubric_version="rubric-r1",
                      chunks=chunks)
    row = state.conn.execute("SELECT * FROM document WHERE id=?", (doc_id,)).fetchone()
    assert row["judgment_status"] == "judged"
    assert row["judge_score"] == 3
    assert row["rubric_version"] == "rubric-r1"
    js = state.conn.execute("SELECT * FROM judgment WHERE doc_id=? ORDER BY chunk_index",
                            (doc_id,)).fetchall()
    assert [j["score"] for j in js] == [4, 3]
    # re-judge same rubric overwrites, not duplicates
    state.mark_judged(doc_id, score=4, judge_model="qwen-test", rubric_version="rubric-r1",
                      chunks=[{**chunks[0], "score": 5}, chunks[1]])
    assert state.conn.execute("SELECT COUNT(*) FROM judgment WHERE doc_id=?",
                              (doc_id,)).fetchone()[0] == 2
    # a NEW rubric version keeps both generations
    state.mark_judged(doc_id, score=4, judge_model="qwen-test", rubric_version="rubric-r2",
                      chunks=chunks)
    assert state.conn.execute("SELECT COUNT(*) FROM judgment WHERE doc_id=?",
                              (doc_id,)).fetchone()[0] == 4


def test_pending_excludes_judged_and_failed(state):
    ids = [state.upsert_document(_doc(i))[0] for i in range(3)]
    state.mark_judged(ids[0], score=5, judge_model="m", rubric_version="r",
                      chunks=[{"score": 5}])
    state.mark_judge_failed(ids[1], "timeout")
    pending = [r["id"] for r in state.pending_for_judge()]
    assert pending == [ids[2]]
    assert state.reset_failed_judgments() == 1
    pending = [r["id"] for r in state.pending_for_judge()]
    assert sorted(pending) == sorted([ids[1], ids[2]])


def test_content_change_resets_judgment(state):
    doc_id, _ = state.upsert_document(_doc(1))
    state.mark_judged(doc_id, score=5, judge_model="m", rubric_version="r",
                      chunks=[{"score": 5}])
    d = _doc(1)
    d.text = "edited content"
    d.content_hash = ""
    d.__post_init__()
    state.upsert_document(d)
    row = state.conn.execute("SELECT judgment_status FROM document WHERE id=?",
                             (doc_id,)).fetchone()
    assert row["judgment_status"] == "pending"


def test_labels_upsert_by_doc_set_rater(state):
    doc_id, _ = state.upsert_document(_doc(1))
    state.add_label(doc_id, score=4, label_set="calibration-100", rater="claude", notes="good")
    state.add_label(doc_id, score=3, label_set="calibration-100", rater="syed")
    state.add_label(doc_id, score=4, label_set="calibration-100", rater="syed")  # revises
    rows = state.labels("calibration-100")
    assert len(rows) == 2
    assert {(r["rater"], r["score"]) for r in rows} == {("claude", 4), ("syed", 4)}
    assert [r["score"] for r in state.labels("calibration-100", rater="syed")] == [4]


def test_reference_helpers(state):
    state.upsert_document(_doc(1, tier="reference"))
    state.upsert_document(_doc(2, tier="reference"))
    state.upsert_document(_doc(3, tier="community"))
    assert state.reference_kept_count() == 2
    assert {r["title"] for r in state.reference_kept_docs()} == {"doc 1", "doc 2"}


def test_migration_idempotent(tmp_path):
    p = tmp_path / "m.sqlite"
    for _ in range(2):                     # open twice — second open must be a no-op
        s = State(p)
        s.close()
    cols = [r[1] for r in sqlite3.connect(p).execute("PRAGMA table_info(document)")]
    assert cols.count("judge_model") == 1
    assert cols.count("rubric_version") == 1
