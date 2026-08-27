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


def _generate_eval(n_per_fault: int, seed: int, out: str, version: int = 1) -> int:
    from .evals import generate_cases, generate_cases_v2, save_cases
    gen = generate_cases_v2 if version == 2 else generate_cases
    cases = gen(n_per_fault, seed=seed)
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


_STAGE2_TRIM_TOL = 0.05   # +/-5% == the ROADMAP Stage-2 idle gate; within it, no change warranted

# identify() fault -> which fuel scalar the correction is attributed to (the "split" the proposer
# uses). None = not a table fix (a leak is mechanical; healthy needs no edit).
def _split_for_fault(fault_id: str):
    from .algorithms.fueling import ScalarSplit
    from .core.tables import FUEL_INJECTOR_FLOW, FUEL_INJECTOR_LATENCY, SENSOR_MAF_TRANSFER
    knob = {"maf_low": SENSOR_MAF_TRANSFER, "maf_high": SENSOR_MAF_TRANSFER,
            "injector_flow_lean": FUEL_INJECTOR_FLOW, "injector_flow_rich": FUEL_INJECTOR_FLOW,
            "injector_latency_lean": FUEL_INJECTOR_LATENCY}.get(fault_id)
    if knob is None:
        return None
    return ScalarSplit(w_latency=float(knob == FUEL_INJECTOR_LATENCY),
                       w_flow=float(knob == FUEL_INJECTOR_FLOW),
                       w_maf=float(knob == SENSOR_MAF_TRANSFER))


def _diagnose(holds: list[str], rom: str | None, independent_baseline: bool) -> int:
    """The log->layer bridge as a command: real CSV holds -> the deterministic layer's OWN diagnosis
    (and, only if it finds an actionable out-of-tolerance fault, the clamped proposal it would make).
    Claude does not read the logs here — `identify()` does."""
    import numpy as np

    from .algorithms import AlgoState, propose_idle_correction
    from .algorithms.identify import identify
    from .core.models import ClampContext
    from .logparse.binning import GridSpec, bin_log
    from .logparse.observe import observations_from_logs
    from .safety import apply_proposal
    from .simulation.mvem import MEASURED_MAF_BASELINE_20260816 as BASELINE
    from .simulation.mvem import EngineParams
    from .simulation.rom_seed import DEFAULT_ROM, fxt_rom_into_ej20x

    rom_path = rom if (rom and rom != "DEFAULT") else str(DEFAULT_ROM)
    believed, _truth, _op, _rep = fxt_rom_into_ej20x(rom_path)
    obs = observations_from_logs(holds, BASELINE, maf_term=independent_baseline)
    est = identify(believed, obs, EngineParams())

    print("=" * 74)
    print(f"DIAGNOSE — {len(holds)} holds, baseline {'INDEPENDENT' if independent_baseline else 'SELF-REFERENTIAL'} "
          f"({'; MAF-vs-flow resolvable' if independent_baseline else 'MAF term OFF — see caveat'})")
    print(f"{'hold':>18} {'air_scale':>10} {'volts':>7} {'trim%':>8} {'maf g/s':>8} {'nominal':>8}")
    for h, o in zip(holds, obs):
        nom = "—" if np.isnan(o.nominal_maf) else f"{o.nominal_maf:.2f}"
        print(f"{Path(h).stem:>18} {o.air_scale:>10.3f} {o.voltage:>7.2f} {o.trim*100:>8.2f} "
              f"{o.maf_reading:>8.2f} {nom:>8}")
    ranked = sorted(est.residuals.items(), key=lambda kv: kv[1])[:4]
    print("\nlayer verdict: fault=" + repr(est.fault_id) + f"  identifiable={est.identifiable}"
          + f"  margin={est.margin:.2f}")
    if est.reason:
        print("  reason: " + est.reason)
    print("  hypothesis ranking (residual, lower=better): "
          + ", ".join(f"{k} {v:.2e}" for k, v in ranked))

    max_trim = max(abs(o.trim) for o in obs)
    print(f"\nidle vs Stage-2 gate (±{_STAGE2_TRIM_TOL*100:.0f}% trim): worst |trim| = {max_trim*100:.2f}% "
          + ("→ WITHIN gate" if max_trim <= _STAGE2_TRIM_TOL else "→ OUT of gate"))
    if not independent_baseline:
        print("  CAVEAT: baseline was derived from THIS capture, so MAF-vs-injector-flow is not "
              "separable here\n          (the ratio is 1.0 by construction). Resolve with an "
              "independent baseline or a 3rd airflow point.")

    split = _split_for_fault(est.fault_id) if est.identifiable else None
    if est.identifiable and max_trim > _STAGE2_TRIM_TOL and split is not None:
        from .logparse.observe import _as_logtable
        cfg = load_config()
        warm_lt = _as_logtable(holds[0])
        warm_rpm = float(np.nanmean(warm_lt.get("rpm")))
        grid = bin_log(warm_lt, GridSpec(x_role="maf_gs", x_breaks=(obs[0].maf_reading,),
                                         y_breaks=(warm_rpm,)))
        prop, _ = propose_idle_correction(grid, believed, AlgoState(), cfg.algo, split,
                                          provenance="algorithm:idle_global_scalar",
                                          metadata={"fault": est.fault_id})
        ctx = ClampContext(believed, cfg.safety, fault_estimate=est)
        new_tables, res = apply_proposal(believed, prop, ctx)
        print("\nPIPELINE PROPOSAL (clamped; nothing written — for Syed's review):")
        print(f"  ok={res.ok}  aborted_by={res.aborted_by or '—'}")
        for e in prop.edits:
            print(f"    {e.table_id}: → {e.new_value:.4f}   ({e.reason})")
    else:
        print("\nPIPELINE PROPOSAL: none — " + (
            "idle within the Stage-2 gate; no change warranted" if max_trim <= _STAGE2_TRIM_TOL
            else "verdict is not an actionable single-table fault (leak/healthy/not-identifiable)"))
    print("=" * 74)
    return 0



