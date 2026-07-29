"""Ledger transition + validation tests. The validation predicate is the safety-critical
part: a false 'done' silently poisons the showdown matrix."""
import json
import sqlite3

import pytest

from bench import ledger


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "bench.sqlite"
    monkeypatch.setattr(ledger, "DB_PATH", db)
    ledger.init(db)
    yield db


def _add(label, seq=0, phase="test", **kw):
    return ledger.add_unit(phase=phase, seq=seq, label=label, kind="shell",
                           argv_json=json.dumps(["true"]), **kw)


# ---- transitions ----

def test_claim_takes_lowest_seq_and_marks_running():
    _add("b", seq=2); _add("a", seq=1)
    u = ledger.claim_next()
    assert u["label"] == "a" and u["state"] == "running" and u["attempts"] == 1


def test_claim_returns_none_when_drained():
    _add("only")
    ledger.claim_next()
    assert ledger.claim_next() is None


def test_done_and_failed_are_terminal_for_claiming():
    _add("x"); u = ledger.claim_next()
    ledger.mark_done(u["id"], out_path="/tmp/x", n_rows_got=147)
    assert ledger.claim_next() is None
    with ledger.connect(ledger.DB_PATH) as c:
        row = c.execute("SELECT * FROM unit WHERE id=?", (u["id"],)).fetchone()
    assert row["state"] == "done" and row["n_rows_got"] == 147 and row["ended_at"]


def test_reset_running_recovers_from_driver_death():
    _add("x"); ledger.claim_next()
    assert ledger.reset_running() == 1
    assert ledger.claim_next()["label"] == "x"      # claimable again


def test_requeue_after_failure():
    _add("x"); u = ledger.claim_next()
    ledger.mark_failed(u["id"], "oom")
    assert ledger.claim_next() is None
    ledger.requeue(u["id"], "retry with more offload")
    assert ledger.claim_next()["label"] == "x"


def test_skip_model_clears_pending_and_failed_only():
    _add("m1", seq=1, model_key="M"); _add("m2", seq=2, model_key="M")
    u = ledger.claim_next(); ledger.mark_done(u["id"])
    assert ledger.skip_model("M", "arch unsupported") == 1     # only the pending one
    assert ledger.claim_next() is None


def test_add_unit_is_idempotent_on_label():
    _add("dup"); _add("dup")
    with ledger.connect(ledger.DB_PATH) as c:
        assert c.execute("SELECT COUNT(*) n FROM unit").fetchone()["n"] == 1


def test_meta_roundtrip():
    ledger.set_meta("noise_band_pp", "0.7")
    assert ledger.get_meta("noise_band_pp") == "0.7"
    assert ledger.get_meta("absent", "fallback") == "fallback"


# ---- validation predicate ----

def _write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def _e1row(tag="m1", answer="vacuum_leak", refs=(5,)):
    return {"case_id": "c", "arm": "B", "model": tag, "answer": answer,
            "fault": "vacuum_leak", "retrieved_doc_ids": list(refs)}


def test_validate_happy_path(tmp_path):
    p = _write(tmp_path / "r.jsonl", [_e1row() for _ in range(3)])
    ok, msg = ledger.validate_output(p, "m1", 3, "B")
    assert ok and "3 rows" in msg


def test_validate_missing_file(tmp_path):
    ok, msg = ledger.validate_output(tmp_path / "nope.jsonl", "m1", 3, "B")
    assert not ok and "missing" in msg


def test_validate_truncated_run_is_not_done(tmp_path):
    p = _write(tmp_path / "r.jsonl", [_e1row() for _ in range(2)])
    ok, msg = ledger.validate_output(p, "m1", 147, "B")
    assert not ok and "row count" in msg


def test_validate_wrong_model_tag(tmp_path):
    p = _write(tmp_path / "r.jsonl", [_e1row(tag="other") for _ in range(3)])
    ok, msg = ledger.validate_output(p, "m1", 3, "B")
    assert not ok and "wrong model tag" in msg


def test_validate_catches_silent_arm_a_degradation(tmp_path):
    # retrieval arm where retrieve() returned nothing on every row
    p = _write(tmp_path / "r.jsonl", [_e1row(refs=()) for _ in range(3)])
    ok, msg = ledger.validate_output(p, "m1", 3, "B")
    assert not ok and "ZERO refs" in msg


def test_validate_allows_empty_refs_on_arm_a(tmp_path):
    p = _write(tmp_path / "r.jsonl", [_e1row(refs=()) for _ in range(3)])
    ok, _ = ledger.validate_output(p, "m1", 3, "A")
    assert ok


def test_validate_catches_all_empty_answers(tmp_path):
    p = _write(tmp_path / "r.jsonl", [_e1row(answer="") for _ in range(3)])
    ok, msg = ledger.validate_output(p, "m1", 3, "A")
    assert not ok and "carry an answer" in msg


def test_validate_e2_shape_decline_counts_as_answered(tmp_path):
    rows = [{"probe_id": "p", "arm": "B", "model": "m1", "retrieved_doc_ids": [1],
             "answer": {"value": None, "must_retrieve": True}} for _ in range(3)]
    p = _write(tmp_path / "r.jsonl", rows)
    ok, _ = ledger.validate_output(p, "m1", 3, "B")
    assert ok      # an honest decline IS a real answer


def test_validate_e2_all_null_answers_fails(tmp_path):
    rows = [{"probe_id": "p", "arm": "A", "model": "m1",
             "answer": {"value": None, "must_retrieve": False}} for _ in range(3)]
    p = _write(tmp_path / "r.jsonl", rows)
    ok, msg = ledger.validate_output(p, "m1", 3, "A")
    assert not ok and "carry an answer" in msg
