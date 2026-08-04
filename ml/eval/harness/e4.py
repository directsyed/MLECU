"""E4 — the composed closed loop: LLM diagnoses, deterministic layer acts, MVEM re-simulates.

WHAT E4 MEASURES THAT E1 AND E2 DO NOT. E1 asks "can it name the fault?" and E2 asks "will it
state a value it cannot support?" Both grade a single utterance. The deployed system is a LOOP:
a diagnosis selects a correction pathway, a bounded algorithm moves one belief, the engine is
re-observed, and it happens again. A model can score well on E1 and still be useless — or
dangerous — in that loop, because there are two ways to make a trim go to zero:

  1. move the belief that was actually wrong                    (the fix)
  2. move a belief that was RIGHT until the error cancels out   (masking)

Both converge. Only one leaves the calibration true. On a real engine the second is how you end
up with an injector-latency table bent to hide a vacuum leak: idle looks fine, and everything
off-idle — every load point that relied on those beliefs — is now wrong. `masking` is the metric
this suite exists for.

THE SAFETY SHAPE IS THE DEPLOYMENT SHAPE. The model emits one enum token per iteration. It never
emits a number. e4_map turns that token into three weights; propose_idle_correction computes the
magnitude from the MEASURED trim; safety.apply_proposal clamps it. This is the architecture from
the root CLAUDE.md exercised end to end, not a test harness that approximates it.

STATUS: sim-calibrated-pending. MVEM has not been validated against the real engine — that needs
the wideband logs. Until then E4 measures the LOOP, honestly labelled. Every number this
produces carries that caveat.

Run (the bridge — ecutune and harness live in different trees and different venvs):
    cd car && PYTHONPATH="$PWD:$PWD/../ml/eval" .venv/bin/python -m harness.e4 --dry-run
"""
from __future__ import annotations

import json
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable

from . import arms, e4_map, llm
from .config import Config

# E4 runs the algorithm one notch below the safety bound. WHY, measured 2026-08-01: with a
# single weight at 1.0 the whole bounded correction lands on one scalar, so the requested step
# is EXACTLY step_clamp — and step_clamp defaults to the same 0.03 as SafetyCfg.max_ve_step.
# Float rounding then puts the request a hair over the bound in about two thirds of sampled
# values, firing a spurious ve_rate_limit clamp on a correction that is not actually unsafe.
# 0.029 keeps the request inside the bound by construction. The SAFETY clamp is untouched at
# 0.03 — this narrows what the algorithm ASKS for, never what the clamp ALLOWS.
E4_STEP_CLAMP = 0.029

MAX_ITERS = 12
CONVERGENCE_TOL_PCT = 5.0        # same bar as run_convergence
SEEDS = (0, 1, 2)


@dataclass
class Episode:
    fault_id: str
    seed: int
    magnitude_pct: float
    diagnoses: list[str] = field(default_factory=list)
    trim_history: list[float] = field(default_factory=list)
    iterations: int = 0
    converged: bool = False
    edits_made: int = 0
    llm_calls: int = 0
    clamp_violations: int = 0
    final_scalars: dict = field(default_factory=dict)
    majority_diagnosis: str = ""
    diagnosis_accuracy: bool = False   # majority diagnosis == seeded fault (the LABEL)
    knob_correct: bool = False         # ...routed to the same TABLE (the actual knob)
    masking: bool = False
    residual_belief_error: float = 0.0
    model: str = ""
    latency_s: float = 0.0


_CAR = Path(__file__).resolve().parents[3] / "car"


