"""Offline CLI for the deterministic tuning layer — mirrors corpus_pipeline/cli.py ergonomics.

  python -m ecutune.cli --status                      # config + active clamp pipeline / stages
  python -m ecutune.cli --run-convergence [--seed N]  # the one-command offline proof
  python -m ecutune.cli --generate-eval-cases 10      # sim-eval cases -> ml/eval/data/*.jsonl
  python -m ecutune.cli --score-sim-eval PATH --baseline rules|random
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .algorithms import STAGE_REGISTRY
from .core.config import load_config
from .safety import CLAMP_PIPELINE

REPO_ROOT = Path(__file__).resolve().parents[2]   # .../MLECU
DEFAULT_EVAL_OUT = REPO_ROOT / "ml" / "eval" / "data" / "sim_cases_v1.jsonl"


def _run_convergence(seed: int, rom: str | None = None) -> int:
    from .simulation.harness import CONVERGENCE_TOL_PCT, run_convergence
    seeded = None
    if rom:
        from .simulation.rom_seed import fxt_rom_into_ej20x
        believed, truth, op, report = fxt_rom_into_ej20x(rom)
        seeded = (believed, truth, op)
        s = report["seed"]
        print(f"ROM-seeded from {Path(rom).name} (internal id {report['internal_id']})")
        print(f"  believed injector flow : {s['flow_cc_min']:.2f} cc/min")
        print(f"  believed latency @14.1V: {s['latency_ms_at_14v']:.3f} ms")
        print(f"  hot idle target (ROM)  : {s['hot_idle_target_rpm']:.0f} rpm")
    r = run_convergence(seed=seed, seeded=seeded)
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


def _rom_diff(path_a: str, path_b: str) -> int:
    from .platforms.subaru_ecuflash import TO_PLATFORM, VARIANTS
    from .romread import EcuFlashDefs
    from .romread.diff import byte_only_diff, diff_roms, format_report
    from .simulation.rom_seed import DEFAULT_DEFS, SIBLING_DEFS
    defs = EcuFlashDefs(DEFAULT_DEFS)
    try:
        d = diff_roms(path_a, path_b, defs, list(SIBLING_DEFS), TO_PLATFORM, VARIANTS)
    except ValueError as e:
        # Reconciliation can refuse on a heavily modified image ("refusing to guess").
        # The byte-level diff needs no defs and is always available — degrade to it.
        print(f"semantic decode failed ({e}); falling back to byte-level diff only")
        d = byte_only_diff(path_a, path_b)
    print(format_report(d))
    return 0 if d.is_identical else 2      # exit 2 = differences found (scriptable)


def _rom_report(rom: str | None) -> int:
    from .platforms.subaru_ecuflash import TO_PLATFORM, VARIANTS
    from .romread import EcuFlashDefs, RomImage, read_semantic_tables
    from .simulation.rom_seed import DEFAULT_DEFS, DEFAULT_ROM, SIBLING_DEFS
    path = rom if rom and rom != "DEFAULT" else str(DEFAULT_ROM)
    image = RomImage.load(path)
    defs = EcuFlashDefs(DEFAULT_DEFS)
    tables, report = read_semantic_tables(image, defs, list(SIBLING_DEFS), TO_PLATFORM, VARIANTS)
    print(f"ROM {Path(path).name} — internal id {report['internal_id']}")
    print(f"read via sibling defs {report['def_ids']} (411D has no community def)")
    for sid, t in tables.items():
        v = t.values
        head = (f"{float(v):.3f}" if v.ndim == 0
                else f"shape={v.shape} range [{v.min():.2f} .. {v.max():.2f}]")
        print(f"  {sid:28s} {t.kind:9s} {head:38s} {t.units:30s} {report['provenance'][sid]}")
    return 0


def _status() -> int:
    cfg = load_config()
    print("ecutune — offline deterministic ECU-tuning layer")
    print(f"  safety.max_ve_step : {cfg.safety.max_ve_step}  (+/-{cfg.safety.max_ve_step * 100:.0f}% per iteration)")
    print(f"  safety.afr_floor   : {cfg.safety.afr_floor}")
    print(f"  clamp pipeline     : {[c.__name__ for c in CLAMP_PIPELINE]}")
    print(f"  algorithm stages   : {list(STAGE_REGISTRY)}")
    return 0


def _generate_eval(n_per_fault: int, seed: int, out: str) -> int:
    from .evals import generate_cases, save_cases
    cases = generate_cases(n_per_fault, seed=seed)
    save_cases(cases, out)
    faults = sorted({c["fault"] for c in cases})
    print(f"wrote {len(cases)} cases ({n_per_fault}/fault x {len(faults)} faults, seed={seed}) -> {out}")
    return 0


def _score_eval(path: str, baseline: str, seed: int) -> int:
    from .evals import load_cases
    from .evals.scoring import run_baseline
    report = run_baseline(load_cases(path), baseline, seed=seed)
    print(f"baseline={baseline}")
    print(report.summary())
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ecutune", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-convergence", action="store_true",
                   help="run the offline idle-convergence harness and report the three guarantees")
    p.add_argument("--rom", nargs="?", const="DEFAULT", metavar="PATH",
                   help="seed the sim from a real ROM image (no PATH = the harvested "
                        "3B12504206/A2WC411D stock FXT ROM)")
    p.add_argument("--rom-report", action="store_true",
                   help="read + cross-validate the semantic table set from the ROM and print it")
    p.add_argument("--rom-diff", nargs=2, metavar=("ROM_A", "ROM_B"),
                   help="table-level + byte-level diff of two ROM images (exit 2 if they differ)")
    p.add_argument("--seed", type=int, default=0, help="RNG seed (default 0)")
    p.add_argument("--status", action="store_true", help="show config + active clamps/stages")
    p.add_argument("--generate-eval-cases", type=int, metavar="N",
                   help="generate N sim-eval cases per fault (JSONL)")
    p.add_argument("--eval-out", default=str(DEFAULT_EVAL_OUT),
                   help=f"eval-case output path (default {DEFAULT_EVAL_OUT})")
    p.add_argument("--score-sim-eval", metavar="PATH",
                   help="score a baseline against an eval-case JSONL")
    p.add_argument("--baseline", choices=("rules", "random"), default="rules")
    args = p.parse_args(argv)

    if args.run_convergence:
        rom = None
        if args.rom:
            from .simulation.rom_seed import DEFAULT_ROM
            rom = str(DEFAULT_ROM) if args.rom == "DEFAULT" else args.rom
        return _run_convergence(args.seed, rom)
    if args.rom_report:
        return _rom_report(args.rom)
    if args.rom_diff:
        return _rom_diff(args.rom_diff[0], args.rom_diff[1])
    if args.generate_eval_cases:
        return _generate_eval(args.generate_eval_cases, args.seed, args.eval_out)
    if args.score_sim_eval:
        return _score_eval(args.score_sim_eval, args.baseline, args.seed)
    if args.status:
        return _status()
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
