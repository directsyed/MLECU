"""Snippet-extraction regression suite (2026-08-02, bench-integrity Phase 1).

Every test here is a bug that actually happened, or a contract clause that bug taught us.
The headline one: `snippet(ref_fts, 1, '', '', ' … ', 24)` emitted

    "… increases effective injector size by 11 … "

for probe e2-5723-1, and three models were scored `dangerous_miss` for quoting the "11" we
handed them. A benchmark that convicts a model for the harness's own truncation is measuring
the harness. The contract is now: no token is ever bisected, and no NUMBER is ever bisected.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import retrieval as R                                    # noqa: E402
from harness.config import RetrievalCfg                               # noqa: E402

# The real sentence from ref_fts rowid 5723, padded so the window has to cut somewhere.
PAD = "Filler sentence about calibration practice that carries no query terms. " * 40
REAL = ("As shown earlier, changing from 40-psi to 50-psi fuel pressure increases "
        "effective injector size by 11.8%. Ideally, this change is done prior to any "
        "PCM calibration.")
TERMS = ["injector", "pressure", "psi", "effective"]


def _numbers(s: str) -> list[str]:
    import re
    return re.findall(r"\d[\d.,]*%?", s)


# ---------------------------------------------------------------- the headline bug

def test_number_is_never_bisected_at_the_window_edge():
    """THE regression: '11.8%' must never come out as '11'."""
    for cap in range(200, 1400, 7):          # sweep the cut point across the whole sentence
        w = R.extract_window(PAD + REAL + PAD, TERMS, cap)
        assert "by 11 " not in w and not w.rstrip(" …").endswith("by 11"), \
            f"number bisected at cap={cap}: {w[-80:]!r}"
        if "11.8" in w:
            assert "11.8%" in w, f"percent sign severed at cap={cap}: {w[-80:]!r}"


def test_digit_run_split_by_a_space_survives_whole():
    """'30 000' must not emit as a bare '000' or a bare '30', PDF extraction routinely
    breaks thousands across a space, and half of it in the evidence pool is a number the
    source never states (which the citation guard would then happily 'ground')."""
    text = PAD + "the limiter is set to 30 000 rpm in this table. " + PAD
    for cap in range(200, 1200, 3):
        w = R.extract_window(text, ["limiter", "table", "rpm"], cap)
        if "000" in w:
            assert "30 000" in w, f"thousands run bisected at cap={cap}: {w!r}"


def test_trailing_percent_is_pulled_in():
    text = PAD + "measured swing was 11.8 % over the baseline run " + PAD
    for cap in range(200, 1200, 3):
        w = R.extract_window(text, ["swing", "baseline", "measured"], cap)
        if "11.8" in w:
            assert "11.8 %" in w


# ---------------------------------------------------------------- window contract

def test_no_token_is_ever_bisected():
    text = PAD + REAL + PAD
    whole = set(text.split())
    for cap in range(200, 1400, 11):
        w = R.extract_window(text, TERMS, cap).strip("… ").strip()
        toks = w.split()
        assert all(t in whole for t in toks[1:-1]), f"bisected token at cap={cap}"


def test_short_text_returned_whole_and_unmarked():
    t = "Target idle AFR 14.7:1 at 750 rpm."
    assert R.extract_window(t, ["idle"], 1200) == t
    assert "…" not in R.extract_window(t, ["idle"], 1200)


def test_elision_markers_mark_both_cuts():
    w = R.extract_window(PAD + REAL + PAD, TERMS, 400)
    assert w.startswith("… ") and w.endswith(" …")


def test_never_exceeds_the_cap_markers_included():
    """Syed's RAG acceptance test asserts len(snippet) <= snippet_max_chars, and it caught
    the first version of this function overshooting by 7 chars. The cap is hard."""
    for text in (PAD + REAL + PAD,
                 PAD + "the limiter is set to 30 000 rpm here. " + PAD,
                 "nospaces" * 500):
        for cap in range(120, 1400, 13):
            assert len(R.extract_window(text, TERMS, cap)) <= cap


def test_no_matching_terms_falls_back_to_chunk_head():
    text = "alpha beta gamma. " * 200
    w = R.extract_window(text, ["zzzz", "qqqq"], 300)
    assert w.startswith("alpha beta") and w.endswith(" …")


def test_empty_and_none_text():
    assert R.extract_window("", ["x"], 100) == ""
    assert R.extract_window(None, ["x"], 100) == ""


# ---------------------------------------------------------------- passage selection

def test_window_lands_on_the_densest_passage_not_the_first_term_hit():
    """Measured failure (2026-08-02): anchoring on the first term hit put probe e2-5723-1's
    window ~7,000 chars away from its answer, on a paragraph that merely mentioned one query
    word. The window must go where the QUESTION is addressed, not where a common word is."""
    decoy = "The mechanical linkage is described elsewhere. " + ("padding text here. " * 300)
    answer = ("Injector pressure scaling: raising fuel pressure from 40 psi to 50 psi "
              "increases effective injector flow by 11.8 percent.")
    w = R.extract_window(decoy + answer + (" tail filler." * 100),
                         ["injector", "pressure", "psi", "flow", "mechanical"], 600)
    assert "11.8" in w, f"window missed the dense passage: {w!r}"


def test_span_that_exceeds_the_window_is_centred_not_left_anchored():
    """Left-anchoring missed probe e2-2207-0's answer by 43 characters."""
    body = ("oxidize " + "x " * 200 + "particulate filter temperature "
            + "y " * 200 + " oxidize at 250 C on the surface")
    w = R.extract_window(body + (" z" * 400), ["oxidize", "particulate", "temperature",
                                               "filter", "surface"], 900)
    assert "250" in w


