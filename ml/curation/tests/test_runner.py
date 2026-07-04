import json

from judge import runner


def test_run_judges_community_and_light_judges_reference(state, cfg, fake_llm):
    stats = runner.run(cfg, state)
    # 2 community (full) + 1 rusefi_docs (light_judge default) = 3 LLM-judged;
    # romraider_defs is auto_pass per config default map
    assert stats.judged == 3
    assert stats.auto_passed == 1
    assert stats.failed == 0
    rows = state.conn.execute(
        "SELECT judgment_status, judge_score, judge_model FROM document ORDER BY id").fetchall()
    assert all(r["judgment_status"] == "judged" for r in rows)
    ap = state.conn.execute(
        "SELECT judge_model, judge_score FROM document WHERE source='romraider_defs'").fetchone()
    assert ap["judge_model"] == runner.AUTO_PASS_MODEL and ap["judge_score"] == 5
    # judgment rows exist with pairs + audit trail written 1:1
    j = state.conn.execute("SELECT COUNT(*) FROM judgment").fetchone()[0]
    assert j == 4
    audit_file = list((cfg.resolve(cfg.audit.dir)).glob("judge-*.jsonl"))[0]
    lines = [json.loads(l) for l in audit_file.read_text().splitlines()]
    assert len(lines) == 4


def test_rerun_is_noop_after_all_judged(state, cfg, fake_llm):
    runner.run(cfg, state)
    stats2 = runner.run(cfg, state)
    assert stats2.judged == 0 and stats2.auto_passed == 0


def test_invalid_verdict_reasked_then_ok(state, cfg, monkeypatch):
    from tests.conftest import FakeLlm
    fake = FakeLlm(fail_first=True)
    monkeypatch.setattr(runner.llm, "chat", fake)
    monkeypatch.setattr(runner.llm, "health_check", lambda c: "fake")
    stats = runner.run(cfg, state, limit=1)
    assert stats.failed == 0
    # first call invalid -> re-ask carries the validation error
    assert "previous reply was invalid" in fake.calls[1]["user"]


def test_grounding_only_for_community(state, cfg, fake_llm):
    from judge import retrieval
    retrieval.ensure_index(state, cfg)
    runner.run(cfg, state)
    community_calls = [c for c in fake_llm.calls if "tier: community" in c["user"]]
    reference_calls = [c for c in fake_llm.calls if "tier: reference" in c["user"]]
    assert any("[REF " in c["user"] for c in community_calls)
    assert all("[REF " not in c["user"] for c in reference_calls)
