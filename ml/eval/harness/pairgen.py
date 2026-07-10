"""Synthetic training-pair generator — the Phase-D pair-synthesis bridge (DRAFT-gated).

Drafts (symptoms -> diagnosis -> change -> outcome) pairs FROM judge-kept reference chunks:
the knowledge is real and judge-certified; the LLM only manufactures the packaging into
training-arc form, grounded in the excerpt it was shown. Every pair carries provenance
(`synthetic:<doc_id>`) and `spot_checked: false` — NOTHING here enters a training mix until
Syed signs knobs C1-C4 (DECISIONS-PENDING.md) and reviews his sample. The 80% synthetic-cap
and organic-displacement policy (C2) are applied at corpus-assembly time, not here.

Output schema mirrors the organic harvest exactly (C1 recommendation) so synthetic + organic
pairs are one dataset differing only in the provenance field.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Callable

from . import llm
from .config import Config, MLECU

SYSTEM = (
    "You write training examples for an automotive ECU-tuning assistant, grounded STRICTLY "
    "in a reference excerpt. Each example is a realistic tuning scenario: symptoms a tuner "
    "observes, the diagnosis, the concrete change made, and the outcome. Every number, table "
    "name, and causal claim must come from the excerpt — if the excerpt supports none, "
    "return an empty list. Never invent values."
)

_USER_TMPL = """Reference excerpt (title: {title}):

{text}

---
Write 0 to 2 training pairs grounded ONLY in this excerpt. Prefer Subaru-specific framing
when the excerpt supports it; otherwise stay platform-neutral. A pair without a concrete,
excerpt-supported outcome is worthless — omit it. The outcome must state what CHANGED as a
result of the change (a measurement, a behavior), never merely restate the action taken."""

PAIR_SCHEMA = {
    "type": "object",
    "properties": {"pairs": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "symptoms": {"type": "string"},
            "diagnosis": {"type": "string"},
            "change": {"type": "string"},
            "outcome": {"type": "string"},
        },
        "required": ["symptoms", "diagnosis", "change", "outcome"],
        "additionalProperties": False,
    }}},
    "required": ["pairs"], "additionalProperties": False,
}

OUT_DEFAULT = MLECU / "ml/curation/data/pairs/pairs-synthetic-draft.jsonl"


def candidate_docs(cfg: Config, limit: int) -> list[sqlite3.Row]:
    """keep>=4 single-chunk reference docs with digits and enough meat to ground a scenario."""
    conn = sqlite3.connect(f"file:{cfg.retrieval.db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """SELECT d.id, d.title, d.url, d.source, d.text, j.score
           FROM document d JOIN judgment j ON j.doc_id = d.id
           WHERE d.tier='reference' AND j.score >= 4 AND j.n_chunks = 1
             AND d.gone_at IS NULL AND d.text GLOB '*[0-9]*'
             AND length(d.text) >= 800
           ORDER BY (d.id * 2654435761) % 4294967296 LIMIT ?""", (limit,)).fetchall()
    # hash-scattered (same fix as e2gen — plain id order sampled only the earliest docs;
    # batch-1 review 2026-07-10)


def generate(cfg: Config, limit: int = 400, out: Path = OUT_DEFAULT,
             exclude_from: Path | None = None,
             chat_fn: Callable | None = None, log=print) -> Path:
    """exclude_from: an earlier draft JSONL — its source docs are skipped (batch increments)."""
    chat_fn = chat_fn or llm.chat
    out.parent.mkdir(parents=True, exist_ok=True)
    used: set[int] = set()
    if exclude_from and exclude_from.exists():
        used = {json.loads(l)['source']['doc_id'] for l in exclude_from.open() if l.strip()}
    docs = [d for d in candidate_docs(cfg, limit + len(used)) if d['id'] not in used][:limit]
    n_pairs = 0
    with out.open("w") as f:
        for i, d in enumerate(docs):
            try:
                content, usage, latency = chat_fn(
                    cfg.llm, SYSTEM,
                    _USER_TMPL.format(title=d["title"] or "untitled", text=d["text"][:12000]),
                    json_schema=PAIR_SCHEMA)
                pairs = json.loads(content)["pairs"] if content else []
            except (llm.LlmError, json.JSONDecodeError, KeyError) as e:
                log(f"  [{i+1}/{len(docs)}] doc {d['id']}: FAILED ({e}) — skipping")
                continue
            for k, pair in enumerate(pairs):
                n_pairs += 1
                f.write(json.dumps({
                    "pair_id": f"syn-{d['id']}-{k}", **pair,
                    "provenance": f"synthetic:{d['id']}",
                    "source": {"doc_id": d["id"], "title": d["title"], "url": d["url"],
                               "source": d["source"], "judge_score": d["score"]},
                    "generator_model": cfg.llm.model,
                    "generated_at": time.strftime("%F"), "spot_checked": False,
                }) + "\n")
            f.flush()
            log(f"  [{i+1}/{len(docs)}] doc {d['id']}: +{len(pairs)} pairs ({latency:.0f}s)")
    log(f"draft: {n_pairs} synthetic pairs from {len(docs)} docs -> {out}")
    return out
