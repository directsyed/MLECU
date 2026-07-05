"""r2 synopsis pre-pass + new verdict fields."""
from __future__ import annotations

from corpus_pipeline.core.models import Document

from judge import runner
from judge.verdict import parse


def test_multichunk_doc_gets_synopsis_in_every_chunk_prompt(state, cfg, fake_llm):
    long_text = "\n\n".join(f"post {i}: MAF Sensor Scaling tweak run {i}, trims logged." * 40
                            for i in range(60))
    assert len(long_text) > cfg.chunking.max_chars          # forces multi-chunk
    state.upsert_document(Document(source="forum_x", source_id="long1",
                                   title="long thread", text=long_text,
                                   tier="community", gate_status="kept"))
    runner.run(cfg, state)
    synopsis_calls = [c for c in fake_llm.calls if c["schema"] is None]
    assert len(synopsis_calls) == 1                          # one pre-pass for the one long doc
    chunk_calls = [c for c in fake_llm.calls
                   if c["schema"] is not None and "long thread" in c["user"]]
    assert len(chunk_calls) >= 2
    assert all("Canned synopsis" in c["user"] for c in chunk_calls)
    # single-chunk docs get no synopsis section
    short_calls = [c for c in fake_llm.calls
                   if c["schema"] is not None and "lean idle after MAF swap" in c["user"]]
    assert all("Canned synopsis" not in c["user"] for c in short_calls)


def test_relevance_and_images_persisted(state, cfg, fake_llm):
    runner.run(cfg, state)
    row = state.conn.execute(
        "SELECT relevance, evidence_in_images FROM judgment WHERE relevance IS NOT NULL LIMIT 1"
    ).fetchone()
    assert row["relevance"] == "subaru_ej"
    assert row["evidence_in_images"] == 0


def test_verdict_parses_r2_fields():
    v = parse('{"score": 3, "rationale": "x", "relevance": "subaru", '
              '"evidence_in_images": true, "pairs": [], "claims_checked": []}')
    assert v.relevance == "subaru" and v.evidence_in_images is True


def test_verdict_rejects_bad_relevance():
    import pytest
    from judge.verdict import VerdictError
    with pytest.raises(VerdictError):
        parse('{"score": 3, "rationale": "x", "relevance": "honda", '
              '"pairs": [], "claims_checked": []}')
