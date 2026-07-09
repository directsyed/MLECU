"""Harness tests — no GPU, no llama-server. chat_fn is stubbed; retrieval tests hit the real
corpus DB read-only and skip cleanly when it's absent (e.g. a fresh clone)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # ml/eval/ on the path

from harness import arms, e1                                       # noqa: E402
from harness.config import Config                                  # noqa: E402

CFG = Config()
CASES = e1.load_cases(CFG.cases_path)


def test_cases_load_and_have_contract():
    assert len(CASES) >= 70
    c = CASES[0]
    assert {"case_id", "prompt", "choices", "fault", "acceptable"} <= c.keys()


def test_answer_schema_pins_choices():
    s = arms.answer_schema(["healthy", "maf_low"])
    assert s["properties"]["fault"]["enum"] == ["healthy", "maf_low"]
    assert s["required"] == ["fault"]


def test_arm_a_is_verbatim():
    user, refs = arms.build_user("A", CFG, "case text")
    assert user == "case text" and refs == []


def test_unknown_arm_rejected():
    with pytest.raises(ValueError):
        arms.build_user("C", CFG, "x")




def test_run_arm_with_stub_and_score(tmp_path):
    cfg = Config(results_dir=tmp_path)          # frozen dataclass: replace via constructor
    cases = CASES[:6]

    def stub_chat(llm_cfg, system, user, json_schema=None):
        # always answers the first allowed choice; grammar-shaped like the real server
        return json.dumps({"fault": json_schema["properties"]["fault"]["enum"][0]}), \
               {"prompt_tokens": 10, "completion_tokens": 5}, 0.01

    out = e1.run_arm(cfg, "A", 1, cases, chat_fn=stub_chat, log=lambda *_: None)
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert len(rows) == 6 and rows[0]["arm"] == "A"
    report = e1.score_results(cfg, out)
    assert report.n == 6                        # scored exactly what was answered
    assert 0.0 <= report.top1 <= 1.0


def test_determinism_helper(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    a.write_text(json.dumps({"case_id": "x", "answer": "healthy"}) + "\n")
    b.write_text(json.dumps({"case_id": "x", "answer": "healthy"}) + "\n")
    assert e1.determinism(a, b) == (1, 1)


def test_scoring_module_is_the_ecutune_one():
    scoring = e1.load_scoring(CFG.scoring_py)
    # the rules baseline exists and brackets the eval — same module the 85.7% came from
    assert hasattr(scoring, "rules_baseline") and hasattr(scoring, "score")
