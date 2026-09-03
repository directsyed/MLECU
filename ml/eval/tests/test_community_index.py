"""Community index + per-parent cap machinery (2026-08-16), built INERT.

Syed's rulings: a SEPARATE community index, results tagged by tier, provenance preserved;
nothing indexed tonight; default retrieval must not change. So the load-bearing tests are:
  (a) with every new field at its default, retrieve_with_meta() is BYTE-IDENTICAL to before
      (ids, snippets, meta), proven on a tiny DB and, when the corpus is present, on the real
      DB in bm25 mode over real E1v2 prompts (no embedding model needed);
  (b) tier tagging survives to the result rows;
  (c) max_per_parent keeps at most N chunks per parent document, after fusion, before top-k,
      and records what it skipped;
  (d) community enabled but absent → falls back cleanly, never raises, reference rows unchanged.
Process caches (_DENSE/_DBCOUNT/_STALE_WARNED) are popped as test_snippets.py does.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

R = pytest.importorskip("harness.retrieval")
from harness.config import RetrievalCfg  # noqa: E402

REAL_DB = RetrievalCfg().db_path
REVERIFY = Path(__file__).resolve().parents[1] / "results" / "e1-armB-run1-20260802-215442.jsonl"


def _clear_caches(db, *paths):
    R._DBCOUNT.pop(str(db), None)
    for p in paths:
        R._DENSE.pop(str(p), None)
        R._STALE_WARNED.discard(str(p))


@pytest.fixture()
def db(tmp_path):
    """ref_fts (2 reference rows) + community_fts (2 rows) + a `document` table giving tier
    and source_id, with rowid == document.id as in the real corpus."""
    p = tmp_path / "corpus.sqlite"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE document (id INTEGER PRIMARY KEY, tier TEXT, source_id TEXT, "
              "title TEXT, text TEXT)")
    c.execute("CREATE VIRTUAL TABLE ref_fts USING fts5(title, text)")
    c.execute("CREATE VIRTUAL TABLE community_fts USING fts5(title, text)")
    rows = [
        (1, "reference", "books/Banish.pdf#p10", "B10", "boost target 18.5 psi wastegate"),
        (2, "reference", "books/Banish.pdf#p11", "B11", "boost target 19 psi wastegate duty"),
        (3, "reference", "books/Banish.pdf#p12", "B12", "boost target 20 psi wastegate spring"),
        (4, "reference", "books/Banish.pdf#p13", "B13", "boost target 21 psi wastegate line"),
        (5, "reference", "rusefi/idle.md", "IDLE", "boost target idle 750 rpm warm"),
        (6, "community", "lgt-thread-777", "smoke test found torn boot",
         "boost leak smoke test found a torn intake boot, trims went from +12 to +2"),
        (7, "community", "rr-thread-888", "MAF scaling after boost",
         "rescaled MAF after boost target change; injector latency 0.66"),
    ]
    for rid, tier, sid, title, text in rows:
        c.execute("INSERT INTO document VALUES (?,?,?,?,?)", (rid, tier, sid, title, text))
        table = "ref_fts" if tier == "reference" else "community_fts"
        c.execute(f"INSERT INTO {table}(rowid,title,text) VALUES (?,?,?)", (rid, title, text))
    c.commit()
    c.close()
    _clear_caches(p)
    return p


def _off(db, **kw):
    """A cfg with the community/cap fields present but at their OFF values."""
    return RetrievalCfg(db_path=db, mode="hybrid", top_k=3, index_path=Path("/nonexistent.npz"),
                        community_fts=None, community_index_path=None, community_top_k=0,
                        max_per_parent=0, **kw)


# ---------------------------------------------------------------- (a) byte-identical when OFF

def test_default_path_is_byte_identical_with_community_and_cap_fields_off(db):
    base = RetrievalCfg(db_path=db, mode="hybrid", top_k=3, index_path=Path("/nonexistent.npz"))
    q = "boost target wastegate psi"
    s1, m1 = R.retrieve_with_meta(base, q)
    s2, m2 = R.retrieve_with_meta(_off(db), q)
    assert [(s.ref_doc_id, s.title, s.snippet) for s in s1] == \
           [(s.ref_doc_id, s.title, s.snippet) for s in s2]
    assert m1 == m2
    # and none of the new meta keys leak into the default row
    for k in ("community_n", "community_top_k", "capped_out", "max_per_parent"):
        assert k not in m1
    # provenance is populated even in default mode (additive fields, no behaviour change)
    assert all(s.tier == "reference" for s in s1)
    assert s1[0].parent == "books/Banish.pdf"


def test_bm25_mode_row_shape_unchanged(db):
    cfg = RetrievalCfg(db_path=db, mode="bm25", top_k=2)
    snips, meta = R.retrieve_with_meta(cfg, "boost psi")
    assert meta["mode_used"] == "bm25" and "community_n" not in meta
    assert snips and snips[0].tier == "reference" and snips[0].parent == ""   # v1 path untouched


@pytest.mark.skipif(not (REAL_DB.exists() and REVERIFY.exists()), reason="corpus/results absent")
def test_real_corpus_bm25_ids_identical_with_new_fields_off():
    """Real DB, real E1v2 prompts (first 8), bm25 mode (no embedding model): the ids a
    default cfg returns must equal what a cfg with every new field explicitly OFF returns."""
    from harness.config import Config
    cases = Config().cases_path.parent / "sim_cases_v2.jsonl"
    if not cases.exists():
        pytest.skip("sim_cases_v2 absent")
    prompts = [json.loads(l)["prompt"] for l in cases.read_text().splitlines()[:8] if l.strip()]
    a = RetrievalCfg(mode="bm25", top_k=3)
    b = RetrievalCfg(mode="bm25", top_k=3, community_fts=None, community_top_k=0, max_per_parent=0)
    for p in prompts:
        assert [s.ref_doc_id for s in R.retrieve(a, p)] == [s.ref_doc_id for s in R.retrieve(b, p)]


@pytest.mark.skipif(os.environ.get("MLECU_HEAVY_TESTS") != "1",
                    reason="set MLECU_HEAVY_TESTS=1: loads bge-m3 and replays the reverify oracle")
def test_hybrid_replay_matches_the_reverify_oracle_file():
    """The strongest anchor: today's default hybrid retrieval must reproduce the ids recorded
    in the 2026-08-02 reverify file (post-fix) for the same prompts. Heavy (2.3 GB model)."""
    from harness.config import Config
    rows = [json.loads(l) for l in REVERIFY.read_text().splitlines() if l.strip()][:5]
    cases = {json.loads(l)["case_id"]: json.loads(l)["prompt"]
             for l in (Config().cases_path.parent / "sim_cases_v2.jsonl").read_text().splitlines()
             if l.strip()}
    cfg = RetrievalCfg(mode="hybrid", top_k=3)
    for r in rows:
        got = [s.ref_doc_id for s in R.retrieve(cfg, cases[r["case_id"]])]
        assert got == r["retrieved_doc_ids"], r["case_id"]


# ---------------------------------------------------------------- (b) tier tagging

def test_community_hits_are_appended_and_tagged_and_reference_rows_unchanged(db):
    q = "boost target wastegate psi smoke test torn boot"
    ref_only, m0 = R.retrieve_with_meta(_off(db), q)
    cfg = _off(db).__class__(**{**_off(db).__dict__, "community_fts": "community_fts",
                                "community_top_k": 2})
    snips, meta = R.retrieve_with_meta(cfg, q)
    ref_part = snips[:len(ref_only)]
    assert [(s.ref_doc_id, s.snippet) for s in ref_part] == \
           [(s.ref_doc_id, s.snippet) for s in ref_only]           # reference rows untouched
    comm = snips[len(ref_only):]
    assert comm and all(s.tier == "community" for s in comm)
    assert {s.ref_doc_id for s in comm} <= {6, 7}
    assert comm[0].parent in ("lgt-thread-777", "rr-thread-888")
    assert meta["community_n"] == len(comm) and meta["community_top_k"] == 2
    assert meta["community_fallback"] is None


# ---------------------------------------------------------------- (c) per-parent cap

def test_max_per_parent_caps_adjacent_chunks_and_records_the_skips(db):
    q = "boost target wastegate psi"
    uncapped, _ = R.retrieve_with_meta(_off(db), q)
    assert [s.parent for s in uncapped].count("books/Banish.pdf") >= 3   # the E2 failure shape
    cfg = RetrievalCfg(db_path=db, mode="hybrid", top_k=3, index_path=Path("/nonexistent.npz"),
                       max_per_parent=2)
    capped, meta = R.retrieve_with_meta(cfg, q)
    assert [s.parent for s in capped].count("books/Banish.pdf") <= 2
    assert len(capped) == 3                                   # still fills top-k
    assert 5 in [s.ref_doc_id for s in capped]                # the other parent gets in
    assert meta["max_per_parent"] == 2 and meta["capped_out"]  # skips are recorded


def test_take_top_is_a_plain_slice_when_cap_is_off(db):
    meta = {}
    assert R._take_top(_off(db), [4, 3, 2, 1, 5], 3, meta) == [4, 3, 2]
    assert "capped_out" not in meta


# ---------------------------------------------------------------- (d) enabled-but-absent

def test_community_enabled_but_index_absent_falls_back_cleanly(db, tmp_path):
    q = "boost target wastegate psi"
    ref_only, _ = R.retrieve_with_meta(_off(db), q)
    cfg = RetrievalCfg(db_path=db, mode="hybrid", top_k=3, index_path=Path("/nonexistent.npz"),
                       community_fts="no_such_table", community_index_path=tmp_path / "no.npz",
                       community_top_k=2)
    snips, meta = R.retrieve_with_meta(cfg, q)
    assert [s.ref_doc_id for s in snips] == [s.ref_doc_id for s in ref_only]
    assert meta["community_n"] == 0 and "absent" in meta["community_fallback"]


def test_parent_key_rule():
    assert R._parent_of("books/Heywood.pdf#p612") == "books/Heywood.pdf"
    assert R._parent_of("Fuel-Overview.md") == "Fuel-Overview.md"
    assert R._parent_of("") == ""
