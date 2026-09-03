"""Pilot training-mix assembly, the last machine step before Syed's final C3 review.

Deterministic (no LLM): consumes drafts + classifications + organic harvest, applies the
agreed policy, emits the mix plus a composition report written to the hardened review
standard (needs census + what the mix does NOT provide).

Policy (DECISIONS-PENDING C1-C3 + Syed directives 2026-07-15):
  drop legacy_tech, drop shallow, drop grounding-flagged ids
  dedup near-duplicates (Jaccard>0.6 on symptoms+change), keep the deepest per cluster
  organic pairs ALWAYS included (gold)
  priority fill to cap: subaru > deficit-topic (maf/idle/ve_load/injectors) > deep > rest
  cap 400 total; report achieved subaru:general ratio vs the 70/30 doctrine target
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .config import MLECU

PAIRS_DIR = MLECU / "ml/curation/data/pairs"
DRAFTS = ("pairs-synthetic-draft.jsonl", "pairs-synthetic-draft-b2.jsonl",
          "pairs-synthetic-draft-b3.jsonl", "pairs-synthetic-draft-b4.jsonl")
FLAGGED = ("REVIEW-flagged.txt", "REVIEW-flagged-b2.txt", "REVIEW-flagged-b3.txt",
           "REVIEW-flagged-b4.txt")
ORGANIC = PAIRS_DIR / "pairs-rubric-r2.jsonl"
CLASSIFIED = PAIRS_DIR / "pairs-classified.jsonl"
CLASSIFIED_V2 = PAIRS_DIR / "pairs-classified-v2.jsonl"   # re-screen overlay (off_field aware)
OUT = PAIRS_DIR / "pilot-mix-v1.jsonl"
CAP = 400
DEFICIT_TOPICS = {"maf", "idle", "ve_load", "injectors"}
_DEPTH_RANK = {"deep": 2, "adequate": 1, "shallow": 0}


def _toks(p: dict) -> frozenset:
    return frozenset(re.findall(r"[a-z]{3,}", (p["symptoms"] + " " + p["change"]).lower()))


def assemble(cap: int = CAP, log=print) -> Path:
    flagged = set()
    for f in FLAGGED:
        fp = PAIRS_DIR / f
        if fp.exists():
            flagged |= {l.strip() for l in fp.open() if l.strip()}
    cls = {json.loads(l)["pair_id"]: json.loads(l) for l in CLASSIFIED.open() if l.strip()}
    if CLASSIFIED_V2.exists():                     # v2 re-screen verdicts override v1
        cls.update({json.loads(l)["pair_id"]: json.loads(l)
                    for l in CLASSIFIED_V2.open() if l.strip()})

    synth = []
    for f in DRAFTS:
        if not (PAIRS_DIR / f).exists():
            continue
        for l in (PAIRS_DIR / f).open():
            if l.strip():
                synth.append(json.loads(l))
    n_raw = len(synth)
    synth = [p for p in synth if p["pair_id"] not in flagged]
    synth = [p for p in synth if p["pair_id"] in cls
             and cls[p["pair_id"]]["relevance"] in ("subaru", "modern_general")
             and cls[p["pair_id"]]["depth"] != "shallow"]
    log(f"synthetic: {n_raw} raw -> {len(synth)} after flag/relevance/depth filters")

    # dedup: greedy clustering, keep the deepest (then longest) exemplar per cluster
    toks = [_toks(p) for p in synth]
    keep_idx: list[int] = []
    for i in range(len(synth)):
        merged = False
        for k, j in enumerate(keep_idx):
            inter = len(toks[i] & toks[j])
            union = len(toks[i] | toks[j])
            if union and inter / union > 0.6:
                ci, cj = cls[synth[i]["pair_id"]], cls[synth[j]["pair_id"]]
                better = (_DEPTH_RANK[ci["depth"]], len(synth[i]["diagnosis"])) > \
                         (_DEPTH_RANK[cj["depth"]], len(synth[j]["diagnosis"]))
                if better:
                    keep_idx[k] = i
                merged = True
                break
        if not merged:
            keep_idx.append(i)
    synth = [synth[i] for i in keep_idx]
    log(f"after dedup: {len(synth)}")

    organic = [json.loads(l) for l in ORGANIC.open() if l.strip()]
    for p in organic:
        p.setdefault("provenance", "organic")

    def prio(p):
        c = cls[p["pair_id"]]
        return (c["relevance"] == "subaru",
                c["topic"] in DEFICIT_TOPICS,
                _DEPTH_RANK[c["depth"]],
                len(p["diagnosis"]))
    synth.sort(key=prio, reverse=True)
    budget = max(0, cap - len(organic))
    chosen = synth[:budget]

    mix = organic + [dict(p, classification=cls[p["pair_id"]]) for p in chosen]
    with OUT.open("w") as f:
        for p in mix:
            f.write(json.dumps(p) + "\n")

    n_sub = sum(1 for p in chosen if cls[p["pair_id"]]["relevance"] == "subaru")
    from collections import Counter
    topics = Counter(cls[p["pair_id"]]["topic"] for p in chosen)
    log(f"MIX: {len(mix)} total = {len(organic)} organic + {len(chosen)} synthetic")
    log(f"  synthetic subaru: {n_sub} ({100*n_sub/max(1,len(chosen)):.0f}%), doctrine target 70% incl. organic")
    log(f"  synthetic topics: {topics.most_common()}")
    log(f"-> {OUT}")
    return OUT