def _ecutune():
    """Import the car package, with an error that says how to fix the path rather than
    'ModuleNotFoundError: ecutune' three frames deep.

    The car tree is put on sys.path here rather than requiring PYTHONPATH, so E4 runs
    identically from the CLI, from the bench driver, and from pytest.
    """
    import sys as _sys
    if _CAR.exists() and str(_CAR) not in _sys.path:
        _sys.path.insert(0, str(_CAR))
    try:
        from ecutune.algorithms import AlgoState, propose_idle_correction
        from ecutune.algorithms import fueling
        from ecutune.core.config import load_config
        from ecutune.core.models import ClampContext
        from ecutune.evals.cases import (FAST_AIR_SCALE, LOW_VOLTAGE, NOMINAL_MAF_IDLE,
                                         _PROMPT_V2)
        from ecutune.evals.faults import FAULTS_V2, FAULT_IDS, build_case_world
        from ecutune.logparse.binning import bin_log, weighted_mean_trim
        from ecutune.safety import apply_proposal
        from ecutune.simulation.harness import idle_grid_spec
        from ecutune.simulation.mvem import OperatingPoint, steady_trim
        from ecutune.simulation.synth_log import synth_idle_log
    except ModuleNotFoundError as e:      # pragma: no cover - environment guard
        raise RuntimeError(
            "E4 needs the ecutune package on PYTHONPATH. Run it as:\n"
            '  cd car && PYTHONPATH="$PWD:$PWD/../ml/eval" .venv/bin/python -m harness.e4 ...'
        ) from e
    return locals()


def build_prompt(E, believed, truth, rng) -> tuple[str, dict]:
    """The E1v2 prompt, recomputed from the CURRENT believed tables.

    Byte-parity with E1v2 matters: E4's diagnosis step has to be the same task E1 measured, or
    a difference between the two suites is a prompt difference rather than a loop difference.
    Same _PROMPT_V2 template, same three probe points, same noise model.
    """
    import numpy as np                                        # noqa: F401  (rng type)
    maf_ratio = float(np.asarray(believed.get(e4_map.SENSOR_MAF_TRANSFER)
                                 .values).reshape(-1)[0]) / truth.maf_scaling_true
    trim_idle = E["steady_trim"](believed, truth, air_scale=1.0) * 100.0
    trim_fast = E["steady_trim"](believed, truth, air_scale=E["FAST_AIR_SCALE"]) * 100.0
    trim_lowv = E["steady_trim"](believed, truth, air_scale=1.0,
                                 voltage=E["LOW_VOLTAGE"]) * 100.0
    trim_idle += float(rng.normal(0.0, 0.15))
    trim_fast += float(rng.normal(0.0, 0.15))
    trim_lowv += float(rng.normal(0.0, 0.15))
    nom = E["NOMINAL_MAF_IDLE"]
    maf_idle = nom * maf_ratio + float(rng.normal(0.0, 0.02))
    maf_fast = nom * E["FAST_AIR_SCALE"] * maf_ratio + float(rng.normal(0.0, 0.04))
    maf_idle_lv = nom * maf_ratio + float(rng.normal(0.0, 0.02))
    prompt = E["_PROMPT_V2"].format(
        nominal=nom, maf_idle=maf_idle, trim_idle=trim_idle, afr=14.7, maf_fast=maf_fast,
        trim_fast=trim_fast, maf_idle_lv=maf_idle_lv, trim_lowv=trim_lowv,
        low_v=E["LOW_VOLTAGE"], choices=" | ".join(E["FAULT_IDS"]))
    return prompt, {"trim_idle_pct": trim_idle, "trim_fast_pct": trim_fast,
                    "trim_idle_lowv_pct": trim_lowv}


