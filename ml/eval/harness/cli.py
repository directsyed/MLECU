"""Eval CLI — mirrors judge.cli ergonomics.

  python -m harness.cli --run-e1 --arm B [--runs 2] [--limit N]   # run arm(s) on sim cases
  python -m harness.cli --score results/e1-armB-run1-*.jsonl      # score a results file
  python -m harness.cli --baselines                               # rules + random, no LLM
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import e1, e2, e2gen, llm
from .config import Config, EVAL_DIR


def main() -> None:
    p = argparse.ArgumentParser("eval-harness")
    p.add_argument("--run-e1", action="store_true")
    p.add_argument("--arm", default="B", help="A (base) or B (base+RAG)")
    p.add_argument("--runs", type=int, default=2, help="repeat count (determinism check)")
    p.add_argument("--limit", type=int, default=None, help="first N cases only (smoke)")
    p.add_argument("--score", type=Path, default=None, help="score a results JSONL")
    p.add_argument("--baselines", action="store_true", help="rules + random reference scores")
    p.add_argument("--gen-e2", action="store_true", help="draft E2 probes from reference keeps")
    p.add_argument("--run-e2", action="store_true", help="run an arm over the E2 probe file")
    p.add_argument("--probes", type=Path, default=EVAL_DIR / "data/e2_probes_draft.jsonl")
    p.add_argument("--tolerance", type=float, default=1.0, help="E2 match tolerance in %%")
    args = p.parse_args()
    cfg = Config()

    if args.gen_e2:
        llm.health_check(cfg.llm)
        e2gen.generate(cfg, limit=args.limit or 60)
        print("DRAFT ONLY — Syed spot-check required before any arm runs against it.")
        return

    if args.run_e2:
        llm.health_check(cfg.llm)
        out = e2.run_arm(cfg, args.arm, args.probes, tolerance_pct=args.tolerance)
        print(json.dumps(e2.score(out), indent=2))
        return

    if args.baselines:
        scoring = e1.load_scoring(cfg.scoring_py)
        cases = e1.load_cases(cfg.cases_path)
        for which in ("rules", "random"):
            print(f"[{which}]\n{scoring.run_baseline(cases, which).summary()}")
        return

    if args.score:
        print(e1.score_results(cfg, args.score).summary())
        return

    if args.run_e1:
        served = llm.health_check(cfg.llm)
        print(f"llama-server up, serving {served}")
        cases = e1.load_cases(cfg.cases_path, args.limit)
        print(f"E1: {len(cases)} cases, arm {args.arm}, {args.runs} run(s)")
        paths = [e1.run_arm(cfg, args.arm, k + 1, cases) for k in range(args.runs)]
        for path in paths:
            print(f"\n{path.name}:\n{e1.score_results(cfg, path).summary()}")
        if len(paths) >= 2:
            same, total = e1.determinism(paths[0], paths[1])
            print(f"\ndeterminism: {same}/{total} identical answers across runs 1-2")
        return

    p.print_help()


if __name__ == "__main__":
    main()
