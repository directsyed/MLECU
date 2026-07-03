"""Sim-generated diagnostic eval — known faults seeded in the MVEM, scored against ground truth.

Why this exists (ml/eval's objective teeth): every case's answer is KNOWN because we seeded the
fault, so the eval is contamination-free (no fine-tune can have memorized it — cases are generated,
not scraped), infinitely regenerable, and UNIVERSAL (prompts speak the generic channel vocabulary:
MAF g/s, fuel trim %, wideband AFR — no platform names). The future LLM evaluee consumes the same
JSONL contract the baselines do; RAG-vs-fine-tune both get measured here.

Deliberate honesty about degeneracy: at a single idle point, latency/flow/MAF/leak faults are
near-indistinguishable in the trim. Cases therefore include TWO operating points (warm idle +
fast idle at ~2x airflow), which separates constant-fraction faults (MAF transfer, injector flow)
from constant-absolute faults (dead time, vacuum leak) — the same multi-condition-logging doctrine
as the car tuning plan. Leak-vs-latency remains degenerate without a battery-voltage sweep (real
logging separates them); scoring handles that with acceptable-answer sets.
"""
from __future__ import annotations

from .cases import generate_cases, load_cases, save_cases
from .scoring import random_baseline, rules_baseline, score

__all__ = ["generate_cases", "save_cases", "load_cases", "score",
           "rules_baseline", "random_baseline"]
