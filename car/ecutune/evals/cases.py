"""Eval-case generation: fault world -> two-point datalog summary -> prompt + ground truth.

A case is a plain JSON dict (JSONL on disk) so ANY evaluee — the rules baseline today, the
fine-tuned/RAG LLM later — consumes the identical contract:
  in:  case["prompt"]  (universal channel vocabulary, no platform names)
  out: one fault id from case["choices"]
Ground truth (fault, magnitude, acceptable set) rides along for the scorer. `features` carries the
raw numbers so deterministic baselines don't have to parse prose.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..simulation.mvem import (FAST_AIR_SCALE, LOW_VOLTAGE, NOMINAL_MAF_IDLE,
                               steady_trim)
from .faults import FAULT_IDS, FAULTS, FAULTS_V2, build_case_world

VERSION = "sim_eval_v1"
VERSION_V2 = "sim_eval_v2"
# NOMINAL_MAF_IDLE / FAST_AIR_SCALE / LOW_VOLTAGE are re-exported from simulation.mvem, which
# is their canonical home (2026-08-05): they define the probe protocol the deterministic
# estimator and the real-car capture procedure both depend on, not just this eval.

_PROMPT = """You are diagnosing a fuel-trim problem on a port-injected gasoline engine \
(2.0 L flat-4, MAF-metered, closed-loop fueling at idle). Healthy baseline at warm idle \
(850 rpm): MAF reading ~{nominal:.2f} g/s, total fuel trim ~0%.

Datalog summary:
- Warm idle (850 rpm): MAF reading {maf_idle:.2f} g/s, total fuel trim (ST+LT) {trim_idle:+.1f}%, \
wideband {afr:.1f} AFR (closed loop holding target), coolant 185 F, knock retard 0.
- Fast idle (~1500 rpm, ~2x airflow): MAF reading {maf_fast:.2f} g/s, total fuel trim {trim_fast:+.1f}%.

Choose the single most likely root cause from: {choices}.
Answer with just the identifier."""


def _one_case(idx: int, spec, rng: np.random.Generator) -> dict:
    believed, truth, magnitude_pct = build_case_world(spec, rng)
    maf_ratio = float(np.asarray(believed.get("sensor.maf_transfer").values).reshape(-1)[0]) \
        / truth.maf_scaling_true

    trim_idle = steady_trim(believed, truth, air_scale=1.0) * 100.0
    trim_fast = steady_trim(believed, truth, air_scale=FAST_AIR_SCALE) * 100.0
    # sensor/log noise (seeded, small) — keeps baselines honest without swamping signatures
    trim_idle += float(rng.normal(0.0, 0.15))
    trim_fast += float(rng.normal(0.0, 0.15))
    maf_idle = NOMINAL_MAF_IDLE * maf_ratio + float(rng.normal(0.0, 0.02))
    maf_fast = NOMINAL_MAF_IDLE * FAST_AIR_SCALE * maf_ratio + float(rng.normal(0.0, 0.04))

    features = {
        "nominal_maf_idle": NOMINAL_MAF_IDLE,
        "maf_gs_idle": round(maf_idle, 3),
        "maf_gs_fast": round(maf_fast, 3),
        "trim_idle_pct": round(trim_idle, 2),
        "trim_fast_pct": round(trim_fast, 2),
        "wideband_afr": 14.7,
    }
    prompt = _PROMPT.format(nominal=NOMINAL_MAF_IDLE, maf_idle=maf_idle, trim_idle=trim_idle,
                            afr=14.7, maf_fast=maf_fast, trim_fast=trim_fast,
                            choices=" | ".join(FAULT_IDS))
    return {
        "version": VERSION,
        "case_id": f"{VERSION}-{idx:04d}",
        "fault": spec.fault_id,
        "magnitude_pct": round(magnitude_pct, 2),
        "acceptable": list(spec.acceptable),
        "choices": list(FAULT_IDS),
        "features": features,
        "prompt": prompt,
    }


def generate_cases(n_per_fault: int, seed: int = 0) -> list[dict]:
    """Deterministic: same (n_per_fault, seed) -> byte-identical cases."""
    rng = np.random.default_rng(seed)
    cases: list[dict] = []
    idx = 0
    for spec in FAULTS:
        for _ in range(n_per_fault):
            cases.append(_one_case(idx, spec, rng))
            idx += 1
    return cases


_PROMPT_V2 = """You are diagnosing a fuel-trim problem on a port-injected gasoline engine \
(2.0 L flat-4, MAF-metered, closed-loop fueling at idle). Healthy baseline at warm idle \
(850 rpm, charging at 14.0 V): MAF reading ~{nominal:.2f} g/s, total fuel trim ~0%.

