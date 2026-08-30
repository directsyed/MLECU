"""Offline CLI for the deterministic tuning layer — mirrors corpus_pipeline/cli.py ergonomics.

  python -m ecutune.cli --status                      # config + active clamp pipeline / stages
  python -m ecutune.cli --run-convergence [--seed N]  # the one-command offline proof
  python -m ecutune.cli --generate-eval-cases 10      # sim-eval cases -> ml/eval/data/*.jsonl
  python -m ecutune.cli --score-sim-eval PATH --baseline rules|random
  python -m ecutune.cli --tune-maf LOG.csv... --rom ROM --baseline-rom STOCK --out CAND.bin
  python -m ecutune.cli --tune-timing LOG.csv... --rom ROM --baseline-rom STOCK --out CAND.bin
  python -m ecutune.cli --verify-flash CAND.bin --rom ROM --baseline-rom STOCK --expect timing
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
              report_out: str | None, baseline: str | None = None,
              ack_knock: bool = False, extrapolate: bool = False) -> int:
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
    from .logparse.signals import live_signals
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

    sig = live_signals(pooled, grid, cfg.safety)
    print(f"  live signals: knock onsets={sig.knock_onsets} (worst {sig.worst_knock_deg:+.2f} deg) "
          f"trims_converged={sig.fuel_trims_converged} steady={sig.steady_state_ok} "
          f"max|trim|={sig.max_trim_abs:.1%}")
    # The cumulative sensor envelope is measured against the ARCHIVED STOCK ROM, not against
    # the image being patched. Passing the current tables here would make the bound vacuous:
    # every iteration would be "0% from baseline" and the curve could walk forever.
    base_path = baseline or rom_path
    if base_path != rom_path:
        base_raw, _ = read_semantic_tables(RomImage(Path(base_path).read_bytes()), defs,
                                           list(SIBLING_DEFS), TO_PLATFORM, VARIANTS)
        baseline_tables = TableSet(base_raw)
        print(f"  cumulative envelope measured against {Path(base_path).name}")
    else:
        baseline_tables = tables
        print("  WARNING: no --baseline given; cumulative envelope is measured against the "
              "image being patched, which makes it inert")
    prop, _ = propose_maf_correction(grid, tables, MafState(), cfg.algo,
                                     baseline=baseline_tables if base_path != rom_path else None,
                                     extrapolate=extrapolate)
    kw = sig.as_context_kwargs()
    if ack_knock and kw["knock_active"]:
        # A HUMAN override, made at the command line, not something a proposal can claim for
        # itself. clamp_knock_auto_abort's exemption covers retard-only TIMING; a fuel or
        # sensor proposal has no such structural argument, so the only way past it is a person
        # stating that they have looked at the knock and judged the closed-loop steady evidence
        # uncontaminated by it. It is stamped into the proposal metadata and printed in the
        # change report, because an override nobody can see afterwards is not a review.
        print("  ** --ack-knock: HUMAN OVERRIDE of clamp_knock_auto_abort **")
        print(f"     {sig.knock_onsets} knock onset(s) in the samples this correction is built "
              f"from, worst {sig.worst_knock_deg:+.2f} deg.")
        print("     Recorded in the change report. A MAF correction is derived from mixture, "
              "not from spark,")
        print("     so knock does not corrupt the trim evidence -- but that is a judgement, "
              "and it is yours.")
        kw["knock_active"] = False
        prop.metadata["human_override"] = (
            f"--ack-knock: {sig.knock_onsets} onsets, worst {sig.worst_knock_deg:+.2f} deg")
    ctx = ClampContext(tables, cfg.safety, sensor_sample_counts=counts,
                       baseline_tables=baseline_tables,
                       sensor_extrapolation_ok=extrapolate, **kw)
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



def _pool_logs(drive_csvs: list[str]):
    """Parse and concatenate several RomRaider exports into one LogTable.

    A channel missing from one file is NaN-filled for that file's rows rather than dropped, so
    pooling a log that carries `Ignition Base Timing` with one that does not keeps both usable
    and leaves the gap visible as NaN instead of as a fabricated zero.
    """
    import numpy as np

    from .logparse.romraider_csv import LogTable, parse_romraider_csv

    logs = [parse_romraider_csv(c) for c in drive_csvs]
    roles = set().union(*[set(l.channels) for l in logs])
    pooled = LogTable({r: np.concatenate([l.channels.get(r, np.full(len(l), np.nan))
                                          for l in logs]) for r in roles})
    collisions = {}
    for l in logs:
        collisions.update(l.collisions)
    return logs, pooled, collisions


def _tune_timing(drive_csvs: list[str], rom: str | None, out: str | None,
                 report_out: str | None, baseline: str | None = None) -> int:
    """ROM + drive logs -> a clamped ignition-retard candidate image + CHANGE REPORT.

    Mirrors `_tune_maf`, with three differences that matter:

      * the log is binned on the TIMING MAP's own axes (load x rpm), so a binned cell and a
        `CellEdit(row, col)` are the same thing;
      * `require_closed_loop=False` -- open loop is where this car makes boost, and knock is
        measured identically in both;
      * the write uses `round_mode="no_greater"`, because Base Timing is uint8 at 0.3516
        deg/step and rounding to nearest could store up to +0.176 deg MORE ADVANCE than the
        clamps approved.

    Nothing is flashed. This emits a FILE for a human to review and write with FastECU.
    """
    from dataclasses import replace

    import numpy as np

    from .algorithms import (TimingState, grid_spec_for_timing, iam_deficit_degrees,
                             propose_timing_retard)
    from .core.models import ClampContext, TableSet
    from .core.tables import IGNITION_BASE_TIMING
    from .logparse.binning import bin_log
    from .logparse.signals import live_signals
    from .platforms.subaru_ecuflash import TO_PLATFORM, VARIANTS
    from .romread import EcuFlashDefs, RomImage, read_semantic_tables
    from .safety import apply_clamps, apply_proposal
    from .safety.romwrite import change_report, patch
    from .simulation.rom_seed import DEFAULT_DEFS, DEFAULT_ROM, SIBLING_DEFS

    cfg = load_config()
    rom_path = rom if (rom and rom != "DEFAULT") else str(DEFAULT_ROM)
    current = Path(rom_path).read_bytes()
    defs = EcuFlashDefs(DEFAULT_DEFS)
    raw, rep = read_semantic_tables(RomImage(current), defs, list(SIBLING_DEFS),
                                    TO_PLATFORM, VARIANTS)
    tables = TableSet(raw)
    timing = tables.tables.get(IGNITION_BASE_TIMING)
    if timing is None:
        print("ROM has no Base Timing map — cannot proceed")
        return 1

    logs, pooled, collisions = _pool_logs(drive_csvs)
    grid = bin_log(pooled, grid_spec_for_timing(timing, cfg.safety.min_sensor_samples))
    sig = live_signals(pooled, grid, cfg.safety)
    iam_deficit, iam_info = iam_deficit_degrees(pooled.get("iam"), cfg.safety, tables, timing)

    # FUEL convergence has to be judged on the grid the FUEL evidence lives on -- closed-loop,
    # binned on airflow -- not on this stage's open-loop-inclusive load x rpm grid. In open
    # loop the A/F correction is FROZEN (measured sd 0.04 vs 9.75 closed), so pooling those
    # samples reports a trim spread that is an artefact of the filter, not of the calibration.
    # The number that gates clamp_fuel_before_timing must mean what its name says.
    from .algorithms import grid_spec_for
    from .core.tables import SENSOR_MAF_TRANSFER
    fuel_sig = sig
    maf_table = tables.tables.get(SENSOR_MAF_TRANSFER)
    if maf_table is not None:
        fuel_sig = live_signals(pooled, bin_log(pooled, grid_spec_for(maf_table)), cfg.safety)
    sig = replace(sig, fuel_trims_converged=fuel_sig.fuel_trims_converged,
                  max_trim_abs=fuel_sig.max_trim_abs)

    print(f"ROM {Path(rom_path).name} — {len(drive_csvs)} log(s), {len(pooled)} rows")
    if collisions:
        print(f"  schema collisions resolved by schema.prefer(): "
              f"{ {k: len(v) for k, v in collisions.items()} }")
    print(f"  {int(grid.count.sum())} steady samples over {int((grid.count > 0).sum())} cells "
          f"({int(np.asarray(grid.confidence).sum())} confident, "
          f">= {cfg.safety.min_sensor_samples} samples)")
    print(f"  IAM: worst {iam_info['iam_worst']} vs reference {iam_info['iam_reference']} "
          f"[{iam_info['iam_reference_source']}] -> deficit "
          f"{iam_info['iam_deficit_fraction']:.3f} x advance authority "
          f"[{iam_info['iam_authority_source']}] = up to "
          f"{iam_info.get('iam_deficit_max_deg', 0.0):.2f} deg")
    print(f"  live signals: knock onsets={sig.knock_onsets} (worst {sig.worst_knock_deg:+.2f} deg) "
          f"trims_converged={sig.fuel_trims_converged} steady={sig.steady_state_ok} "
          f"max|trim|={sig.max_trim_abs:.1%}")

    prop, _ = propose_timing_retard(grid, tables, TimingState(), cfg.algo, cfg.safety,
                                    iam_deficit_deg=iam_deficit,
                                    metadata={"logs": [Path(c).name for c in drive_csvs]})

    base_path = baseline or rom_path
    if base_path != rom_path:
        base_raw, _ = read_semantic_tables(RomImage(Path(base_path).read_bytes()), defs,
                                           list(SIBLING_DEFS), TO_PLATFORM, VARIANTS)
        baseline_tables = TableSet(base_raw)
        print(f"  cumulative retard measured against {Path(base_path).name}")
    else:
        # REFUSED, not warned. For --tune-maf an inert cumulative envelope still leaves the
        # per-iteration displacement cap doing real work. Here it would leave the cumulative
        # retard floor as the ONLY bound below, and the ceiling only bounds above — so the
        # stage's own safety story would rest on `min_timing_advance` alone.
        print("  REFUSED: --tune-timing requires --baseline-rom (the archived stock ROM).")
        print("           Without it the cumulative retard floor is inert and the only bound")
        print("           below is the absolute min_timing_advance backstop.")
        return 2

    ctx = ClampContext(tables, cfg.safety, baseline_tables=baseline_tables,
                       cell_sample_counts={IGNITION_BASE_TIMING: grid.count},
                       **sig.as_context_kwargs())
    res = apply_clamps(prop, ctx)
    after_tables, _ = apply_proposal(tables, prop, ctx)

    m = prop.metadata
    print(f"  proposal: {m['n_edited']}/{m['n_cells']} cells "
          f"({m['n_evidence_driven']} evidence-driven, {m['n_ceiling_only']} ceiling-only), "
          f"worst pull {m['max_pull_deg']:.2f} deg")
    print(f"  clamps: ok={res.ok} surviving={len(res.clamped_edits)} "
          f"violations={len(res.violations)} {sorted({v.action for v in res.violations})}")
    if not res.ok:
        print(f"  ABORTED BY {res.aborted_by} — nothing written")
        return 2
    if not res.clamped_edits:
        print("  no edit survived the clamps — nothing to write")
        return 2

    w = patch(current, res, raw, rep["resolved"],
              round_modes={IGNITION_BASE_TIMING: "no_greater"})
    back, _ = read_semantic_tables(RomImage(w.data), defs, list(SIBLING_DEFS),
                                   TO_PLATFORM, VARIANTS)
    moved = [s for s in raw if s != IGNITION_BASE_TIMING
             and not np.array_equal(raw[s].values, back[s].values)]
    flashed = np.asarray(back[IGNITION_BASE_TIMING].values, float)
    stock_map = np.asarray(raw[IGNITION_BASE_TIMING].values, float)
    print(f"  wrote {sum(b - a for a, b in w.byte_ranges)} bytes in "
          f"{len(w.byte_ranges)} range(s); checksum records repaired {list(w.checksum_repaired)}")
    print(f"  read-back: other tables moved = {moved or 'none'}; "
          f"worst advance vs current {float(np.max(flashed - stock_map)):+.4f} deg "
          f"(must be <= 0)")

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



# --- pre-flash audit ---------------------------------------------------------------------
# Which semantic table a stage is allowed to move, and the checks that table's OWN physics
# demand. Before 2026-08-30 this was hardcoded to the MAF curve ("exactly one semantic table
# changed" asserted `moved == [SENSOR_MAF_TRANSFER]`, plus "strictly ascending" and
# `max_sensor_recal`), so a timing candidate got NO-GO on three checks that do not apply to it
# and skipped every check that does.
_FLASH_PROFILES = {
    "maf": "sensor.maf_transfer",
    "timing": "ignition.base_timing",
}


def _verify_flash(candidate: str, rom: str | None, baseline: str | None = None,
                  expect: str | None = None) -> int:
    """Pre-flash audit: prove a candidate image is safe to write, or refuse it.

    Every check is independent and every one must pass. This is the last automated gate before
    a human puts the file on an ECU, so it reports GO / NO-GO and nothing softer -- there is no
    "passed with warnings" state, because a warning on a flashable image is a defect.

    `rom` is the image being REPLACED (the one currently on the car), so per-iteration bounds
    are measured against it. `baseline` is the ARCHIVED STOCK ROM, so cumulative bounds are
    measured against that; it defaults to `rom`, which makes the cumulative checks vacuous and
    says so out loud rather than quietly passing.

    `expect` ("maf" | "timing") states which table the candidate is SUPPOSED to move. The audit
    determines the answer independently either way; supplying it turns "I flashed the wrong
    candidate file" from an undetected mistake into a NO-GO.
    """
    import hashlib

    import numpy as np

    from .platforms.subaru_ecuflash import TO_PLATFORM, VARIANTS
    from .romread import EcuFlashDefs, RomImage, read_semantic_tables
    from .safety.romwrite import checksum as ck
    from .safety.romwrite.encoder import quantisation_step
    from .safety.romwrite.patcher import _diff_ranges
    from .simulation.rom_seed import DEFAULT_DEFS, DEFAULT_ROM, SIBLING_DEFS

    rom_path = Path(rom if (rom and rom != "DEFAULT") else str(DEFAULT_ROM))
    stock, cand = rom_path.read_bytes(), Path(candidate).read_bytes()
    base_path = Path(baseline) if baseline else rom_path
    fails: list[str] = []

    # `fatal` is the subset of failures that mean the image cannot meaningfully be DECODED --
    # wrong size, another ECU's calibration ID, a rewritten boot region. Those short-circuit,
    # because reconciliation will refuse a foreign image and raise. Everything else is a real
    # failure that still produces a NO-GO, but not a reason to stop looking: a chained build
    # legitimately bases on a CANDIDATE rather than a ROM read off the car, so the
    # archived-checksum check fails on provenance while the image is perfectly decodable.
    fatal: list[str] = []

    def check(ok: bool, label: str, detail: str = "", is_fatal: bool = False) -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}{('  — ' + detail) if detail else ''}")
        if not ok:
            fails.append(label)
            if is_fatal:
                fatal.append(label)

    print(f"PRE-FLASH AUDIT\n  current   {rom_path.name}\n  candidate {Path(candidate).name}\n"
          f"  baseline  {base_path.name}"
          f"{'  (== current: CUMULATIVE CHECKS ARE INERT)' if base_path == rom_path else ''}\n")

    check(len(cand) == len(stock) == 1024 * 1024, "size is exactly 1,048,576 bytes",
          f"current {len(stock)}, candidate {len(cand)}", is_fatal=True)

    # The archived stock must be the one we actually read off THIS car.
    sums = rom_path.parent / "SHA256SUMS.txt"
    digest = hashlib.sha256(stock).hexdigest()
    if sums.exists():
        check(digest in sums.read_text(), "current image matches the archived SHA256SUMS",
              digest[:16] + ("" if digest in sums.read_text() else
                             "  (expected for a CHAINED build: the base is a candidate, "
                             "not a ROM read off the car — record it in SHA256SUMS.txt)"))
    else:
        print("  [ -- ] no SHA256SUMS.txt beside the current ROM (skipped)")

    # A calibration ID that moved means we patched the wrong thing entirely.
    check(stock[0x2000:0x2008] == cand[0x2000:0x2008], "calibration ID unchanged",
          cand[0x2000:0x2008].decode("ascii", "replace"), is_fatal=True)
    check(stock[:0x2000] == cand[:0x2000], "boot/vector region 0x0-0x1FFF untouched",
          is_fatal=True)

    # SHORT-CIRCUIT once IDENTITY is in doubt. Everything above answers "is this even the same
    # ECU's calibration?", and if the answer is no there is nothing to be gained by decoding it
    # -- reconciliation will refuse a foreign image ("defs disagree ... refusing to guess") and
    # raise, so the audit would die on a traceback instead of printing a verdict.
    #
    # Found 2026-08-30 by passing a REAL foreign ROM in as a candidate: a reference tune from
    # another car (AZ1E401A, an 08 WRX) against our A2WC411D. Every identity check fired
    # correctly and then the run crashed before reaching the summary. A person reading that
    # output has to interpret a Python stack trace to learn the answer is "do not flash this".
    # This is the last automated gate before a human touches an ECU; it owes a verdict, not an
    # exception.
    if fatal:
        print(f"\nNO-GO — {len(fatal)} check(s) failed before the image could even be decoded: "
              f"{fatal}")
        print("       This does not look like a calibration for THIS ECU. Refusing to go "
              "further.")
        return 2

    # Only now is it safe to diff: _diff_ranges raises on a size mismatch, so it has to sit
    # AFTER the size check has been allowed to fail the audit rather than before it.
    ranges = _diff_ranges(stock, cand)
    nbytes = sum(b - a for a, b in ranges)
    check(0 < len(ranges) < 64, f"{len(ranges)} changed byte-range(s), {nbytes} bytes total")

    defs = EcuFlashDefs(DEFAULT_DEFS)
    try:
        s_tab, s_rep = read_semantic_tables(RomImage(stock), defs, list(SIBLING_DEFS),
                                            TO_PLATFORM, VARIANTS)
        c_tab, _ = read_semantic_tables(RomImage(cand), defs, list(SIBLING_DEFS),
                                        TO_PLATFORM, VARIANTS)
        b_tab, _ = read_semantic_tables(RomImage(base_path.read_bytes()), defs,
                                        list(SIBLING_DEFS), TO_PLATFORM, VARIANTS)
    except ValueError as e:
        # romread refuses rather than guessing when sibling defs disagree and plausibility
        # cannot pick a winner. That refusal is correct; surfacing it as a crash is not.
        check(False, "the image decodes through our definition set", str(e)[:160])
        print(f"\nNO-GO — {len(fails)} check(s) failed: {fails}")
        return 2
    moved = [k for k in s_tab if not np.array_equal(s_tab[k].values, c_tab[k].values)]
    check(len(moved) == 1, "exactly one semantic table changed", str(moved) if moved else "none")
    if len(moved) != 1:
        print(f"\nNO-GO — {len(fails)} check(s) failed: {fails}")
        return 2
    target = moved[0]
    check(target in _FLASH_PROFILES.values(), "the changed table is one this layer tunes", target)
    if expect:
        check(_FLASH_PROFILES.get(expect) == target,
              f"changed table is the one --expect={expect} asked for", target)

    # Every changed byte must fall inside that table, or inside a checksum record's stored field.
    rd = s_rep["resolved"][target]
    n = np.asarray(s_tab[target].values).size
    lo, hi = rd.table_def.address, rd.table_def.address + n * rd.scaling.byte_size
    cks = {(r.offset + 8, r.offset + 12) for r in ck.read_records(stock)}
    stray = [r for r in ranges
             if not (lo <= r[0] and r[1] <= hi)
             and not any(a <= r[0] and r[1] <= b for a, b in cks)]
    check(not stray, f"every changed byte is inside {target} or a checksum field",
          f"table 0x{lo:X}-0x{hi:X}" if not stray else f"stray {stray[:3]}")

    check(ck.verify(cand) == [], "candidate satisfies its own SH7058 checksum")

    cur = np.asarray(c_tab[target].values, float)
    old = np.asarray(s_tab[target].values, float)
    base = np.asarray(b_tab[target].values, float)
    check(bool(np.all(np.isfinite(cur))), "every value is finite")
    sc = rd.scaling
    if sc.vmin is not None and sc.vmax is not None:
        check(bool(cur.min() >= sc.vmin - 1e-9 and cur.max() <= sc.vmax + 1e-9),
              f"every value inside the def's declared range [{sc.vmin}, {sc.vmax}]",
              f"{cur.min():.3f} .. {cur.max():.3f}")

    cfg = load_config()
    if target == "sensor.maf_transfer":
        curve = cur.ravel()
        check(bool(np.all(np.diff(curve) > 0)), "MAF curve is strictly ascending")
        check(bool(curve.min() > 0), "MAF curve positive",
              f"{curve.min():.2f} .. {curve.max():.2f} g/s")
        worst = float(np.max(np.abs(curve / old.ravel() - 1.0)))
        check(worst <= cfg.safety.max_sensor_recal + 1e-9,
              f"no cell exceeds max_sensor_recal ({cfg.safety.max_sensor_recal:.0%})",
              f"worst {worst:+.1%}")
        if base_path != rom_path:
            cum = float(np.max(np.abs(curve / base.ravel() - 1.0)))
            check(cum <= cfg.safety.sensor_envelope + 1e-9,
                  f"no cell exceeds sensor_envelope vs stock "
                  f"({cfg.safety.sensor_envelope:.0%})", f"worst {cum:+.1%}")

    elif target == "ignition.base_timing":
        from .algorithms import ceiling_grid  # noqa: F401  (used by the checks below)
        # RETARD ONLY. This is the property clamp_knock_auto_abort and clamp_fuel_before_timing
        # granted their exemptions on, so it is re-proved here against the actual BYTES rather
        # than trusted from the in-memory proposal.
        adv = cur - old
        check(bool(np.all(adv <= 1e-9)), "no cell is more advanced than the current ROM",
              f"worst advance {adv.max():+.4f} deg")

        # One storage step of slack, in the RETARD direction only: Base Timing is uint8 at
        # 0.3516 deg/step and the timing write rounds with "no_greater", so a value the clamp
        # allowed at exactly the 6 deg bound stores at most one LSB further retarded. The
        # excess can only ever be extra retard -- the advance check above is exact.
        step_tol = quantisation_step(sc, float(old.max())) + 1e-9
        moved_deg = float(np.max(np.abs(cur - old)))
        # A cell may exceed the step ONLY by landing on its own ceiling — that is the undriven-
        # cell exemption (Syed, 2026-08-30), and it is checkable from the image alone: the clamp
        # verified "never driven" against the log, and the bytes must show "arrived at the
        # ceiling". Anything that moved further than a step and did NOT land on its ceiling is
        # an unbounded pull, whatever produced it.
        ceil_here = ceiling_grid(s_tab[target], cfg.safety)
        big = np.abs(cur - old) > cfg.safety.max_timing_step + step_tol
        landed = np.abs(cur - np.maximum(ceil_here, cfg.safety.min_timing_advance)) <= step_tol
        check(bool(np.all(~big | landed)),
              f"every cell moved at most max_timing_step ({cfg.safety.max_timing_step} deg), or "
              "landed exactly on its ceiling",
              f"worst move {moved_deg:.4f} deg; {int(big.sum())} cell(s) beyond one step, "
              f"{int((big & ~landed).sum())} of them not on a ceiling")

        # NOT "every cell is at or below its ceiling" -- that is a post-condition of the whole
        # CONVERGED sequence, not of one pass. Syed ratified 6 deg per iteration precisely so
        # the map walks down to the ceiling over several drives, and the worst cell on this ROM
        # starts 18.12 deg above it, i.e. four passes away. Asserting the end state here would
        # NO-GO every iteration but the last.
        # The invariant that IS true of a single pass: a cell still above its ceiling may only
        # be there because the rate limit stopped it, never because it was passed over.
        ceil = ceiling_grid(s_tab[target], cfg.safety)
        above = cur > ceil + 1e-9
        stalled = above & ((old - cur) < cfg.safety.max_timing_step - step_tol)
        check(not bool(stalled.any()),
              "every cell still above its ceiling took a full rate-limited step",
              f"{int(above.sum())} cell(s) above ceiling, {int(stalled.any() and stalled.sum())} "
              f"of them not moving")
        if above.any():
            remaining = float(np.max((cur - ceil)[above]))
            print(f"  [ .. ] {int(above.sum())} cell(s) remain above their ceiling, worst by "
                  f"{remaining:.2f} deg — "
                  f"{int(np.ceil(remaining / cfg.safety.max_timing_step))} more iteration(s) "
                  f"at {cfg.safety.max_timing_step} deg/pass")

        if base_path != rom_path:
            retard = float(np.max(base - cur))
            check(retard <= cfg.safety.max_timing_retard + step_tol,
                  f"no cell is more than max_timing_retard ({cfg.safety.max_timing_retard} deg) "
                  "below stock", f"worst {retard:.4f} deg")
        n_moved = int(np.sum(np.abs(cur - old) > 1e-9))
        print(f"  [ .. ] {n_moved} of {cur.size} cells changed; "
              f"mean pull {float(np.mean(old - cur)):.3f} deg, worst {moved_deg:.3f} deg")

    print()
    if fails:
        print(f"NO-GO — {len(fails)} check(s) failed: {fails}")
        return 2
    print("GO — every check passed. The image is internally consistent and changes only what")
    print("     was approved. This says nothing about whether the CALIBRATION is right, only")
    print("     that the file is what we intended to build.")
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
    p.add_argument("--tune-timing", nargs="+", metavar="DRIVE_CSV",
                   help="ROM + drive logs -> clamped ignition-retard correction of Base Timing "
                        "-> verified candidate image + CHANGE REPORT (nothing is flashed)")
    p.add_argument("--out", metavar="PATH",
                   help="with --tune-maf / --tune-timing: write the candidate ROM here")
    p.add_argument("--verify-flash", metavar="CANDIDATE",
                   help="pre-flash audit of a candidate ROM against the current image "
                        "(GO/NO-GO; exit 2 on any failure)")
    p.add_argument("--expect", choices=("maf", "timing"),
                   help="with --verify-flash: which table the candidate is SUPPOSED to move. "
                        "The audit works it out either way; stating it turns 'wrong candidate "
                        "file' into a NO-GO instead of a silent pass")
    p.add_argument("--baseline-rom", metavar="PATH",
                   help="the ARCHIVED STOCK ROM that CUMULATIVE bounds are measured against "
                        "(not the image being patched): the sensor envelope for --tune-maf, "
                        "the retard floor for --tune-timing, and both under --verify-flash")
    p.add_argument("--extrapolate-maf", action="store_true",
                   help="with --tune-maf: extend the measured correction PLATEAU to breakpoints "
                        "ABOVE the measured airflow span. Off by default -- the stage's rule is "
                        "never to extrapolate. Turn it on when leaving those cells at stock is "
                        "the MORE dangerous option: above the span the curve still under-reads "
                        "~30%, closed-loop trims hide that but OPEN loop does not, and every "
                        "error mode of extrapolating is the safe one (rich, and load reads high "
                        "so timing indexes further into retard)")
    p.add_argument("--ack-knock", action="store_true",
                   help="with --tune-maf: HUMAN override of clamp_knock_auto_abort. Declares "
                        "that you have reviewed the knock in these logs and judged the "
                        "closed-loop fuel evidence uncontaminated. Recorded in the change "
                        "report. Retard-only timing proposals do not need it -- they are "
                        "exempt structurally")
    p.add_argument("--report-out", metavar="PATH",
                   help="with --tune-maf / --tune-timing: write the change report here "
                        "instead of stdout")
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
    if args.verify_flash:
        return _verify_flash(args.verify_flash, args.rom, args.baseline_rom, args.expect)
    if args.tune_maf:
        return _tune_maf(args.tune_maf, args.rom, args.out, args.report_out, args.baseline_rom,
                         args.ack_knock, args.extrapolate_maf)
    if args.tune_timing:
        return _tune_timing(args.tune_timing, args.rom, args.out, args.report_out,
                            args.baseline_rom)
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
