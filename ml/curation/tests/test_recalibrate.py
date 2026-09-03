"""recalibrate.py, the candidate-judge calibration harness.

These exist because the first revision (2026-08-16) instantiated `Config()` instead of
`load_config()`, which silently ran rubric r1 at 1500 tokens, an invalid comparison that would
have gated the corpus. Nothing here talks to a real LLM."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from judge import recalibrate
from judge.config import DEFAULT_CONFIG, load_config

from tests.conftest import FakeLlm

SET = "calibration-test"


def _label_all(state, label_set=SET, rater="adjudicated"):
    """Truth labels for the 4 seeded docs (ids 1..4) + the ref_fts the grounding path reads
    (the real corpus has it; recalibrate deliberately never (re)builds indexes)."""
    from judge import retrieval
    from judge.config import Config
    retrieval.ensure_index(state, Config())
    for doc_id, score in ((1, 4), (2, 2), (3, 3), (4, 3)):
        state.add_label(doc_id, score=score, label_set=label_set, rater=rater)


def _write_cfg(cfg, tmp_path) -> str:
    """Materialise the fixture Config as a yaml so `--config` is genuinely exercised."""
    d = cfg.model_dump()
    d["calibration"]["set_name"] = SET
    d["llm"]["max_completion_tokens"] = 24576
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    load_config.cache_clear()
    return str(p)


@pytest.fixture()
def fake(monkeypatch):
    f = FakeLlm(score=4)
    from judge import runner
    monkeypatch.setattr(runner.llm, "chat", f)
    monkeypatch.setattr(runner.llm, "health_check", lambda c: "fake-served-model")
    return f


def test_real_config_yaml_is_r2_with_a_thinking_budget():
    """The F1 regression guard: what recalibrate now loads must be the calibrated rubric."""
    load_config.cache_clear()
    cfg = load_config(str(DEFAULT_CONFIG))
    assert cfg.rubric_version == "rubric-r2"
    assert cfg.llm.max_completion_tokens >= 8192
    assert cfg.llm.model != "unknown"


def test_preregistered_bars_come_from_db_meta(state):
    state.set_meta(f"{SET}:pass_bars", json.dumps(
        {"keep_drop_pct": 90, "within1_pct": 90, "dangerous_cells": 0, "registered": "x"}))
    bars = recalibrate.load_preregistered_bars(state, SET)
    assert bars["keep_agree_pct"] == 90.0 and bars["within1_pct"] == 90.0
    assert bars["dangerous_max"] == 0 and "meta[" in bars["source"]


def test_preregistered_bars_fall_back_when_meta_missing(state):
    bars = recalibrate.load_preregistered_bars(state, "no-such-set")
    assert bars["keep_agree_pct"] == 90.0 and "default" in bars["source"]


def test_verdict_vs_bars_dangerous_is_a_hard_fail():
    ag = SimpleNamespace(keep_agree_pct=99.0, within1_pct=99.0, dangerous=1)
    ok, lines = recalibrate.verdict_vs_bars(ag, recalibrate.INCUMBENT_BARS)
    assert ok is False and any("FAIL" in l and "dangerous" in l for l in lines)
    ag2 = SimpleNamespace(keep_agree_pct=93.1, within1_pct=97.7, dangerous=0)
    assert recalibrate.verdict_vs_bars(ag2, recalibrate.INCUMBENT_BARS)[0] is True


def test_main_scores_through_real_path_and_checkpoints_every_doc(state, cfg, fake, tmp_path,
                                                                 monkeypatch):
    _label_all(state)
    state.set_meta(f"{SET}:pass_bars", json.dumps(
        {"keep_drop_pct": 90, "within1_pct": 90, "dangerous_cells": 0}))
    state.conn.commit()
    cfg_path = _write_cfg(cfg, tmp_path)
    out = tmp_path / "recal.json"
    seen = []
    real_write = recalibrate._write_report

    def spy(path, payload):
        seen.append(payload["n_scored"])
        real_write(path, payload)
    monkeypatch.setattr(recalibrate, "_write_report", spy)

    with pytest.raises(SystemExit) as ex:
        recalibrate.main(["--model-tag", "cand", "--config", cfg_path, "--out", str(out)])
    rep = json.loads(out.read_text())
    assert rep["complete"] is True and rep["n_scored"] == 4
    assert rep["served_model"] == "fake-served-model"
    assert rep["rubric_version"] == "rubric-r2"
    assert rep["max_completion_tokens"] == 24576
    assert rep["bars_preregistered"]["keep_agree_pct"] == 90.0
    assert rep["bars_incumbent"]["keep_agree_pct"] == 93.1
    # checkpointed after each of the 4 docs, then the final write
    assert seen == [1, 2, 3, 4, 4]
    # fake judge says 4 for everything: truth (4,2,3,3) -> keep/drop agrees on 1 of 4, 1 dangerous
    assert rep["agreement"]["dangerous"] == 1
    assert rep["passed"] is False and ex.value.code == 1


def test_resume_skips_scored_docs_and_doc_ids_selects_subset(state, cfg, fake, tmp_path):
    _label_all(state)
    state.conn.commit()
    cfg_path = _write_cfg(cfg, tmp_path)
    out = tmp_path / "recal.json"
    with pytest.raises(SystemExit):
        recalibrate.main(["--model-tag", "cand", "--config", cfg_path, "--out", str(out),
                          "--doc-ids", "1,2"])
    rep = json.loads(out.read_text())
    assert sorted(map(int, rep["scores"])) == [1, 2]
    calls_before = len(fake.calls)

    with pytest.raises(SystemExit):
        recalibrate.main(["--model-tag", "cand", "--config", cfg_path, "--out", str(out),
                          "--resume"])
    rep2 = json.loads(out.read_text())
    assert sorted(map(int, rep2["scores"])) == [1, 2, 3, 4]
    # only docs 3 and 4 hit the LLM on resume (one chunk each -> 2 calls)
    assert len(fake.calls) - calls_before == 2
    assert rep2["complete"] is True


def test_doc_ids_outside_label_set_is_an_error(state, cfg, fake, tmp_path):
    _label_all(state)
    state.conn.commit()
    cfg_path = _write_cfg(cfg, tmp_path)
    with pytest.raises(SystemExit) as ex:
        recalibrate.main(["--model-tag", "cand", "--config", cfg_path, "--doc-ids", "999"])
    assert "not in label set" in str(ex.value.code)