def _tune_maf(drive_csvs: list[str], rom: str | None, out: str | None,
              report_out: str | None) -> int:
    """The full pipeline, end to end: ROM + drive logs -> a verified candidate image.

    ROM -> semantic tables -> bin the pooled logs on THIS ROM's MAF breakpoints -> the layer's
    own identify() second opinion -> stage -> clamps -> romwrite -> CHANGE REPORT. Nothing is
    written unless --out is given, and even then we emit a FILE: flashing stays a human act in
    ECUFlash (ROADMAP Phase E.5).
    """
    import numpy as np

    from .algorithms import MafState, grid_spec_for, propose_maf_correction
    from .core.models import ClampContext, TableSet
    from .core.tables import SENSOR_MAF_TRANSFER
    from .logparse.binning import bin_log
    from .logparse.romraider_csv import LogTable, parse_romraider_csv
    from .platforms.subaru_ecuflash import TO_PLATFORM, VARIANTS
    from .romread import EcuFlashDefs, RomImage, read_semantic_tables
    from .safety import apply_clamps, apply_proposal
    from .safety.romwrite import change_report, patch
    from .simulation.rom_seed import DEFAULT_DEFS, DEFAULT_ROM, SIBLING_DEFS

    cfg = load_config()
    rom_path = rom if (rom and rom != "DEFAULT") else str(DEFAULT_ROM)
    stock = Path(rom_path).read_bytes()
    defs = EcuFlashDefs(DEFAULT_DEFS)
    raw, rep = read_semantic_tables(RomImage(stock), defs, list(SIBLING_DEFS),
                                    TO_PLATFORM, VARIANTS)
    tables = TableSet(raw)
    maf = tables.get(SENSOR_MAF_TRANSFER)
    if maf is None:
        print("ROM has no MAF transfer table — cannot proceed")
        return 1

    logs = [parse_romraider_csv(c) for c in drive_csvs]
    roles = set().union(*[set(l.channels) for l in logs])
    pooled = LogTable({r: np.concatenate([l.channels.get(r, np.full(len(l), np.nan))
                                          for l in logs]) for r in roles})
    grid = bin_log(pooled, grid_spec_for(maf))
    counts = {SENSOR_MAF_TRANSFER: tuple(int(c) for c in grid.count.sum(axis=0))}

    prop, _ = propose_maf_correction(grid, tables, MafState(), cfg.algo)
    ctx = ClampContext(tables, cfg.safety, sensor_sample_counts=counts,
                       baseline_tables=tables)
    res = apply_clamps(prop, ctx)
    after, _ = apply_proposal(tables, prop, ctx)

    print(f"ROM {Path(rom_path).name} — {len(drive_csvs)} log(s), {len(pooled)} rows")
    print(f"  {int(grid.count.sum())} closed-loop steady samples over "
          f"{prop.metadata['n_confident_bins']} confident breakpoints")
    print(f"  proposal: {prop.metadata['n_corrected']}/{prop.metadata['n_breakpoints']} cells, "
          f"max measured {prop.metadata['max_measured_correction'] * 100:+.1f}% "
          f"(damping {prop.metadata['damping']})")
    print(f"  clamps: ok={res.ok} violations={len(res.violations)} "
          f"{sorted({v.action for v in res.violations})}")
    if not res.ok:
        print(f"  ABORTED BY {res.aborted_by} — nothing written")
        return 2

    w = patch(stock, res, raw, rep["resolved"])
    back, _ = read_semantic_tables(RomImage(w.data), defs, list(SIBLING_DEFS),
                                   TO_PLATFORM, VARIANTS)
    moved = [s for s in raw if s != SENSOR_MAF_TRANSFER
             and not np.array_equal(raw[s].values, back[s].values)]
    print(f"  wrote {sum(b - a for a, b in w.byte_ranges)} bytes in "
          f"{len(w.byte_ranges)} range(s); checksum records repaired {list(w.checksum_repaired)}")
    print(f"  read-back: other tables moved = {moved or 'none'}")

    md = change_report(prop, res, w, raw, back, rom_name=Path(rom_path).name)
    if report_out:
        Path(report_out).write_text(md)
        print(f"  change report -> {report_out}")
    else:
        print()
        print(md)
    if out:
        Path(out).write_bytes(w.data)
        print(f"  candidate image -> {out}  (NOT flashed; review the report first)")
    else:
        print("  (no --out given: nothing written to disk)")
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
    p.add_argument("--diagnose", nargs="+", metavar="HOLD_CSV",
                   help="the log->layer bridge: real RomRaider hold CSVs (warm first) -> the "
                        "deterministic layer's own diagnosis + any clamped proposal")
    p.add_argument("--independent-baseline", action="store_true",
                   help="with --diagnose: the MAF baseline is independent of these holds, so the "
                        "MAF-vs-flow term is trusted (default: self-referential, MAF term off)")
    p.add_argument("--seed", type=int, default=0, help="RNG seed (default 0)")
    p.add_argument("--status", action="store_true", help="show config + active clamps/stages")
    p.add_argument("--generate-eval-cases", type=int, metavar="N",
                   help="generate N sim-eval cases per fault (JSONL)")
    p.add_argument("--eval-out", default=str(DEFAULT_EVAL_OUT),
                   help=f"eval-case output path (default {DEFAULT_EVAL_OUT})")
    p.add_argument("--score-sim-eval", metavar="PATH",
                   help="score a baseline against an eval-case JSONL")
    p.add_argument("--baseline", choices=("rules", "rules_v2", "random"), default="rules")
    p.add_argument("--tune-maf", nargs="+", metavar="DRIVE_CSV",
                   help="ROM + drive logs -> clamped MAF transfer-curve correction -> verified "
                        "candidate image + CHANGE REPORT (nothing is flashed)")
    p.add_argument("--out", metavar="PATH", help="with --tune-maf: write the candidate ROM here")
    p.add_argument("--report-out", metavar="PATH",
                   help="with --tune-maf: write the change report here instead of stdout")
    p.add_argument("--eval-version", type=int, choices=(1, 2), default=1,
                   help="sim-eval generator version (2 = adds the voltage-sweep probe point)")
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
    if args.diagnose:
        return _diagnose(args.diagnose, args.rom, args.independent_baseline)
    if args.tune_maf:
        return _tune_maf(args.tune_maf, args.rom, args.out, args.report_out)
    if args.generate_eval_cases:
        return _generate_eval(args.generate_eval_cases, args.seed, args.eval_out,
                              args.eval_version)
    if args.score_sim_eval:
        return _score_eval(args.score_sim_eval, args.baseline, args.seed)
    if args.status:
        return _status()
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
