from judge import retrieval


def test_index_builds_and_retrieves(state, cfg):
    assert retrieval.ensure_index(state, cfg) is True
    assert retrieval.ensure_index(state, cfg) is False       # unchanged -> no rebuild
    hits = retrieval.grounding(state, cfg, "MAF Sensor Scaling trims at idle")
    assert hits, "expected reference hits for a lexical MAF query"
    titles = {h.title for h in hits}
    assert titles & {"MAF theory", "A2WC400D def"}
    assert all(len(h.snippet) <= cfg.retrieval.snippet_max_chars for h in hits)


def test_query_terms_escaped():
    terms = retrieval._query_terms('AND OR NEAR "quoted" injector-latency 2.5rows')
    assert all(t.startswith('"') and t.endswith('"') for t in terms)


def test_rebuilds_when_reference_grows(state, cfg):
    retrieval.ensure_index(state, cfg)
    from corpus_pipeline.core.models import Document
    state.upsert_document(Document(source="rusefi_docs", source_id="r2", title="AVCS theory",
                                   text="intake cam advance changes overlap and idle stability",
                                   tier="reference", gate_status="kept"))
    assert retrieval.ensure_index(state, cfg) is True
    hits = retrieval.grounding(state, cfg, "intake cam advance overlap idle")
    assert any(h.title == "AVCS theory" for h in hits)


# ---------------------------------------------------------------- 2026-08-16 community index

def test_ensure_community_index_is_separate_includes_gone_docs_and_leaves_ref_fts_alone(state, cfg):
    from judge import retrieval
    from judge.config import Config
    retrieval.ensure_index(state, Config())
    ref_before = state.conn.execute("SELECT COUNT(*) FROM ref_fts").fetchone()[0]
    # judge the two community docs: one keeps (4), one drops (2); mark the keeper GONE
    state.mark_judged(1, score=4, judge_model="t", rubric_version="r2",
                      chunks=[{"score": 4, "rationale": "x"}])
    state.mark_judged(2, score=2, judge_model="t", rubric_version="r2",
                      chunks=[{"score": 2, "rationale": "x"}])
    state.conn.execute("UPDATE document SET gone_at='2026-06-26T00:00:00Z' WHERE id=1")

    assert state.community_kept_count(4) == 1
    assert retrieval.ensure_community_index(state, min_score=4) is True
    ids = [r[0] for r in state.conn.execute("SELECT rowid FROM community_fts")]
    assert ids == [1]                                    # gone doc INDEXED (NARROW policy)
    assert state.conn.execute("SELECT COUNT(*) FROM ref_fts").fetchone()[0] == ref_before
    assert state.get_meta("community_fts_doc_count") == "1"
    assert state.get_meta("community_fts_min_score") == "4"
    # idempotent on an unchanged corpus; rebuilds when the bar moves
    assert retrieval.ensure_community_index(state, min_score=4) is False
    assert retrieval.ensure_community_index(state, min_score=3) is True
    # tier is provenance: never written
    tiers = {r[0] for r in state.conn.execute("SELECT tier FROM document WHERE id IN (1,2)")}
    assert tiers == {"community"}
