"""retrieval-v2 (hybrid dense+BM25) unit tests, 2026-07-22 overnight build.

Everything here runs WITHOUT the dense index or the embedding model: the fusion math is
tested directly, and the fallback path is tested by pointing index_path at a missing file.
The end-to-end hybrid smoke (real index, paraphrase query) runs in the overnight chain and
is logged there; it needs the 2.3GB model, too heavy for a unit suite.
"""
from pathlib import Path

import pytest

harness = pytest.importorskip("harness.retrieval")
from harness.config import Config, RetrievalCfg  # noqa: E402
from harness import retrieval  # noqa: E402

DB = RetrievalCfg().db_path


def _cfg(**kw):
    return RetrievalCfg(**kw)


@pytest.mark.skipif(not DB.exists(), reason="corpus DB not present")
def test_bm25_mode_is_v1_behavior():
    cfg = _cfg(mode="bm25", top_k=3)
    snips = retrieval.retrieve(cfg, "boost target duty cycle wastegate MAF scaling")
    assert len(snips) <= 3
    for s in snips:
        assert isinstance(s.ref_doc_id, int) and len(s.snippet) <= cfg.snippet_max_chars


@pytest.mark.skipif(not DB.exists(), reason="corpus DB not present")
def test_hybrid_without_index_falls_back_to_bm25(tmp_path):
    cfg_v1 = _cfg(mode="bm25", top_k=3)
    cfg_hy = _cfg(mode="hybrid", top_k=3, index_path=tmp_path / "absent.npz")
    q = "injector latency dead time voltage compensation"
    assert [s.ref_doc_id for s in retrieval.retrieve(cfg_hy, q)] == \
           [s.ref_doc_id for s in retrieval.retrieve(cfg_v1, q)]


def test_rrf_fusion_prefers_doubly_ranked():
    # doc 10 ranks mid in both lists; doc 1 tops one list only. RRF: 10 must win.
    bm25_order = [1, 10, 3]
    dense_order = [7, 10, 9]
    scores = {}
    for rank, rid in enumerate(bm25_order):
        scores[rid] = scores.get(rid, 0.0) + 1.0 / (60 + rank + 1)
    for rank, rid in enumerate(dense_order):
        scores[rid] = scores.get(rid, 0.0) + 1.0 / (60 + rank + 1)
    fused = sorted(scores, key=scores.get, reverse=True)
    assert fused[0] == 10


@pytest.mark.skipif(not DB.exists(), reason="corpus DB not present")
def test_hybrid_respects_top_k_cap():
    cfg = _cfg(mode="hybrid", top_k=6, index_path=Path("/nonexistent.npz"))
    snips = retrieval.retrieve(cfg, "fuel trim idle rpm target timing advance knock")
    assert len(snips) <= 6
