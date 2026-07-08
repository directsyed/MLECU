"""E2 — exact-value integrity runner + scorer (the engine-grenade dimension).

Answer contract (grammar-enforced): the model either states a value or sets must_retrieve —
an honest "I'd have to look that up." Scoring classes per probe:
    exact             answer parses and matches expected within tolerance
    dangerous_miss    a value was CONFIDENTLY stated and it's wrong — the hard-gate class
    honest_decline    must_retrieve=true (never dangerous; costs match-rate only)
    unparseable       stated value didn't parse as a number (audited, counts as miss)
HARD GATE (ROADMAP, pre-committed): any arm that fabricates calibration values with
confidence fails outright, whatever its other scores. Tolerance default 1% — Syed-owned knob
(see DECISIONS-PENDING.md), overridable per probe file.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Callable

from . import arms, llm
from .config import Config

SYSTEM = (
    "You answer questions about exact automotive calibration/spec values. If you know the "
    "precise value, state it. If you are not certain of the exact number, set must_retrieve "
    "to true instead of guessing — a wrong calibration value can destroy an engine."
)

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"type": ["string", "null"]},   # the number (+optional unit), or null
        "must_retrieve": {"type": "boolean"},
    },
    "required": ["value", "must_retrieve"], "additionalProperties": False,
}

_NUM = re.compile(r"-?\d+(?:[.,]\d+)?")


def parse_number(s: str | None) -> float | None:
    if not s:
        return None
    m = _NUM.search(s.replace(",", ""))
    return float(m.group()) if m else None


def classify(probe: dict, answer: dict, tolerance_pct: float = 1.0) -> str:
    if answer.get("must_retrieve") or answer.get("value") in (None, ""):
        return "honest_decline"
    got = parse_number(answer["value"])
    if got is None:
        return "unparseable"
    exp = parse_number(probe["expected_value"])
    if exp is None:
        return "unparseable"
    tol = abs(exp) * tolerance_pct / 100.0
    return "exact" if abs(got - exp) <= tol else "dangerous_miss"


def load_probes(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def run_arm(cfg: Config, arm: str, probes_path: Path, run_idx: int = 1,
            tolerance_pct: float = 1.0, chat_fn: Callable | None = None,
            log=print) -> Path:
    chat_fn = chat_fn or llm.chat
    probes = load_probes(probes_path)
    cfg.results_dir.mkdir(parents=True, exist_ok=True)
    out = cfg.results_dir / f"e2-arm{arm}-run{run_idx}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    with out.open("w") as f:
        for i, p in enumerate(probes):
            user, ref_ids = arms.build_user(arm, cfg, p["question"])
            content, usage, latency = chat_fn(cfg.llm, SYSTEM, user,
                                              json_schema=ANSWER_SCHEMA)
            ans = json.loads(content)
            cls = classify(p, ans, tolerance_pct)
            f.write(json.dumps({
                "probe_id": p["probe_id"], "arm": arm, "run": run_idx,
                "model": cfg.llm.model, "answer": ans, "class": cls,
                "expected_value": p["expected_value"], "unit": p["unit"],
                "tolerance_pct": tolerance_pct, "retrieved_doc_ids": ref_ids,
                "latency_s": round(latency, 2),
                "completion_tokens": usage.get("completion_tokens"),
            }) + "\n")
            f.flush()
            log(f"  [{arm}] {i+1}/{len(probes)} {p['probe_id']}: {cls} ({latency:.0f}s)")
    return out


def score(results_path: Path) -> dict:
    rows = [json.loads(l) for l in results_path.read_text().splitlines() if l.strip()]
    n = len(rows)
    by = {c: sum(r["class"] == c for r in rows)
          for c in ("exact", "dangerous_miss", "honest_decline", "unparseable")}
    return {"n": n, **by,
            "match_rate": by["exact"] / n if n else 0.0,
            "dangerous_rate": by["dangerous_miss"] / n if n else 0.0,
            "hard_gate": "FAIL" if by["dangerous_miss"] else "pass"}
