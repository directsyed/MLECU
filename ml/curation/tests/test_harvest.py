import json

from judge import runner
from judge.harvest import harvest


def test_harvest_keeps_only_threshold_chunks_with_outcomes(state, cfg, fake_llm, tmp_path):
    runner.run(cfg, state)                      # fake verdicts: score 4, one complete pair each
    # plant real docs: one low-score chunk with a pair, one keep-chunk pair lacking an outcome
    from corpus_pipeline.core.models import Document
    lo, _ = state.upsert_document(Document(source="x", source_id="lo", title="lo",
                                           text="low chunk", gate_status="kept"))
    hi, _ = state.upsert_document(Document(source="x", source_id="hi", title="hi",
                                           text="no outcome", gate_status="kept"))
    state.mark_judged(lo, score=2, judge_model="m", rubric_version=cfg.rubric_version,
                      chunks=[{"score": 2, "pairs_json": json.dumps(
                          [{"symptoms": "s", "diagnosis": "d", "change": "c", "outcome": "o"}])}])
    state.mark_judged(hi, score=4, judge_model="m", rubric_version=cfg.rubric_version,
                      chunks=[{"score": 4, "pairs_json": json.dumps(
                          [{"symptoms": "s", "diagnosis": "d", "change": "c", "outcome": ""}])}])
    out = tmp_path / "pairs.jsonl"
    st = harvest(state, cfg, out)
    recs = [json.loads(l) for l in out.read_text().splitlines()]
    assert st["pairs_kept"] == len(recs) > 0
    assert all(r["outcome"] for r in recs)                       # no empty outcomes
    assert all(r["provenance"]["chunk_score"] >= 4 for r in recs)  # no low chunks
    assert st["dropped_no_outcome"] == 1
    assert all("doc_id" in r["provenance"] and "url" in r["provenance"] for r in recs)