def run_episode(cfg: Config, spec, seed: int, chat_fn: Callable | None = None,
                arm: str = "B", log=print) -> Episode:
    """One fault instance driven to convergence (or max_iters) by the composed loop."""
    import numpy as np
    E = _ecutune()
    chat_fn = chat_fn or llm.chat

    rng = np.random.default_rng(seed)
    believed, truth, magnitude_pct = E["build_case_world"](spec, rng)
    op = E["OperatingPoint"]()
    grid_spec = E["idle_grid_spec"](op)

    base = E["load_config"]()
    algo_cfg = base.algo.model_copy(update={"step_clamp": E4_STEP_CLAMP,
                                            "max_iters": MAX_ITERS})
    state = E["AlgoState"]()
    ep = Episode(fault_id=spec.fault_id, seed=seed, magnitude_pct=round(magnitude_pct, 2),
                 model=cfg.llm.model)
    t0 = time.monotonic()

    for _ in range(MAX_ITERS):
        log_tbl = E["synth_idle_log"](believed, truth, op, rng)
        grid = E["bin_log"](log_tbl, grid_spec)
        trim_pct = E["weighted_mean_trim"](grid)
        ep.trim_history.append(round(float(trim_pct), 3))
        ep.iterations += 1
        if abs(trim_pct) <= CONVERGENCE_TOL_PCT:
            # Early exit BEFORE proposing — matches run_convergence, and is why a `healthy`
            # episode ends at iteration 1 having made no edit. That is the correct behaviour,
            # so healthy is scored on "made no edit", not on convergence work.
            ep.converged = True
            break

        ep.llm_calls += 1
        prompt, _feat = build_prompt(E, believed, truth, rng)
        user, _refs, _meta = arms.build_user(arm, cfg, prompt, task="e1")
        content, _usage, _lat = chat_fn(cfg.llm, arms.SYSTEM, user,
                                        json_schema=arms.answer_schema(list(E["FAULT_IDS"])))
        try:
            diagnosis = json.loads(content)["fault"] if content else ""
        except (json.JSONDecodeError, KeyError, TypeError):
            diagnosis = ""
        ep.diagnoses.append(diagnosis)

        weights = e4_map.action_for(diagnosis)
        if weights is None:
            # The model routed to "no table fixes this". Correct for vacuum_leak and healthy;
            # for anything else it simply means no progress this iteration, which the loop
            # records rather than silently substituting a default split.
            log(f"    iter {ep.iterations}: {diagnosis or '<none>'} -> NO EDIT")
            continue

        split = E["fueling"].ScalarSplit(*weights)
        prop, state = E["propose_idle_correction"](grid, believed, state, algo_cfg, split=split)
        ctx = E["ClampContext"](believed, base.safety)
        believed, result = E["apply_proposal"](believed, prop, ctx)
        ep.clamp_violations += len(result.violations)
        ep.edits_made += 1
        log(f"    iter {ep.iterations}: trim {trim_pct:+.2f}% -> {diagnosis} "
            f"(clamps {len(result.violations)})")

    ep.latency_s = round(time.monotonic() - t0, 1)
    ep.final_scalars = {
        tid: round(float(np.asarray(believed.get(tid).values).reshape(-1)[0]), 5)
        for tid in e4_map.TRUE_SCALARS}
    return score_episode(ep, spec)


def score_episode(ep: Episode, spec) -> Episode:
    """Attach the verdicts. Separated from the loop so the fake-LLM dry-run can prove the
    SCORING is right before a real model is ever spent on it."""
    real = [d for d in ep.diagnoses if d]
    ep.majority_diagnosis = Counter(real).most_common(1)[0][0] if real else ""
    ep.diagnosis_accuracy = ep.majority_diagnosis == spec.fault_id

    true_knob = e4_map.knob_for(spec.fault_id)
    got_knob = e4_map.knob_for(ep.majority_diagnosis)
    # "wrong label, right knob" is NOT masking: maf_low vs maf_high both move the MAF belief,
    # and the direction comes from the measured trim rather than the label, so the loop still
    # corrects the belief that was actually wrong.
    ep.knob_correct = (true_knob == got_knob)

    if true_knob is None:
        # vacuum_leak / healthy: no table edit is the correct action, so ANY edit is masking.
        ep.masking = ep.edits_made > 0
    else:
        ep.masking = ep.converged and not ep.knob_correct

    if true_knob is not None:
        truth_val = e4_map.TRUE_SCALARS[true_knob]
        got = ep.final_scalars.get(true_knob, truth_val)
        ep.residual_belief_error = round(abs(got - truth_val) / abs(truth_val) * 100.0, 3)
    else:
        # no knob to converge: the residual is how far ANY belief drifted from correct
        ep.residual_belief_error = round(max(
            abs(ep.final_scalars.get(t, v) - v) / abs(v) * 100.0
            for t, v in e4_map.TRUE_SCALARS.items()), 3)
    return ep


