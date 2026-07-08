"""Arm-B retrieval — BM25 over the judge-kept reference corpus, read-only.

Reuses the ref_fts FTS5 index the judge maintains inside corpus.sqlite (rebuilt by
`judge.cli --reindex` / on judge runs when the kept-count changes). We open the DB with
mode=ro so an eval run can never hold a write lock against a live judge/labeler. Query-term
extraction mirrors the judge's grounding (frequency-ranked content words) so arm B retrieves
the way the certified judge retrieves — one fewer variable between them.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from .config import RetrievalCfg

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_/.-]{2,}")
_STOP = frozenset("""the and for with that this from have has was were are you your not can will
would should could about into over under than then them they there their what when where which
while been being does doing very just like also some more most much many each other only same
""".split())


@dataclass(frozen=True)
class RefSnippet:
    ref_doc_id: int
    title: str
    snippet: str


def _connect_ro(cfg: RetrievalCfg) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{cfg.db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    n = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='ref_fts'").fetchone()[0]
    if not n:
        raise RuntimeError("ref_fts index missing — run `judge.cli --reindex` first")
    return conn


def query_terms(text: str, max_terms: int = 12) -> list[str]:
    """Salient query terms, double-quoted (bare FTS5 tokens are syntax: AND/OR/NEAR/'-')."""
    freq: dict[str, int] = {}
    for w in _WORD.findall(text):
        lw = w.lower()
        if lw not in _STOP:
            freq[lw] = freq.get(lw, 0) + 1
    ranked = sorted(freq, key=lambda w: (-freq[w], -len(w)))
    return [f'"{w}"' for w in ranked[:max_terms]]


def retrieve(cfg: RetrievalCfg, text: str) -> list[RefSnippet]:
    """Top-k reference snippets for an eval prompt, or [] when nothing matches."""
    terms = query_terms(text)
    if not terms:
        return []
    with _connect_ro(cfg) as conn:
        rows = conn.execute(
            """SELECT rowid, title,
                      snippet(ref_fts, 1, '', '', ' … ', 24) AS snip
               FROM ref_fts WHERE ref_fts MATCH ? ORDER BY bm25(ref_fts) LIMIT ?""",
            (" OR ".join(terms), cfg.top_k),
        ).fetchall()
    cap = cfg.snippet_max_chars
    return [RefSnippet(r["rowid"], r["title"] or "", r["snip"][:cap]) for r in rows]
