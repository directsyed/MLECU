"""Pair harvest — turn certified judge verdicts into the training-pair corpus.

Selection rule (Syed's blind metric ruling, 2026-07-05): pairs are harvested PER CHUNK from
chunks scoring >= keep_threshold under the current rubric, regardless of the doc's headline
score — and a pair must have a NON-EMPTY outcome (the safety signal; incomplete arcs are
honest but don't train outcome-grounded reasoning). Doc noise chunks never ride along.

Output: JSONL, one pair per line with full provenance (doc, chunk, scores, relevance, url)
so any training example can be traced to its exact source forever.
"""
from __future__ import annotations

import json
from pathlib import Path

from corpus_pipeline.core.state import State

from .config import Config


def harvest(state: State, cfg: Config, out_path: Path) -> dict:
    rows = state.conn.execute(
        """SELECT j.doc_id, j.chunk_index, j.n_chunks, j.score, j.pairs_json, j.relevance,
                  j.judge_model, j.rubric_version,
                  d.source, d.title, d.url, d.tier
           FROM judgment j JOIN document d ON d.id = j.doc_id
           WHERE j.rubric_version = ? AND j.score >= ? AND j.pairs_json IS NOT NULL
                 AND j.pairs_json != '[]'
           ORDER BY j.doc_id, j.chunk_index""",
        (cfg.rubric_version, cfg.judge.keep_threshold),
    ).fetchall()

    stats = {"chunks_seen": 0, "pairs_seen": 0, "pairs_kept": 0,
             "dropped_no_outcome": 0, "docs": set(), "by_relevance": {}}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for r in rows:
            stats["chunks_seen"] += 1
            for p in json.loads(r["pairs_json"]):
                stats["pairs_seen"] += 1
                if not (p.get("outcome") or "").strip():
                    stats["dropped_no_outcome"] += 1
                    continue
                rec = {
                    "symptoms": p.get("symptoms", ""), "diagnosis": p.get("diagnosis", ""),
                    "change": p.get("change", ""), "outcome": p["outcome"],
                    "provenance": {
                        "doc_id": r["doc_id"], "chunk_index": r["chunk_index"],
                        "chunk_score": r["score"], "source": r["source"],
                        "title": r["title"], "url": r["url"], "tier": r["tier"],
                        "relevance": r["relevance"], "judge_model": r["judge_model"],
                        "rubric_version": r["rubric_version"],
                    },
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                stats["pairs_kept"] += 1
                stats["docs"].add(r["doc_id"])
                rel = r["relevance"] or "unknown"
                stats["by_relevance"][rel] = stats["by_relevance"].get(rel, 0) + 1
    stats["docs"] = len(stats["docs"])
    return stats