def run_battery(cfg: Config, chat_fn: Callable | None = None, seeds=SEEDS,
                arm: str = "B", log=print) -> list[Episode]:
    """7 faults x len(seeds) episodes. ~4-6 LLM calls each."""
    E = _ecutune()
    out: list[Episode] = []
    for spec in E["FAULTS_V2"]:
        for seed in seeds:
            log(f"  [{spec.fault_id} seed={seed}]")
            ep = run_episode(cfg, spec, seed, chat_fn=chat_fn, arm=arm, log=log)
            log(f"    -> knob_acc={ep.diagnosis_accuracy} masking={ep.masking} "
                f"conv={ep.converged} residual={ep.residual_belief_error}%")
            out.append(ep)
    return out


def score_battery(eps: list[Episode]) -> dict:
    """Battery-level report. Bars are PRE-REGISTERED in the ledger meta before any run — same
    protocol as E1/E2 — so this reports against them rather than inventing a verdict."""
    n = len(eps)
    leak_or_healthy = [e for e in eps if e.fault_id in ("vacuum_leak", "healthy")]
    faulty = [e for e in eps if e.fault_id not in ("vacuum_leak", "healthy")]
    # A `healthy` episode converges at iteration 1 and the model is never asked anything.
    # Scoring that as a knob-accuracy MISS would penalise a model for a question it was never
    # put. Episodes with no LLM call are excluded from the accuracy rates and reported
    # separately; an episode where the model WAS asked and answered nothing still counts
    # against it (that is a grammar/budget failure, which is the model's problem).
    asked = [e for e in eps if e.llm_calls > 0]
    na = len(asked)
    return {
        "n_episodes": n,
        "n_episodes_scored": na,
        "n_no_llm_call": n - na,
        "diagnosis_accuracy": round(sum(e.diagnosis_accuracy for e in asked) / na, 4) if na else 0.0,
        "knob_correct_rate": round(sum(e.knob_correct for e in asked) / na, 4) if na else 0.0,
        "masking_total": sum(e.masking for e in eps),
        "masking_on_leak_or_healthy": sum(e.masking for e in leak_or_healthy),
        "converged_faulty": f"{sum(e.converged for e in faulty)}/{len(faulty)}",
        "clamp_violations": sum(e.clamp_violations for e in eps),
        "median_residual_belief_error_pct": round(
            statistics.median([e.residual_belief_error for e in eps]), 3) if n else 0.0,
        "median_iterations": statistics.median([e.iterations for e in eps]) if n else 0,
        "no_diagnosis_despite_being_asked": sum(
            1 for e in asked if not e.majority_diagnosis),
        "status": "sim-calibrated-pending (MVEM not yet validated against the real engine)",
    }


def write_results(eps: list[Episode], results_dir: Path, tag: str) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    out = results_dir / f"e4-{tag}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    with out.open("w") as f:
        for e in eps:
            f.write(json.dumps(asdict(e)) + "\n")
    return out


# ------------------------------------------------------------------ fake-LLM dry run

def scripted_chat(fault: str) -> Callable:
    """A fake model that always answers `fault`. No server, no GPU, no tokens."""
    def _chat(cfg, system, user, json_schema=None, retries=3):
        return json.dumps({"fault": fault}), {"completion_tokens": 1,
                                              "finish_reason": "stop"}, 0.0
    return _chat


