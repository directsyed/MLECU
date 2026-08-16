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


# ---------------------------------------------------------------- 2026-08-16 hardening

def test_pending_for_judge_INCLUDES_gone_marked_docs(state):
    """Gone-sweep policy (decisions.md 2026-07-22, NARROW): gone-ness affects scraping only,
    never judging. The old query filtered `gone_at IS NULL` and hid 303/314 pending community
    docs for a month."""
    state.conn.execute("UPDATE document SET gone_at='2026-06-26T00:00:00Z' WHERE id IN (1, 2)")
    ids = [r["id"] for r in state.pending_for_judge(100)]
    assert 1 in ids and 2 in ids
    ids_src = [r["id"] for r in state.pending_for_judge(100, sources=("forum_x",))]
    assert set(ids_src) == {1, 2}


def test_no_reindex_leaves_ensure_index_untouched(state, cfg, fake_llm, monkeypatch):
    from judge import retrieval
    from judge.config import Config
    retrieval.ensure_index(state, Config())     # the real corpus already has ref_fts
    calls = []
    monkeypatch.setattr(retrieval, "ensure_index", lambda s, c: calls.append(1))
    stats = runner.run(cfg, state, reindex=False)
    assert calls == [] and stats.judged == 3
    stats2 = runner.run(cfg, state, reindex=True)
    assert calls == [1] and stats2.judged == 0


def test_dead_server_STOPS_the_run_and_leaves_the_doc_pending(state, cfg, monkeypatch):
    from judge import retrieval
    from judge.config import Config
    retrieval.ensure_index(state, Config())
    health = {"n": 0}

    def health_check(c):
        health["n"] += 1
        if health["n"] == 1:
            return "fake-model"            # start-of-run check passes
        raise runner.llm.LlmError("connection refused")

    def dead_chat(llm_cfg, system, user, json_schema=None, retries=3):
        raise runner.llm.LlmError("chat failed after 3 attempts: connection refused")

    monkeypatch.setattr(runner.llm, "health_check", health_check)
    monkeypatch.setattr(runner.llm, "chat", dead_chat)
    stats = runner.run(cfg, state)
    assert stats.stopped and "unreachable" in stats.stopped
    assert stats.failed == 0                       # nothing burned to 'failed'
    rows = state.conn.execute(
        "SELECT judgment_status FROM document WHERE tier='community' ORDER BY id").fetchall()
    assert all(r["judgment_status"] == "pending" for r in rows)


def test_llm_error_with_a_LIVE_server_still_marks_that_doc_failed(state, cfg, monkeypatch):
    """The stop path is only for a dead server; a per-doc LlmError (e.g. verdict invalid after
    N attempts) with the server up must still park the doc as 'failed', as before."""
    from judge import retrieval
    from judge.config import Config
    retrieval.ensure_index(state, Config())
    monkeypatch.setattr(runner.llm, "health_check", lambda c: "fake-model")

    def bad_chat(llm_cfg, system, user, json_schema=None, retries=3):
        raise runner.llm.LlmError("verdict invalid after 3 attempts: nope")

    monkeypatch.setattr(runner.llm, "chat", bad_chat)
    stats = runner.run(cfg, state, limit=1)
    assert not stats.stopped and stats.failed >= 1
    st = state.conn.execute("SELECT judgment_status FROM document WHERE id=1").fetchone()[0]
    assert st == "failed"
