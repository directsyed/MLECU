"""Retrieved-document DIVERSITY over archived result files — the "doc-collapse" counter.

WHY (2026-08-15/16). The Qwen3.8 E1 runs retrieved only 4 distinct documents across all 70 cases,
two on 100% of queries. That number was computed ad hoc and never committed, so the obvious
follow-up — "did 3.6's ratified base+RAG@3 headline collapse the same way?" — had nothing to
reuse. This is that ~40 lines, committed. Retrieval is a pure function of (case prompt, index),
so this is a property of the corpus/query pairing, not of the model that answered.

Every E1/E2/E4 result row carries `retrieved_doc_ids` (list[int] == ref_fts rowid == document.id,
written at harness/e1.py, e2.py, e4.py; `[]` for the no-retrieval arms). Files back to 2026-07-08
have it. Later rows also carry `top_k`, `retrieval_mode`, `index_stale` — July rows do not, so k is
inferred from len(retrieved_doc_ids).

USAGE
    car/.venv/bin/python -m doc_collapse results/e1-armB-run1-20260724-184006.jsonl [more.jsonl ...]
    car/.venv/bin/python -m doc_collapse --glob 'results/e1-armB-*.jsonl' --top 5

Prints, per file: n rows, model tag, top-1 (answer == fault) where present, k (from row length),
distinct doc ids, distinct ordered id-tuples (and the dominant tuple's count), and the top-N docs
by fraction of queries containing them. `--json` emits the same as one JSON object per file.
"""
from __future__ import annotations

import argparse
import glob as globmod
import json
from collections import Counter
from pathlib import Path


def analyse(path: str | Path, top: int = 5) -> dict:
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    ids_per_row = [tuple(r.get("retrieved_doc_ids") or ()) for r in rows]
    with_ids = [t for t in ids_per_row if t]
    doc_counter: Counter = Counter()
    for t in with_ids:
        for d in set(t):                    # count a doc once per query
            doc_counter[d] += 1
    tuple_counter = Counter(with_ids)
    n_q = len(with_ids)
    scored = [r for r in rows if "answer" in r and "fault" in r]
    top1 = (sum(1 for r in scored if r["answer"] == r["fault"]) / len(scored)) if scored else None
    models = Counter(r.get("model") for r in rows)
    ks = Counter(len(t) for t in with_ids)
    return {
        "file": str(path),
        "n_rows": len(rows),
        "n_rows_with_retrieval": n_q,
        "model": models.most_common(1)[0][0] if models else None,
        "top1_pct": round(100 * top1, 1) if top1 is not None else None,
        "k": ks.most_common(1)[0][0] if ks else 0,
        "distinct_docs": len(doc_counter),
        "distinct_tuples": len(tuple_counter),
        "dominant_tuple": list(tuple_counter.most_common(1)[0][0]) if tuple_counter else [],
        "dominant_tuple_count": tuple_counter.most_common(1)[0][1] if tuple_counter else 0,
        "top_docs": [{"doc_id": d, "coverage_pct": round(100 * c / n_q, 1)}
                     for d, c in doc_counter.most_common(top)] if n_q else [],
    }


def fmt(a: dict) -> str:
    top = " · ".join(f"{t['doc_id']} {t['coverage_pct']}%" for t in a["top_docs"]) or "(none)"
    return (f"{Path(a['file']).name}\n"
            f"  rows={a['n_rows']} retrieval_rows={a['n_rows_with_retrieval']} model={a['model']} "
            f"top1={a['top1_pct']} k={a['k']}\n"
            f"  DISTINCT DOCS={a['distinct_docs']}  distinct id-tuples={a['distinct_tuples']} "
            f"(dominant x{a['dominant_tuple_count']}: {a['dominant_tuple']})\n"
            f"  top docs by query coverage: {top}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser("doc_collapse")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--glob", default=None)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    files = list(args.files) + (sorted(globmod.glob(args.glob)) if args.glob else [])
    if not files:
        ap.error("no files")
    for f in files:
        a = analyse(f, args.top)
        print(json.dumps(a) if args.json else fmt(a))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
