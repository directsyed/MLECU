"""Offline CLI for the deterministic tuning layer — mirrors corpus_pipeline/cli.py ergonomics.

  python -m ecutune.cli --status              # show config + the active clamp pipeline / stages
  python -m ecutune.cli --run-convergence     # the one-command offline proof (idle convergence)
  python -m ecutune.cli --run-convergence --seed 3
"""
from __future__ import annotations

import argparse
import sys

from .algorithms import STAGE_REGISTRY
from .core.config import load_config
from .safety import CLAMP_PIPELINE


def _run_convergence(seed: int) -> int:
    from .simulation.harness import CONVERGENCE_TOL_PCT, run_convergence
    r = run_convergence(seed=seed)
    ok = r.converged and r.clamp_violations == 0
    print(f"convergence run (seed={r.seed})")
    print(f"  start trim    : {r.trim_history[0]:+.2f}%")
    print(f"  final trim    : {r.trim_history[-1]:+.2f}%   (tolerance +/-{CONVERGENCE_TOL_PCT:.0f}%)")
    print(f"  converged     : {r.converged}")
    print(f"  iterations    : {r.iterations}")
    print(f"  clamp violations: {r.clamp_violations}")
    print(f"  trim history  : {[round(t, 2) for t in r.trim_history]}")
    print(f"  final scalars : {r.scalars}")
    print(f"  RESULT        : {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def _status() -> int:
    cfg = load_config()
    print("ecutune — offline deterministic ECU-tuning layer")
    print(f"  safety.max_ve_step : {cfg.safety.max_ve_step}  (+/-{cfg.safety.max_ve_step * 100:.0f}% per iteration)")
    print(f"  safety.afr_floor   : {cfg.safety.afr_floor}")
    print(f"  clamp pipeline     : {[c.__name__ for c in CLAMP_PIPELINE]}")
    print(f"  algorithm stages   : {list(STAGE_REGISTRY)}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ecutune", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-convergence", action="store_true",
                   help="run the offline idle-convergence harness and report the three guarantees")
    p.add_argument("--seed", type=int, default=0, help="RNG seed for the synthetic log (default 0)")
    p.add_argument("--status", action="store_true", help="show config + active clamps/stages")
    args = p.parse_args(argv)

    if args.run_convergence:
        return _run_convergence(args.seed)
    if args.status:
        return _status()
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
