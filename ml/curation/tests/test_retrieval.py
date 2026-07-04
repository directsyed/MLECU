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
