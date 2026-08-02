"""Arm-B retrieval - Syed's build.

query_terms: Syed, solo, 2026-07-08 (his first working Python).
RefSnippet + retrieve + the arms.py branch: finished by Claude same night for schedule
(Syed stopped at the piece-2 scaffold) — resume the walkthrough from retrieve() next session.

2026-08-02 (bench-integrity Phase 1): snippet extraction rewritten (see the block above
extract_window), retrieval provenance exposed via retrieve_with_meta(), dense-index
freshness checked at load. query_terms() is UNTOUCHED — it is Syed's code and it is correct.
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
    """retrieval-v1 core (Syed's query_terms + FTS5 BM25), limit parameterized.

    The FTS snippet() call stays here because mode="bm25" is byte-frozen for audit/repro of
    every result produced before 2026-08-02. Hybrid mode no longer consumes `snip`.
    """
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


# --- unified snippet extraction (2026-08-02, bench-integrity Phase 1) ------------------
#
# WHY THIS EXISTS. retrieval-v1 showed models `snippet(ref_fts, 1, '', '', ' … ', 24)` — a
# 24-TOKEN window cut by the FTS5 tokenizer. That tokenizer splits "11.8%" into the tokens
# "11" and "8", so a window boundary landing between them emitted "11 …". On probe
# e2-5723-1 three separate models were scored `dangerous_miss` for faithfully quoting the
# mutilated evidence WE handed them (found 2026-08-01). A benchmark that convicts a model
# for the harness's own truncation is measuring the harness, not the model.
#
# Second defect, same code path (audit A6): the token window was applied ONLY to BM25 hits.
# Dense-only hits got 1200 clean characters. So a document both rankers agreed on — the
# best evidence in the pool — was the one served mangled, while a weaker dense-only hit came
# through intact. The asymmetry ran backwards from quality.
#
# THE FIX: one character-window extractor used for every hit in hybrid mode. It centres on
# the first query-term match, snaps to whitespace so no token is ever bisected, and refuses
# to end (or begin) inside a run of number characters — including runs broken across a space
# ("30 000") or trailing a unit sign ("11.8 %"). The number guard is bounded so a table row
# of digits cannot drag the window open indefinitely.
_NUMISH_HEAD = re.compile(r"[0-9%]")
_NUM_TOKEN = re.compile(r"[0-9][0-9.,%]*$")     # a token that is / continues a number
NUM_RUN_MAX_EXTEND = 40                          # budget reserved for the no-cut extension
_ELLIPSIS_LEAD = "… "
_ELLIPSIS_TAIL = " …"


def _prev_token(text: str, i: int) -> tuple[int, str]:
    """The whitespace-delimited token immediately before offset i -> (start, token)."""
    j = i
    while j > 0 and text[j - 1].isspace():
        j -= 1
    k = j
    while k > 0 and not text[k - 1].isspace():
        k -= 1
    return k, text[k:j]


def _next_token(text: str, i: int) -> tuple[int, str]:
    """The whitespace-delimited token at/after offset i -> (end, token)."""
    n = len(text)
    j = i
    while j < n and text[j].isspace():
        j += 1
    k = j
    while k < n and not text[k].isspace():
        k += 1
    return k, text[j:k]


def _snap_back(text: str, i: int) -> int:
    """Move left to a whitespace boundary so a window edge never bisects a token."""
    while i > 0 and not text[i - 1].isspace():
        i -= 1
    return i


def _bisects_number_at_end(text: str, end: int) -> bool:
    """True when the boundary at `end` sits inside a number run ('30 000', '11.8 %')."""
    if end <= 0 or end >= len(text):
        return False
    _, last = _prev_token(text, end)
    if not _NUM_TOKEN.match(last or ""):
        return False
    _, nxt = _next_token(text, end)
    return bool(nxt) and bool(_NUMISH_HEAD.match(nxt))


def _no_cut_number_end(text: str, end: int, hard_limit: int) -> int:
    """Move `end` off a number run it would otherwise bisect, staying within hard_limit.

    Preference is to EXTEND forward and keep the whole number. When the run will not fit in
    the remaining budget we RETREAT instead, dropping the trailing number tokens: a truncated
    number in the evidence is the exact defect this module exists to prevent, so losing a
    number at the edge is always preferable to emitting half of one.
    """
    while _bisects_number_at_end(text, end):
        nxt_end, _ = _next_token(text, end)
        if nxt_end <= hard_limit:
            end = nxt_end
            continue
        while end > 0 and _bisects_number_at_end(text, end):   # retreat off the run
            end, _ = _prev_token(text, end)
        break
    return end


def _bisects_number_at_start(text: str, start: int) -> bool:
    if start <= 0 or start >= len(text):
        return False
    _, first = _next_token(text, start)
    if not first or not _NUMISH_HEAD.match(first):
        return False
    _, prev = _prev_token(text, start)
    return bool(prev) and bool(_NUM_TOKEN.match(prev))


def _no_cut_number_start(text: str, start: int, hard_floor: int) -> int:
    """Same contract at the leading edge. Emitting the tail of '30 000' as a bare '000'
    would inject a number into the evidence pool that the source never states — and the
    citation guard would then happily 'ground' a fabrication against it."""
    while _bisects_number_at_start(text, start):
        p_start, _ = _prev_token(text, start)
        if p_start >= hard_floor:
            start = p_start
            continue
        while start < len(text) and _bisects_number_at_start(text, start):
            start, _ = _next_token(text, start)      # advance off the run
        break
    return start


def extract_window(text: str, terms: list[str], max_chars: int,
                   lead_frac: float = 0.25) -> str:
    """A readable evidence window around the first query-term hit.

    Contract (the regression tests are the spec): no token is ever bisected; no number run
    is ever bisected; elisions are marked with '…' so the model can see the text was cut;
    and the result is NEVER longer than max_chars, markers included. That last clause is
    Syed's — his RAG acceptance test asserts it, and it caught this function overshooting by
    7 chars on the first pass. The no-cut allowance is therefore RESERVED up front rather
    than spent on top of the budget.
    """
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    budget = max(1, max_chars - len(_ELLIPSIS_LEAD) - len(_ELLIPSIS_TAIL))
    core = max(1, budget - NUM_RUN_MAX_EXTEND)      # room held back for the no-cut extension

    span_start, span_end = _best_span(text, terms, core)
    ideal = span_start - int(core * lead_frac)      # give the first hit some run-up
    if span_end > ideal + core:                     # span wouldn't fit -> centre it instead
        ideal = (span_start + span_end) // 2 - core // 2
    start = max(0, min(ideal, len(text) - core))
    if start > 0:
        # snapping runs LEFT, so the window grows; end is derived afterwards to stay in core
        start = _no_cut_number_start(text, _snap_back(text, start),
                                     max(0, start - NUM_RUN_MAX_EXTEND))
    end = min(len(text), start + core)
    if end < len(text):
        snapped = _snap_back(text, end)
        # a single token longer than the whole window would snap the edge past the start; in
        # that (pathological) case keep the hard cut rather than emit nothing
        if snapped > start:
            end = _no_cut_number_end(text, snapped, start + budget)
    out = text[start:end].strip()
    if start > 0:
        out = _ELLIPSIS_LEAD + out
    if end < len(text):
        out = out + _ELLIPSIS_TAIL
    return out


_MAX_HITS_PER_TERM = 200      # bounds the scan on a pathological chunk


def _term_hits(text_low: str, terms: list[str]) -> list[tuple[int, int]]:
    """(offset, term_index) for every query-term occurrence, capped per term, sorted."""
    hits: list[tuple[int, int]] = []
    for ti, term in enumerate(terms):
        t = term.strip('"').lower()
        if len(t) < 3:
            continue
        pos, n = 0, 0
        while n < _MAX_HITS_PER_TERM:
            i = text_low.find(t, pos)
            if i < 0:
                break
            hits.append((i, ti))
            pos, n = i + len(t), n + 1
    hits.sort()
    return hits


def _best_span(text: str, terms: list[str], width: int) -> tuple[int, int]:
    """The densest passage: the `width`-char span covering the most DISTINCT query terms.
    Returns (span_start, span_end) — the first and last hit offsets inside that span.

    Two earlier drafts of this were wrong, and both were caught by running real probes
    through it rather than by reading the code:
      1. Anchoring on the FIRST term hit lands on whichever query word appears earliest in
         the chunk. On probe e2-5723-1's source, "mechanical" occurs ~7,000 chars before the
         passage that answers the question — the window served a paragraph about ignition
         amplifiers and dropped the answer entirely.
      2. Left-anchoring the window at the densest hit still missed probe e2-2207-0's answer
         by 43 characters, because the span extended past the window's right edge.
    Hence: score spans at the full window width, then let the caller centre the window on the
    span so everything that made the span dense actually survives into the snippet.
    Ties go to the earlier passage.
    """
    hits = _term_hits(text.lower(), terms)
    if not hits:
        return 0, 0
    best, best_key = (hits[0][0], hits[0][0]), (-1, -1)
    counts: dict[int, int] = {}
    j = 0
    for i in range(len(hits)):
        while j < len(hits) and hits[j][0] - hits[i][0] <= width:
            counts[hits[j][1]] = counts.get(hits[j][1], 0) + 1
            j += 1
        key = (len(counts), sum(counts.values()))
        if key > best_key:
            best_key, best = key, (hits[i][0], hits[j - 1][0])
        ti = hits[i][1]                      # slide the left edge off hits[i]
        counts[ti] -= 1
        if counts[ti] == 0:
            del counts[ti]
    return best


# --- retrieval-v2 dense side (2026-07-22 overnight; index: harness/embed_index.py) ---
_DENSE = {}          # process-lifetime cache: {"model": SentenceTransformer, path: (...)}
_DBCOUNT = {}        # process-lifetime cache: {db_path: ref_fts row count}

_CAND = 20           # candidates each ranker contributes before fusion
_RRF_K = 60          # standard RRF damping constant


def _load_index(cfg: RetrievalCfg):
    """(vecs, rowids, n_rows_stamp) or None. Cache is keyed by index PATH (bug found
    2026-07-25: an unkeyed cache served the first-loaded index to every later config)."""
    key = str(cfg.index_path)
    if key not in _DENSE:
        if not cfg.index_path.exists():
            return None
        import numpy as np
        data = np.load(cfg.index_path, allow_pickle=False)
        stamp = int(data["n_rows"]) if "n_rows" in data.files else None
        _DENSE[key] = (data["vecs"], data["rowids"], stamp)
    return _DENSE[key]


def _db_row_count(cfg: RetrievalCfg) -> int | None:
    key = str(cfg.db_path)
    if key not in _DBCOUNT:
        try:
            conn = sqlite3.connect(f"file:{cfg.db_path}?mode=ro", uri=True)
            try:
                _DBCOUNT[key] = int(conn.execute("SELECT COUNT(*) FROM ref_fts").fetchone()[0])
            finally:
                conn.close()
        except Exception:
            _DBCOUNT[key] = None
    return _DBCOUNT[key]


_STALE_WARNED: set[str] = set()


def index_freshness(cfg: RetrievalCfg) -> dict:
    """{stamp, live, stale} — stale is None when it cannot be determined.

    A10 (2026-08-02): ref_dense_v1 was built at 5,608 rows while ref_fts had grown to 5,638.
    Thirty chunks were invisible to the dense ranker for the entire five-model showdown and
    nothing in the pipeline noticed. An index that cannot prove its own freshness is an
    unrecorded variable, so the stamp now travels inside the artifact and is checked here.
    """
    idx = _load_index(cfg)
    stamp = idx[2] if idx else None
    live = _db_row_count(cfg)
    stale = None if (stamp is None or live is None) else (stamp != live)
    if stale and str(cfg.index_path) not in _STALE_WARNED:
        _STALE_WARNED.add(str(cfg.index_path))
        print(f"WARNING: dense index STALE — {cfg.index_path.name} built at {stamp} rows, "
              f"ref_fts now has {live}. Rebuild: python -m harness.embed_index")
    return {"stamp": stamp, "live": live, "stale": stale}


def _dense_ranked(cfg: RetrievalCfg, text: str, limit: int) -> list[int]:
    """rowids ranked by cosine similarity, best first. [] if index/model unavailable."""
    idx = _load_index(cfg)
    if idx is None:
        return []
    if "model" not in _DENSE:
        from sentence_transformers import SentenceTransformer
        _DENSE["model"] = SentenceTransformer("BAAI/bge-m3", device="cpu")
    vecs, rowids, _ = idx
    q = _DENSE["model"].encode([text[:6000]], normalize_embeddings=True,
                               convert_to_numpy=True)[0]
    sims = vecs @ q                      # cosine similarity (both sides L2-normalized)
    top = sims.argsort()[::-1][:limit]
    return [int(rowids[i]) for i in top]


def _fetch_rows(cfg: RetrievalCfg, rowids: list[int]) -> dict[int, tuple[str, str]]:
    """title+text for each rowid in one query."""
    if not rowids:
        return {}
    conn = sqlite3.connect(f"file:{cfg.db_path}?mode=ro", uri=True)
    try:
        marks = ",".join("?" * len(rowids))
        return {r[0]: (r[1] or "", r[2] or "") for r in conn.execute(
            f"SELECT rowid, title, text FROM ref_fts WHERE rowid IN ({marks})", rowids)}
    finally:
        conn.close()


def _snippets_for(cfg: RetrievalCfg, ordered_rowids: list[int],
                  query_text: str) -> tuple[list[RefSnippet], list[int]]:
    """RefSnippets in fused order, every hit windowed from FULL TEXT by the same extractor.

    Returns (snippets, missing_rowids). A11: the old version silently dropped any rowid it
    could not resolve, so a top-ranked hit could vanish from the pool without a trace and
    top_k=3 would quietly serve 2. Missing ids are now returned and recorded — a rowid the
    dense index knows but ref_fts does not IS index drift, and the caller should see it.
    """
    rows = _fetch_rows(cfg, ordered_rowids)
    terms = [t.strip('"') for t in query_terms(query_text)]
    out, missing = [], []
    for rid in ordered_rowids:
        if rid not in rows:
            missing.append(rid)
            continue
        title, text = rows[rid]
        out.append(RefSnippet(rid, title, extract_window(
            text, terms, cfg.snippet_max_chars, cfg.snippet_window_lead_frac)))
    return out, missing


def retrieve_with_meta(cfg: RetrievalCfg, text: str) -> tuple[list[RefSnippet], dict]:
    """retrieve() plus the provenance every result row now carries (audit C5).

    Nothing about retrieval was recorded before 2026-08-02: which mode actually ran, which
    index, how fresh, whether hybrid silently fell back to BM25 because the index was
    missing. Cells that differed in retrieval were compared as if they had not.
    """
    meta = {"retrieval_mode": cfg.mode, "mode_used": cfg.mode, "top_k": cfg.top_k,
            "index_path": cfg.index_path.name, "index_mtime": None, "index_stale": None,
            "index_n_rows": None, "dense_fallback": False, "missing_rowids": [],
            "n_bm25": 0, "n_dense": 0}

    if cfg.mode == "bm25":                    # retrieval-v1, byte-frozen
        rows = _bm25_ranked(cfg, text, cfg.top_k)
        meta["n_bm25"] = len(rows)
        return ([RefSnippet(r["rowid"], r["title"] or "", r["snip"][:cfg.snippet_max_chars])
                 for r in rows], meta)

    if cfg.index_path.exists():
        meta["index_mtime"] = int(cfg.index_path.stat().st_mtime)
    fresh = index_freshness(cfg)
    meta["index_stale"], meta["index_n_rows"] = fresh["stale"], fresh["stamp"]

    bm25 = _bm25_ranked(cfg, text, _CAND)
    dense = _dense_ranked(cfg, text, _CAND)
    meta["n_bm25"], meta["n_dense"] = len(bm25), len(dense)

    if not dense:                             # index absent -> graceful v1 ranking, RECORDED
        meta["mode_used"], meta["dense_fallback"] = "bm25_fallback", True
        snips, missing = _snippets_for(cfg, [r["rowid"] for r in bm25[:cfg.top_k]], text)
        meta["missing_rowids"] = missing
        return snips, meta

    scores: dict[int, float] = {}
    for rank, r in enumerate(bm25):
        scores[r["rowid"]] = scores.get(r["rowid"], 0.0) + 1.0 / (_RRF_K + rank + 1)
    for rank, rid in enumerate(dense):
        scores[rid] = scores.get(rid, 0.0) + 1.0 / (_RRF_K + rank + 1)
    fused = sorted(scores, key=scores.get, reverse=True)[:cfg.top_k]
    snips, missing = _snippets_for(cfg, fused, text)
    meta["missing_rowids"] = missing
    return snips, meta


def retrieve(cfg: RetrievalCfg, text: str) -> list[RefSnippet]:
    """Top-k reference snippets for an eval prompt, or [] when nothing matches.

    mode="bm25": retrieval-v1 exactly (Syed's build, preserved for audit/repro) — including
    its FTS token snippet, so historical cells stay reproducible byte-for-byte.
    mode="hybrid" (default since 2026-07-22): BM25 top-20 and BGE-M3 cosine top-20 fused by
    Reciprocal Rank Fusion — score(doc) = sum over rankers of 1/(60 + rank). RRF needs no
    tuned weights and rewards documents both rankers like, while letting either ranker
    alone carry a hit the other missed (the paraphrase case BM25 can't see). Falls back to
    pure BM25 when the dense index hasn't been built.

    Since 2026-08-02 every hybrid hit is windowed from full text by extract_window().
    """
    return retrieve_with_meta(cfg, text)[0]
