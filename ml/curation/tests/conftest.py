"""Shared fixtures: a tmp corpus State with seeded docs, and a canned fake-LLM."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # ml/curation on path

from corpus_pipeline.core.models import Document
from corpus_pipeline.core.state import State

from judge.config import Config


@pytest.fixture()
def cfg(tmp_path) -> Config:
    c = Config()
    c.corpus.db_path = str(tmp_path / "corpus.sqlite")
    c.audit.dir = str(tmp_path / "audit")
    c.judge.prompts_dir = str(Path(__file__).resolve().parents[1] / "prompts" / "rubric-r1")
    # mirror config.yaml's reference policy (pydantic defaults are deliberately conservative)
    c.judge.reference_policy = {"default": "light_judge", "romraider_defs": "auto_pass"}
    return c


@pytest.fixture()
def state(cfg):
    s = State(cfg.corpus.db_path)
    docs = [
        Document(source="forum_x", source_id="t1", title="lean idle after MAF swap",
                 text="Trims were +12% at idle. Rescaled MAF Sensor Scaling by 7%, "
                      "trims settled to +2%. Injector latency stock at 0.66ms @14V.",
                 tier="community", gate_status="kept"),
        Document(source="forum_x", source_id="t2", title="opinions on oil",
                 text="I reckon thicker oil just feels better, no data though." * 3,
                 tier="community", gate_status="kept"),
        Document(source="romraider_defs", source_id="d1", title="A2WC400D def",
                 text="Table: MAF Sensor Scaling, address 0xCB75C, float, g/s, 48 elements.",
                 tier="reference", gate_status="kept"),
        Document(source="rusefi_docs", source_id="r1", title="MAF theory",
                 text="MAF Sensor Scaling maps sensor volts to airflow g/s; errors show as "
                      "closed-loop fuel trims at steady state; injector latency shifts with "
                      "battery voltage.",
                 tier="reference", gate_status="kept"),
    ]
    for d in docs:
        s.upsert_document(d)
    yield s
    s.close()


class FakeLlm:
    """Stands in for llm.chat — returns canned verdict JSON, records prompts."""
    def __init__(self, score: int = 4, fail_first: bool = False):
        self.score = score
        self.fail_first = fail_first
        self.calls: list[dict] = []

    def __call__(self, llm_cfg, system, user, json_schema=None, retries=3):
        self.calls.append({"system": system, "user": user})
        if self.fail_first and len(self.calls) == 1:
            return "not json at all", {"prompt_tokens": 10, "completion_tokens": 2}
        verdict = {
            "score": self.score,
            "rationale": "canned rationale",
            "pairs": [{"symptoms": "+12% trims", "diagnosis": "MAF misscale",
                       "change": "rescale 7%", "outcome": "trims +2%"}],
            "claims_checked": [],
        }
        return json.dumps(verdict), {"prompt_tokens": 100, "completion_tokens": 50}


@pytest.fixture()
def fake_llm(monkeypatch):
    fake = FakeLlm()
    from judge import runner
    monkeypatch.setattr(runner.llm, "chat", fake)
    monkeypatch.setattr(runner.llm, "health_check", lambda c: "fake-model")
    return fake
