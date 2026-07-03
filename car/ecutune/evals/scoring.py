"""Scoring + reference baselines for the sim-generated diagnostic eval.

score() is evaluee-agnostic: it takes {case_id: answer} and reports
  * top1        — answered exactly the seeded fault
  * acceptable  — answer within the case's acceptable set (credits genuine degeneracies:
                  leak vs dead-time cannot be separated without a voltage sweep)
Baselines bracket the eval: random ~= chance (floor); rules = the two-point signature logic a
competent tuner applies (ceiling for non-LLM methods — the LLM must at least match it):
  constant-fraction trim across airflow -> scaling fault (MAF reading tells MAF vs injector-flow);
  trim that SHRINKS with airflow -> constant-absolute fault (leak / dead time).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class EvalReport:
    n: int
    top1: float
    acceptable: float
    per_fault: dict = field(default_factory=dict)   # fault_id -> {n, top1, acceptable}

    def summary(self) -> str:
        lines = [f"cases: {self.n}   top1: {self.top1:.1%}   acceptable: {self.acceptable:.1%}"]
        for fid, m in sorted(self.per_fault.items()):
            lines.append(f"  {fid:<24} n={m['n']:<3} top1={m['top1']:.0%} acceptable={m['acceptable']:.0%}")
        return "\n".join(lines)


def score(cases: list[dict], answers: dict[str, str]) -> EvalReport:
    per: dict[str, dict] = {}
    top1 = acc = 0
    for c in cases:
        a = (answers.get(c["case_id"]) or "").strip()
        m = per.setdefault(c["fault"], {"n": 0, "top1": 0, "acceptable": 0})
        m["n"] += 1
        if a == c["fault"]:
            top1 += 1
            m["top1"] += 1
        if a in c["acceptable"]:
            acc += 1
            m["acceptable"] += 1
    n = len(cases)
    for m in per.values():
        m["top1"] = m["top1"] / m["n"]
        m["acceptable"] = m["acceptable"] / m["n"]
    return EvalReport(n, top1 / n if n else 0.0, acc / n if n else 0.0, per)


# --- baselines ---------------------------------------------------------------------------

HEALTHY_TRIM_TOL = 3.0     # |idle trim| under this -> healthy
MAF_DEV_TOL = 0.03         # |reading/nominal - 1| over this -> MAF transfer fault
CONSTANT_RATIO = 0.80      # trim_fast/trim_idle above this -> constant-fraction (scaling) fault


def rules_baseline(case: dict) -> str:
    f = case["features"]
    trim_i, trim_f = f["trim_idle_pct"], f["trim_fast_pct"]
    maf_dev = f["maf_gs_idle"] / f["nominal_maf_idle"] - 1.0
    if abs(trim_i) < HEALTHY_TRIM_TOL:
        return "healthy"
    if maf_dev < -MAF_DEV_TOL:
        return "maf_low"
    if maf_dev > MAF_DEV_TOL:
        return "maf_high"
    ratio = trim_f / trim_i if trim_i else 1.0
    if trim_i > 0:
        return "injector_flow_lean" if ratio > CONSTANT_RATIO else "vacuum_leak"
    return "injector_flow_rich"


def random_baseline(case: dict, rng: random.Random) -> str:
    return rng.choice(case["choices"])


def run_baseline(cases: list[dict], which: str, seed: int = 0) -> EvalReport:
    rng = random.Random(seed)
    if which == "rules":
        answers = {c["case_id"]: rules_baseline(c) for c in cases}
    elif which == "random":
        answers = {c["case_id"]: random_baseline(c, rng) for c in cases}
    else:
        raise ValueError(f"unknown baseline {which!r}")
    return score(cases, answers)
