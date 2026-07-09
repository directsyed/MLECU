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


def retrieve(cfg: RetrievalCfg, text: str) -> list[RefSnippet]:
    """Top-k reference snippets for an eval prompt, or [] when nothing matches."""
    terms = query_terms(text)
    if not terms:
        return []
    match_query = " OR ".join(terms)
    conn = sqlite3.connect(f"file:{cfg.db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT rowid, title,
                      snippet(ref_fts, 1, '', '', ' … ', 24) AS snip
               FROM ref_fts WHERE ref_fts MATCH ? ORDER BY bm25(ref_fts) LIMIT ?""",
            (match_query, cfg.top_k),
        ).fetchall()
    finally:
        conn.close()
    return [RefSnippet(r["rowid"], r["title"] or "", r["snip"][:cfg.snippet_max_chars])
            for r in rows]