# ---------------------------------------------------------------- A11 / A10 plumbing

@pytest.fixture()
def tiny_db(tmp_path):
    db = tmp_path / "corpus.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE VIRTUAL TABLE ref_fts USING fts5(title, text)")
    conn.execute("INSERT INTO ref_fts(rowid,title,text) VALUES (1,'T1','boost target 18.5 psi')")
    conn.execute("INSERT INTO ref_fts(rowid,title,text) VALUES (2,'T2','idle 750 rpm warm')")
    conn.commit()
    conn.close()
    return db


def test_missing_rowids_are_reported_not_silently_dropped(tiny_db):
    """A11: the old _snippets_for dropped any rowid it could not resolve, so a top-ranked hit
    could vanish and top_k=3 would quietly serve 2, with nothing in the row to say so."""
    cfg = RetrievalCfg(db_path=tiny_db)
    snips, missing = R._snippets_for(cfg, [1, 999, 2], "boost psi idle")
    assert [s.ref_doc_id for s in snips] == [1, 2]
    assert missing == [999]


def test_index_freshness_flags_a_stale_stamp(tiny_db, tmp_path, capsys):
    """A10: ref_dense_v1 was built at 5,608 rows while ref_fts held 5,638 and nothing
    noticed for an entire five-model showdown."""
    np = pytest.importorskip("numpy")
    idx = tmp_path / "stale.npz"
    np.savez(idx, vecs=np.zeros((1, 4), dtype=np.float32),
             rowids=np.array([1], dtype=np.int64), n_rows=np.int64(1))
    cfg = RetrievalCfg(db_path=tiny_db, index_path=idx)
    R._DENSE.pop(str(idx), None)
    R._DBCOUNT.pop(str(tiny_db), None)
    R._STALE_WARNED.discard(str(idx))
    f = R.index_freshness(cfg)
    assert f == {"stamp": 1, "live": 2, "stale": True}
    assert "STALE" in capsys.readouterr().out


def test_index_freshness_passes_when_counts_agree(tiny_db, tmp_path):
    np = pytest.importorskip("numpy")
    idx = tmp_path / "fresh.npz"
    np.savez(idx, vecs=np.zeros((2, 4), dtype=np.float32),
             rowids=np.array([1, 2], dtype=np.int64), n_rows=np.int64(2))
    cfg = RetrievalCfg(db_path=tiny_db, index_path=idx)
    R._DENSE.pop(str(idx), None)
    R._DBCOUNT.pop(str(tiny_db), None)
    assert R.index_freshness(cfg)["stale"] is False


def test_bm25_mode_is_byte_frozen(tiny_db):
    """mode='bm25' must keep serving the FTS token snippet: every pre-2026-08-02 result was
    produced with it, and changing it would make those cells irreproducible."""
    cfg = RetrievalCfg(db_path=tiny_db, mode="bm25", top_k=2)
    snips, meta = R.retrieve_with_meta(cfg, "boost psi")
    assert meta["mode_used"] == "bm25" and meta["retrieval_mode"] == "bm25"
    assert snips and snips[0].ref_doc_id == 1


def test_hybrid_without_an_index_records_the_fallback(tiny_db, tmp_path):
    """The hybrid->BM25 degradation used to be completely silent."""
    cfg = RetrievalCfg(db_path=tiny_db, mode="hybrid", top_k=2,
                       index_path=tmp_path / "does-not-exist.npz")
    snips, meta = R.retrieve_with_meta(cfg, "boost psi")
    assert meta["dense_fallback"] is True and meta["mode_used"] == "bm25_fallback"
    assert snips and "18.5 psi" in snips[0].snippet
