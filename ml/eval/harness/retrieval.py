"""Arm-B retrieval - Syed's build.

query_terms: Syed, solo, 2026-07-08 (his first working Python).
RefSnippet + retrieve + the arms.py branch: finished by Claude same night for schedule
(Syed stopped at the piece-2 scaffold) — resume the walkthrough from retrieve() next session.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from .config import RetrievalCfg

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_/.-]{2,}")

_STOP = frozenset("""the and for with that this from have has was were are
you
your not can will would should could about into over under than then them
they
there their what when where which while been being does doing very just like
also some more most much many each other only same""".split())

def query_terms(text: str, max_terms: int = 12) -> list[str]:
    freq = {}
    for word in _WORD.findall(text):
        word = word.lower()
        if word in _STOP:
            continue
        freq[word] = freq.get(word, 0) + 1
    
    ranked = sorted(freq, key=lambda w: (-freq[w], -len(w)))
    top = ranked[:max_terms]
    result = []
    for w in top:
        result.append(f'"{w}"')
    return result


@dataclass(frozen=True)
class RefSnippet:
    ref_doc_id: int
    title: str
    snippet: str


def _bm25_ranked(cfg: RetrievalCfg, text: str, limit: int) -> list[sqlite3.Row]:
    """retrieval-v1 core (Syed's query_terms + FTS5 BM25), limit parameterized."""
    terms = query_terms(text)
    if not terms:
        return []
    match_query = " OR ".join(terms)
    conn = sqlite3.connect(f"file:{cfg.db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            """SELECT rowid, title,
                      snippet(ref_fts, 1, '', '', ' … ', 24) AS snip
               FROM ref_fts WHERE ref_fts MATCH ?
               ORDER BY bm25(ref_fts), rowid LIMIT ?""",
            (match_query, limit),
        ).fetchall()
    finally:
        conn.close()


# --- retrieval-v2 dense side (2026-07-22 overnight; index: harness/embed_index.py) ---
_DENSE = {}          # process-lifetime cache: {"model": SentenceTransformer, "idx": npz}

_CAND = 20           # candidates each ranker contributes before fusion
_RRF_K = 60          # standard RRF damping constant


def _dense_ranked(cfg: RetrievalCfg, text: str, limit: int) -> list[int]:
    """rowids ranked by cosine similarity, best first. [] if index/model unavailable.
    Cache is keyed by index PATH (bug found 2026-07-25: an unkeyed cache served the
    first-loaded index to every later config, ignoring index_path)."""
    key = str(cfg.index_path)
    if key not in _DENSE:
        if not cfg.index_path.exists():
            return []
        import numpy as np
        data = np.load(cfg.index_path)
        _DENSE[key] = (data["vecs"], data["rowids"])
    if "model" not in _DENSE:
        from sentence_transformers import SentenceTransformer
        _DENSE["model"] = SentenceTransformer("BAAI/bge-m3", device="cpu")
    vecs, rowids = _DENSE[key]
    q = _DENSE["model"].encode([text[:6000]], normalize_embeddings=True,
                               convert_to_numpy=True)[0]
    sims = vecs @ q                      # cosine similarity (both sides L2-normalized)
    top = sims.argsort()[::-1][:limit]
    return [int(rowids[i]) for i in top]


def _snippets_for(cfg: RetrievalCfg, ordered_rowids: list[int],
                  bm25_rows: dict[int, sqlite3.Row]) -> list[RefSnippet]:
    """RefSnippets in fused order. BM25 hits keep their FTS snippet(); dense-only hits get
    the chunk head (FTS snippet() needs a MATCH, which a dense hit may not have)."""
    need = [r for r in ordered_rowids if r not in bm25_rows]
    fetched = {}
    if need:
        conn = sqlite3.connect(f"file:{cfg.db_path}?mode=ro", uri=True)
        try:
            marks = ",".join("?" * len(need))
            for rowid, title, text in conn.execute(
                    f"SELECT rowid, title, text FROM ref_fts WHERE rowid IN ({marks})", need):
                fetched[rowid] = (title or "", (text or "")[:cfg.snippet_max_chars])
        finally:
            conn.close()
    out = []
    for rid in ordered_rowids:
        if rid in bm25_rows:
            r = bm25_rows[rid]
            out.append(RefSnippet(rid, r["title"] or "", r["snip"][:cfg.snippet_max_chars]))
        elif rid in fetched:
            out.append(RefSnippet(rid, fetched[rid][0], fetched[rid][1]))
    return out


def retrieve(cfg: RetrievalCfg, text: str) -> list[RefSnippet]:
    """Top-k reference snippets for an eval prompt, or [] when nothing matches.

    mode="bm25": retrieval-v1 exactly (Syed's build, preserved for audit/repro).
    mode="hybrid" (default since 2026-07-22): BM25 top-20 and BGE-M3 cosine top-20 fused by
    Reciprocal Rank Fusion — score(doc) = sum over rankers of 1/(60 + rank). RRF needs no
    tuned weights and rewards documents both rankers like, while letting either ranker
    alone carry a hit the other missed (the paraphrase case BM25 can't see). Falls back to
    pure BM25 when the dense index hasn't been built."""
    if cfg.mode == "bm25":
        rows = _bm25_ranked(cfg, text, cfg.top_k)
        return [RefSnippet(r["rowid"], r["title"] or "", r["snip"][:cfg.snippet_max_chars])
                for r in rows]

    bm25 = _bm25_ranked(cfg, text, _CAND)
    dense = _dense_ranked(cfg, text, _CAND)
    if not dense:                        # index absent -> graceful v1 behavior
        return [RefSnippet(r["rowid"], r["title"] or "", r["snip"][:cfg.snippet_max_chars])
                for r in bm25[:cfg.top_k]]

    scores: dict[int, float] = {}
    for rank, r in enumerate(bm25):
        scores[r["rowid"]] = scores.get(r["rowid"], 0.0) + 1.0 / (_RRF_K + rank + 1)
    for rank, rid in enumerate(dense):
        scores[rid] = scores.get(rid, 0.0) + 1.0 / (_RRF_K + rank + 1)
    fused = sorted(scores, key=scores.get, reverse=True)[:cfg.top_k]
    return _snippets_for(cfg, fused, {r["rowid"]: r for r in bm25})



