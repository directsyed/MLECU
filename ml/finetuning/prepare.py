"""pilot-mix-v3 -> instruction dataset (SYED'S BUILD, 2026-07-22 QLoRA night).

Converts signed training pairs into chat-transcript examples for SFTTrainer, applying the
two rulings from tonight: the STRUCTURAL GATE (a pair whose user turn would be empty is
excluded from conversion — blank input teaches confident output from nothing, the opposite
of cite-or-decline) and the 10% STRATIFIED HOLDOUT (validation slice the trainer never
learns from; overfitting compass).

Output format: one JSON object per line, {"messages": [{role, content} x3]} — the shape
trl's SFTTrainer consumes directly.

Run tests:   car/.venv/bin/python -m pytest ml/finetuning/tests/test_prepare_syed.py -v
Run for real: car/.venv/bin/python ml/finetuning/prepare.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path

MLECU = Path(__file__).resolve().parents[2]
PAIRS = MLECU / "ml/curation/data/pairs/pilot-mix-v3.jsonl"
OUT_DIR = Path(__file__).resolve().parent / "data"
VAL_FRAC = 0.10
SEED = 0

# Deployment identity — the prompt the fine-tuned model will SERVE under (ratified by Syed
# 2026-07-22). NOT the E1 harness prompt: eval arms keep their own frozen fixture prompt
# per the single-variable arm protocol.
SYSTEM = (
    "You are an ECU tuning assistant for gasoline engine management. From datalog evidence "
    "and observed vehicle behavior, diagnose what is happening and propose what to change. "
    "Structure every answer as — Diagnosis: the causal chain from evidence to mechanism. "
    "Change: the specific adjustment to try. Expected result: what should measurably change "
    "if the diagnosis is right. Never invent calibration values: every number must come "
    "from the evidence provided or be flagged as needing measurement."
)


def format_assistant(pair: dict) -> str:
    """TODO(Syed) #1 — warm-up. Build the assistant turn from the pair's diagnosis, change,
    and outcome fields, in the ratified explicit structure:

        Diagnosis: <diagnosis>
        Change: <change>
        Expected result: <outcome>

    Exactly those three labels, each on its own line (separate with \\n). Strip each field's
    surrounding whitespace before use.
    Java translation: an f-string f"Diagnosis: {x}" is String.format("Diagnosis: %s", x);
    "\\n".join(list) is String.join("\\n", list).
    """
    raise NotImplementedError  # replace with your implementation


def to_example(pair: dict) -> dict | None:
    """TODO(Syed) #2 — the gate + assembly. Return None if the pair fails the structural
    gate: the user turn (the symptoms field) is missing, or empty after .strip().
    (Remember from your query_terms build: pair.get("symptoms") or "" handles both a
    missing key and a None value — then .strip() kills whitespace-only.)

    Otherwise return the chat example:
        {"messages": [
            {"role": "system",    "content": SYSTEM},
            {"role": "user",      "content": <stripped symptoms>},
            {"role": "assistant", "content": format_assistant(pair)},
        ]}
    Java translation: returning None here is returning null after a guard clause —
    `if (blank) return null;` — the caller filters the nulls.
    """
    raise NotImplementedError  # replace with your implementation


def stratum_key(pair: dict) -> str:
    """Provided. The stratification bucket: organic pairs group as 'organic'; synthetic
    pairs group by their classified topic (so no topic can vanish into the holdout)."""
    if isinstance(pair.get("provenance"), dict):
        return "organic"
    c = pair.get("classification") or {}
    return f"syn:{c.get('topic', 'unknown')}"


def stratified_split(items: list[tuple[str, dict]], val_frac: float = VAL_FRAC,
                     seed: int = SEED) -> tuple[list[dict], list[dict]]:
    """TODO(Syed) #3 — the meaty one. items is a list of (stratum, example) tuples.
    Return (train, val) lists of examples such that:
      - each stratum contributes round(len(stratum) * val_frac) examples to val
      - WHICH examples go to val is decided by shuffling each stratum's list with the
        seeded generator, then slicing — so the split is random but reproducible
      - nothing is lost or duplicated: len(train) + len(val) == len(items)

    Plan of attack:
      1. Group into a dict of stratum -> list of examples.
         Java: HashMap<String, List<Example>> with computeIfAbsent — in Python,
         groups.setdefault(stratum, []).append(ex)
      2. rng = random.Random(seed)  — ONE generator, created once, used for every stratum
         (Java: new Random(seed) + Collections.shuffle(list, rng)). Python: rng.shuffle(lst)
         shuffles IN PLACE and returns None — don't assign its result.
      3. Per stratum: n_val = round(len(lst) * val_frac); val gets lst[:n_val], train gets
         lst[n_val:]  (Java: subList — Python slices copy, no view aliasing to worry about).
      4. Iterate strata in sorted(groups) order so the result is deterministic even though
         dict insertion order depends on input order.
    """
    raise NotImplementedError  # replace with your implementation


def main() -> None:
    """Provided: load -> gate/convert -> split -> write -> report."""
    pairs = [json.loads(l) for l in PAIRS.open() if l.strip()]
    items, gated = [], []
    for p in pairs:
        ex = to_example(p)
        if ex is None:
            gated.append(p.get("pair_id", p.get("provenance", {}).get("title", "?")))
        else:
            items.append((stratum_key(p), ex))
    train, val = stratified_split(items)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, rows in (("train", train), ("val", val)):
        with (OUT_DIR / f"{name}.jsonl").open("w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    print(f"{len(pairs)} pairs -> {len(items)} pass gate ({len(gated)} gated out)")
    print(f"train {len(train)} / val {len(val)}  -> {OUT_DIR}/")
    print("gated:", gated)


if __name__ == "__main__":
    main()
