"""Syed's RAG acceptance suite. SKIPS entirely until harness/retrieval.py exists;
when it does, these define "done". Run: .venv/bin/python -m pytest tests/test_rag_syed.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

retrieval = pytest.importorskip("harness.retrieval",
                                reason="harness/retrieval.py not built yet — Syed's project")

from harness import arms, e1                                        # noqa: E402
from harness.config import Config                                   # noqa: E402

CFG = Config()
CASES = e1.load_cases(CFG.cases_path)
needs_db = pytest.mark.skipif(not CFG.retrieval.db_path.exists(),
                              reason="corpus DB not present")


def test_query_terms_quoted_and_stopword_free():
    terms = retrieval.query_terms("the MAF reading and fuel trim at idle idle idle")
    assert '"idle"' == terms[0]                  # frequency-ranked, most-repeated first
    assert all(t.startswith('"') for t in terms) # quoted: bare FTS5 tokens are query syntax
    assert '"the"' not in terms                  # stopwords never reach the index


@needs_db
def test_retrieve_returns_snippets_with_provenance():
    snips = retrieval.retrieve(CFG.retrieval, CASES[0]["prompt"])
    assert snips, "a fuel-trim prompt must hit something in 3.8k kept reference chunks"
    assert len(snips) <= CFG.retrieval.top_k
    s = snips[0]
    assert s.ref_doc_id > 0 and s.snippet       # traceable to a corpus doc, non-empty text
    assert len(s.snippet) <= CFG.retrieval.snippet_max_chars


@needs_db
def test_arm_b_injects_reference_block():
    user, refs, _ = arms.build_user("B", CFG, CASES[0]["prompt"])
    assert refs, "arm B must report which doc ids it retrieved (audit trail)"
    assert "[REF " in user                       # the context block is present...
    assert CASES[0]["prompt"] in user            # ...and the case is intact within it


@needs_db
def test_arm_a_untouched_by_rag_build():
    # the single-variable discipline: A must remain the verbatim case, forever
    user, refs, _ = arms.build_user("A", CFG, CASES[0]["prompt"])
    assert user == CASES[0]["prompt"] and refs == []