Datalog summary:
- Warm idle (850 rpm, battery 14.0 V): MAF reading {maf_idle:.2f} g/s, total fuel trim (ST+LT) \
{trim_idle:+.1f}%, wideband {afr:.1f} AFR (closed loop holding target), coolant 185 F, knock retard 0.
- Fast idle (~1500 rpm, ~2x airflow, battery 14.0 V): MAF reading {maf_fast:.2f} g/s, total fuel \
trim {trim_fast:+.1f}%.
- Warm idle under heavy electrical load (850 rpm, battery sagged to {low_v:.1f} V): MAF reading \
{maf_idle_lv:.2f} g/s, total fuel trim {trim_lowv:+.1f}%.

Choose the single most likely root cause from: {choices}.
Answer with just the identifier."""


def _one_case_v2(idx: int, spec, rng: np.random.Generator) -> dict:
    believed, truth, magnitude_pct = build_case_world(spec, rng)
    maf_ratio = float(np.asarray(believed.get("sensor.maf_transfer").values).reshape(-1)[0]) \
        / truth.maf_scaling_true

    trim_idle = steady_trim(believed, truth, air_scale=1.0) * 100.0
    trim_fast = steady_trim(believed, truth, air_scale=FAST_AIR_SCALE) * 100.0
    trim_lowv = steady_trim(believed, truth, air_scale=1.0, voltage=LOW_VOLTAGE) * 100.0
    trim_idle += float(rng.normal(0.0, 0.15))
    trim_fast += float(rng.normal(0.0, 0.15))
    trim_lowv += float(rng.normal(0.0, 0.15))
    maf_idle = NOMINAL_MAF_IDLE * maf_ratio + float(rng.normal(0.0, 0.02))
    maf_fast = NOMINAL_MAF_IDLE * FAST_AIR_SCALE * maf_ratio + float(rng.normal(0.0, 0.04))
    maf_idle_lv = NOMINAL_MAF_IDLE * maf_ratio + float(rng.normal(0.0, 0.02))

    features = {
        "nominal_maf_idle": NOMINAL_MAF_IDLE,
        "maf_gs_idle": round(maf_idle, 3),
        "maf_gs_fast": round(maf_fast, 3),
        "trim_idle_pct": round(trim_idle, 2),
        "trim_fast_pct": round(trim_fast, 2),
        "trim_idle_lowv_pct": round(trim_lowv, 2),
        "battery_v_ref": 14.0,
        "battery_v_low": LOW_VOLTAGE,
        "wideband_afr": 14.7,
    }
    prompt = _PROMPT_V2.format(nominal=NOMINAL_MAF_IDLE, maf_idle=maf_idle, trim_idle=trim_idle,
                               afr=14.7, maf_fast=maf_fast, trim_fast=trim_fast,
                               maf_idle_lv=maf_idle_lv, trim_lowv=trim_lowv, low_v=LOW_VOLTAGE,
                               choices=" | ".join(FAULT_IDS))
    return {
        "version": VERSION_V2,
        "case_id": f"{VERSION_V2}-{idx:04d}",
        "fault": spec.fault_id,
        "magnitude_pct": round(magnitude_pct, 2),
        "acceptable": list(spec.acceptable),
        "choices": list(FAULT_IDS),
        "features": features,
        "prompt": prompt,
    }


def generate_cases_v2(n_per_fault: int, seed: int = 0) -> list[dict]:
    """v2: adds the low-voltage probe point; acceptable sets are exact-only (FAULTS_V2)."""
    rng = np.random.default_rng(seed)
    cases: list[dict] = []
    idx = 0
    for spec in FAULTS_V2:
        for _ in range(n_per_fault):
            cases.append(_one_case_v2(idx, spec, rng))
            idx += 1
    return cases


def save_cases(cases: list[dict], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")


def load_cases(path: str | Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
