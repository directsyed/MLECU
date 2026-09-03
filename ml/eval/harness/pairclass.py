"""Pair classification, executes the hardened review standard (ml/CLAUDE.md, 2026-07-15).

Every synthetic pair gets judged on BOTH coupled axes: structural quality (depth of the
causal arc) AND fit to the project's CURRENT need (idle-tune-first, modern-ECU Subaru).
Output feeds the assembly pass: dedup -> drop legacy/shallow -> 70/30 stratify -> cap.
The classifier model never sees provenance, only the pair text; no source-prestige bias.
Resume-safe: appends, skips already-classified ids on restart.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from . import llm
from .config import Config, MLECU

SYSTEM = (
    "You grade training pairs for an ECU-tuning assistant. PROJECT CONTEXT: the current goal "
    "is making a modern MAF-metered, closed-loop Subaru idle and drive correctly, priority "
    "topics are MAF calibration, idle control, injector flow/latency, VE/load-model, fuel "
    "trims/AFR; ignition and boost matter later. OUT OF FIELD entirely (grade off_field): "
    "diesel calibration/fuel delivery, engine CONSTRUCTION or fabrication (porting, machining, "
    "part selection), combustion research and simulation mathematics (heat flux, radiation, "
    "chemical kinetics), emissions-lab regulation work, and vintage tech (carburetors, points) "
    " - anything a gasoline-ECU calibrator cannot act on with a laptop and a ROM editor. "
    "Grade BOTH axes independently and honestly."
)

_USER_TMPL = """Training pair:
symptoms: {symptoms}
diagnosis: {diagnosis}
change: {change}
outcome: {outcome}

Grade it:
- relevance: subaru (Subaru/EJ-FA specific), modern_general (transfers to any modern
  gasoline EFI engine AND is actionable via ECU calibration), legacy_tech (carburetors,
  points, vintage fitment), off_field (diesel, engine construction/machining, combustion
  research math, emissions-lab, not gasoline-ECU-calibration work)
- depth: deep (diagnosis states the causal mechanism and excludes alternatives; change names
  a specific parameter with direction/magnitude), adequate (correct arc, thinner reasoning),
  shallow (label-matching, 'fix by applying fix', restated outcome)
- topic: the single best fit"""

SCHEMA = {
    "type": "object",
    "properties": {
        "relevance": {"type": "string", "enum": ["subaru", "modern_general", "legacy_tech", "off_field"]},
        "depth": {"type": "string", "enum": ["deep", "adequate", "shallow"]},
        "topic": {"type": "string", "enum": [
            "afr_fueltrim", "ve_load", "ignition_knock", "maf", "injectors",
            "boost", "idle", "cams", "sensors", "fuel_type", "other"]},
        "reason": {"type": "string"},
    },
    "required": ["relevance", "depth", "topic", "reason"],
    "additionalProperties": False,
}

DRAFTS = (MLECU / "ml/curation/data/pairs/pairs-synthetic-draft.jsonl",
          MLECU / "ml/curation/data/pairs/pairs-synthetic-draft-b2.jsonl")
OUT = MLECU / "ml/curation/data/pairs/pairs-classified.jsonl"


def classify(cfg: Config, drafts=DRAFTS, out: Path = OUT, only_ids=None,
             chat_fn: Callable | None = None, log=print) -> Path:
    chat_fn = chat_fn or llm.chat
    pairs = []
    for f in drafts:
        pairs += [json.loads(l) for l in Path(f).open() if l.strip()]
    done = set()
    if out.exists():
        done = {json.loads(l)["pair_id"] for l in out.open() if l.strip()}
    with out.open("a") as f:
        for i, p in enumerate(pairs):
            if p["pair_id"] in done or (only_ids is not None and p["pair_id"] not in only_ids):
                continue
            try:
                content, usage, latency = chat_fn(
                    cfg.llm, SYSTEM,
                    _USER_TMPL.format(symptoms=p["symptoms"], diagnosis=p["diagnosis"],
                                      change=p["change"], outcome=p["outcome"]),
                    json_schema=SCHEMA)
                verdict = json.loads(content)
            except (llm.LlmError, json.JSONDecodeError, KeyError) as e:
                log(f"  [{i+1}/{len(pairs)}] {p['pair_id']}: FAILED ({e}), skipping")
                continue
            f.write(json.dumps({"pair_id": p["pair_id"], **verdict}) + "\n")
            f.flush()
            if (i + 1) % 50 == 0:
                log(f"  classified {i+1}/{len(pairs)}")
    log(f"classification -> {out}")
    return out