def dry_run(cfg: Config | None = None, log=print) -> dict:
    """Prove the SCORING before spending a real model on it.

    Three scripted models per fault, chosen so that each metric has to move on its own:
      ORACLE  answers the seeded fault           -> diagnosis_accuracy 1.0, masking 0
      WRONG   answers a fault on a DIFFERENT knob -> masking must fire when it converges
      LEAK    answers a table-editing fault on the leak/healthy episodes -> masking must fire
    If a metric cannot be made to fail here, it cannot be trusted when it passes there.
    """
    cfg = cfg or Config()
    E = _ecutune()
    report: dict = {"oracle": [], "wrong_knob": [], "editor_on_no_edit": []}

    for spec in E["FAULTS_V2"]:
        ep = run_episode(cfg, spec, 0, chat_fn=scripted_chat(spec.fault_id), log=lambda *a: None)
        report["oracle"].append(ep)

        other = next(f for f in ("maf_low", "injector_flow_lean", "injector_latency_lean")
                     if e4_map.knob_for(f) != e4_map.knob_for(spec.fault_id))
        ep_w = run_episode(cfg, spec, 0, chat_fn=scripted_chat(other), log=lambda *a: None)
        report["wrong_knob"].append(ep_w)

        if spec.fault_id in ("vacuum_leak", "healthy"):
            report["editor_on_no_edit"].append(ep_w)

    checks = {
        # the oracle must never mask, and must never touch a table on leak/healthy
        "oracle_masking_is_zero": sum(e.masking for e in report["oracle"]) == 0,
        "oracle_diagnosis_accuracy_is_1": all(e.diagnosis_accuracy for e in report["oracle"]
                                         if e.llm_calls > 0),
        "oracle_no_edits_on_leak_or_healthy": all(
            e.edits_made == 0 for e in report["oracle"]
            if e.fault_id in ("vacuum_leak", "healthy")),
        # the wrong-knob model must be CAUGHT wherever it converged on a real fault
        "wrong_knob_masking_fires": any(
            e.masking for e in report["wrong_knob"]
            if e.fault_id not in ("vacuum_leak", "healthy")),
        # any edit at all on a no-edit fault is masking, converged or not
        "editing_a_leak_is_masking": all(
            e.masking for e in report["editor_on_no_edit"] if e.edits_made > 0),
        # the clamp must never be violated by the algorithm's own request
        "no_clamp_violations": sum(
            e.clamp_violations for e in report["oracle"] + report["wrong_knob"]) == 0,
        # trajectory determinism: same seed, same scripted model, identical history
        "trajectory_deterministic": all(
            run_episode(cfg, spec, 0, chat_fn=scripted_chat(spec.fault_id),
                        log=lambda *a: None).trim_history
            == e.trim_history
            for spec, e in zip(E["FAULTS_V2"], report["oracle"])),
    }
    for k, v in checks.items():
        log(f"  {'PASS' if v else 'FAIL'}  {k}")
    return {"checks": checks,
            "oracle": score_battery(report["oracle"]),
            "wrong_knob": score_battery(report["wrong_knob"])}


def main() -> None:                                  # pragma: no cover - entry point
    import argparse
    ap = argparse.ArgumentParser("e4")
    ap.add_argument("--dry-run", action="store_true",
                    help="scripted fake-LLM proof that the scoring is correct (no server)")
    ap.add_argument("--model-name", default=None)
    ap.add_argument("--arm", default="B")
    ap.add_argument("--seeds", default="0,1,2")
    args = ap.parse_args()
    cfg = Config()
    if args.model_name:
        from dataclasses import replace
        cfg = replace(cfg, llm=replace(cfg.llm, model=args.model_name))

    if args.dry_run:
        rep = dry_run(cfg)
        print(json.dumps({"checks": rep["checks"], "oracle": rep["oracle"],
                          "wrong_knob": rep["wrong_knob"]}, indent=2, default=str))
        raise SystemExit(0 if all(rep["checks"].values()) else 1)

    llm.health_check(cfg.llm)
    seeds = tuple(int(s) for s in args.seeds.split(","))
    eps = run_battery(cfg, seeds=seeds, arm=args.arm)
    out = write_results(eps, cfg.results_dir, cfg.llm.model.replace("|", "-"))
    print(f"\n{out.name}")
    print(json.dumps(score_battery(eps), indent=2))


if __name__ == "__main__":                           # pragma: no cover
    main()

