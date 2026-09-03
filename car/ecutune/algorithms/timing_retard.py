"""Ignition-timing retard, the first stage that tunes a 2-D MAP, and the first that never
uses a fuel trim.

WHY THIS EXISTS (2026-08-30). On the post-flash-3 drive the car's `IAM` collapsed from 0.500 to
0.000 and stayed there for 52 seconds while running, recovering only to 0.125. IAM 0 means the
ECU has withdrawn *all* dynamic ignition advance, the strongest protective response it has, and
it is out of authority. `Base Timing` commands 38-42 deg BTDC at 0.7-1.0 g/rev, where this car
makes boost. That map was calibrated for an 8.4:1 EJ255, where 0.85 g/rev is ~59% of NA maximum;
on the 9.5:1 EJ20X the same cell is ~73% of NA max. Two factors compounding, both in the same
direction.

Fuel is no longer a confound: three MAF iterations took the cruise region from ~+30% trim to
under 3%, so the LOAD axis this map is indexed on is finally trustworthy. That ordering is not
incidental; it is `clamp_fuel_before_timing`, and it is why this stage could not have been
written first.

HOW IT DIFFERS FROM `maf_transfer`
  * That stage corrects a SENSOR: a measurement wrong by a fixed amount, established over ~20k
    samples, where the correction is bounded by evidence and displacement.
  * This stage corrects a CALIBRATION CHOICE against a hazard. There is no "correct" value to
    converge on, only a value that stops the engine detonating, so the basis is HYBRID:
    measured knock evidence where the car has actually been driven, and a ratified octane /
    compression ceiling everywhere else. Syed's decision, 2026-08-30.

THE CORRECTION BASIS

    confident cell : new = min(current - evidence, ceiling)
    everywhere else: new = min(current,            ceiling)

`evidence` is what the ECU itself already had to take away at that cell:

    evidence = retard(feedback knock) + retard(fine learned knock) + global IAM deficit

Only the RETARD half of each channel counts: `Fine Learning Knock Correction` reached +0.35 deg
on this log, i.e. the ECU had learned it could add a little advance somewhere, and learned
advance is not evidence for retarding.

THE IAM TERM IS GLOBAL, DELIBERATELY. IAM is one multiplier for the whole engine, so a per-cell
mean would encode WHEN IN THE DRIVE each cell was visited, not how dangerous it is, cells
driven after the collapse would be punished for the clock. One number derived from the drive's
worst IAM is applied to every evidence-driven cell instead. The reason it is counted at all: a
cell that logged no knock while IAM sat at 0 is not proven safe, because it was running with the
ECU's dynamic advance already withdrawn and will get that advance back when IAM recovers.

WHAT THIS STAGE DOES NOT DO
  * It never ADVANCES a cell. Every path is a `min` against the current value.
  * It never invents evidence for a cell it has no samples for; those get the ceiling, which is
    an octane/compression limit rather than a measurement (Syed approved applying it to undriven
    cells because the drive to the shop is a highway).
  * It does not bound itself. `clamp_timing_row_ceiling` re-asserts the ceiling and
    `clamp_timing_rate_limit` applies retard-only, the 6 deg/iteration step and the cumulative
    floor against stock. The stage proposing something reasonable is convenience; the clamps
    refusing something unreasonable is the safety property.

Pure, like every stage: returns a Proposal and NEVER applies it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.config import AlgoCfg, SafetyCfg
from ..core.models import CellEdit, Proposal, Table, TableSet
from ..core.tables import (IGNITION_ADVANCE_MULT_INITIAL, IGNITION_BASE_TIMING,
                           IGNITION_KNOCK_ADVANCE_MAX)
from ..logparse.binning import BinnedGrid, GridSpec

# Mean measured retard below this is indistinguishable from log noise and the single-sample
# jitter of a 0.3516 deg/step storage grid, so it contributes nothing. The ceiling still
# applies to these cells: this deadband suppresses evidence, never protection.
EVIDENCE_DEADBAND_DEG = 0.25


@dataclass
class TimingState:
    """Per-stage state. A counter, like MafState: there is no integral term because each cell is
    an independent bin re-measured from a fresh log every iteration."""
    iterations: int = 0


def grid_spec_for_timing(table: Table, min_samples: int = 20) -> GridSpec:
    """Bin a log against the timing map's OWN axes, so bins line up 1:1 with map cells.

    x = the map's load breakpoints, y = its rpm breakpoints, which makes `CellEdit(row=rpm index,
    col=load index)` a direct index into the binned grid with no resampling in between.

    `require_closed_loop=False`, unlike the MAF stage. That flag exists because an open-loop
    sample carries a FROZEN A/F correction and would drag a binned fuel trim toward zero. Knock
    is measured in open loop exactly as it is in closed loop, and open loop is precisely where
    this car makes boost, so filtering it would discard the only samples that matter.
    """
    if table.x_axis is None or table.y_axis is None:
        raise ValueError(f"{table.table_id}: timing map needs both a load and an rpm axis")
    return GridSpec(x_role="load", x_breaks=tuple(float(v) for v in table.x_axis.breakpoints),
                    y_role="rpm", y_breaks=tuple(float(v) for v in table.y_axis.breakpoints),
                    min_samples=min_samples, require_closed_loop=False)


def _align_to(source: Table, target: Table) -> np.ndarray:
    """Resample `source` onto `target`'s axes by nearest breakpoint.

    `Knock Correction Advance Max` shares Base Timing's rpm axis but carries SIXTEEN load
    columns to its fifteen (it has an extra 2.5 g/rev column), so aligning by index would be
    right for this pair by luck and wrong for the next one. Matching on breakpoint VALUES is
    the same discipline `bin_log` uses to assign samples to cells.
    """
    src = np.asarray(source.values, dtype=float)
    sx = np.asarray(source.x_axis.breakpoints if source.x_axis else [0.0], dtype=float)
    sy = np.asarray(source.y_axis.breakpoints if source.y_axis else [0.0], dtype=float)
    tx = np.asarray(target.x_axis.breakpoints if target.x_axis else [0.0], dtype=float)
    ty = np.asarray(target.y_axis.breakpoints if target.y_axis else [0.0], dtype=float)
    ci = np.abs(tx[:, None] - sx[None, :]).argmin(axis=1)
    ri = np.abs(ty[:, None] - sy[None, :]).argmin(axis=1)
    return src[np.ix_(ri, ci)]


def iam_deficit_degrees(iam: np.ndarray | None, safety: SafetyCfg,
                        tables: TableSet | None = None,
                        target: Table | None = None) -> tuple[np.ndarray | float, dict]:
    """Degrees of dynamic advance the ECU was holding back, per cell, from the drive's WORST IAM.

    Returns `(deficit, info)`. `deficit` is a per-cell array when the ROM exposes the advance
    map, and a scalar fallback otherwise; `info` carries the numbers for the change report.

    TWO ROM-DERIVED FACTS REPLACED TWO GUESSES HERE (2026-08-30).

    1. WHAT IAM MULTIPLIES. On this ECU family the commanded advance is
       `Base Timing + IAM x Knock Correction Advance Max + feedback + fine learning + comps`.
       So the advance a cell loses when IAM collapses is not a flat constant -- it is that
       cell's own entry in `Knock Correction Advance Max`, which on this ROM is **0.0 across
       the whole idle and cruise region** (load <= 0.55) and 3.16-9.14 deg where the car makes
       boost. The flat 2 deg constant this function used first was therefore retarding the idle
       band, which is independently validated as knock-free, while UNDER-correcting the boost
       cells that actually needed it.

    2. WHAT COUNTS AS HEALTHY. `Advance Multiplier (Initial)` in this ROM is **0.5**, not 1.0.
       An observed IAM of 0.500 is this calibration's factory value, not a halved one, and the
       step is 0.25. Measuring the deficit from a hardcoded 1.0 would have doubled it and
       invented a permanent 50% deficit on a perfectly healthy engine.

    `None` (channel absent) and an all-NaN channel both give 0.0 -- a log that never recorded
    IAM is not evidence that IAM was healthy, but it is also not evidence that it was not, and
    inventing retard from a missing channel is the wrong kind of conservative.
    """
    info: dict = {"iam_worst": None, "iam_reference": safety.iam_reference,
                  "iam_reference_source": "config", "iam_authority_source": "config",
                  "iam_deficit_fraction": 0.0}
    if iam is None:
        return 0.0, info
    v = np.asarray(iam, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return 0.0, info

    reference = safety.iam_reference
    if tables is not None:
        init = tables.tables.get(IGNITION_ADVANCE_MULT_INITIAL)
        if init is not None:
            reference = float(np.asarray(init.values).reshape(-1)[0])
            info["iam_reference_source"] = "ROM:Advance Multiplier (Initial)"

    worst = float(v.min())
    fraction = max(0.0, reference - worst)
    info.update(iam_worst=worst, iam_reference=reference, iam_deficit_fraction=fraction)

    authority: np.ndarray | float = safety.iam_advance_authority_deg
    if tables is not None and target is not None:
        adv = tables.tables.get(IGNITION_KNOCK_ADVANCE_MAX)
        if adv is not None and np.asarray(adv.values).ndim == 2:
            authority = np.maximum(_align_to(adv, target), 0.0)
            info["iam_authority_source"] = "ROM:Knock Correction Advance Max"
    deficit = fraction * authority
    info["iam_deficit_max_deg"] = float(np.max(deficit)) if np.ndim(deficit) else float(deficit)
    return deficit, info


def _retard(a: np.ndarray | None, shape: tuple[int, int]) -> np.ndarray:
    """The RETARD magnitude of a signed correction channel: max(0, -x), NaN treated as 0.

    A knock-correction channel is <= 0 when the ECU is pulling timing and > 0 when it has
    learned it can give some back. Only the pulling half is evidence for retarding further.
    """
    if a is None:
        return np.zeros(shape)
    return np.where(np.isfinite(a), np.maximum(0.0, -np.asarray(a, dtype=float)), 0.0)


def ceiling_grid(table: Table, safety: SafetyCfg) -> np.ndarray:
    """The per-cell advance ceiling, evaluated at the map's own axis values.

    Evaluated against the breakpoints as the ROM stores them (float32), not against the decimal
    literals in config.yaml, `SafetyCfg.timing_ceiling_for` is epsilon-tolerant for exactly
    this reason. Before that fix both ratified load bands started one column late.
    """
    rpms = table.y_axis.breakpoints if table.y_axis else (0.0,)
    loads = table.x_axis.breakpoints if table.x_axis else (None,)
    return np.array([[safety.timing_ceiling_for(float(r), None if c is None else float(c))
                      for c in loads] for r in rpms], dtype=float)


def propose_timing_retard(grid: BinnedGrid, tables: TableSet, state: TimingState,
                          cfg: AlgoCfg, safety: SafetyCfg,
                          iam_deficit_deg: np.ndarray | float = 0.0,
                          provenance: str = "algorithm:timing_retard",
                          metadata: dict | None = None) -> tuple[Proposal, TimingState]:
    """One bounded ignition-retard Proposal from a log binned on this ROM's timing-map axes.

    Note there is no `damping` here, unlike the MAF stage. Damping exists to under-shoot a
    target you are converging on from measurements that will move as you correct. A ceiling is
    not a target being chased; it is a limit, and deliberately arriving at 70% of a safety
    limit is not caution. Approach speed is Syed's 6 deg/iteration rate cap, applied by
    `clamp_timing_rate_limit`, not a gain in the proposer.
    """
    table = tables.tables.get(IGNITION_BASE_TIMING)
    if table is None:
        raise ValueError(f"{IGNITION_BASE_TIMING} absent from the table set")
    current = np.asarray(table.values, dtype=float)
    if current.ndim != 2:
        raise ValueError(f"{IGNITION_BASE_TIMING} is {current.ndim}-D; the timing stage needs a map")
    if grid.count.shape != current.shape:
        raise ValueError(f"grid is {grid.count.shape}, map is {current.shape}, the GridSpec was "
                         "not built from this table (use grid_spec_for_timing)")

    ceiling = ceiling_grid(table, safety)
    measured = _retard(grid.mean_knock, current.shape) + _retard(grid.mean_fine_knock,
                                                                 current.shape)
    measured = np.where(measured < EVIDENCE_DEADBAND_DEG, 0.0, measured)

    confident = np.asarray(grid.confidence, dtype=bool)
    evidence = np.where(confident, measured + iam_deficit_deg, 0.0)
    proposed = np.minimum(current - evidence, ceiling)

    edits: list[CellEdit] = []
    n_evidence_driven = 0
    for r, c in zip(*np.nonzero(proposed < current)):
        r, c = int(r), int(c)
        why = []
        if evidence[r, c] > 0:
            iam_here = float(np.asarray(iam_deficit_deg).reshape(current.shape)[r, c]
                             if np.ndim(iam_deficit_deg) else iam_deficit_deg)
            why.append(f"measured retard {measured[r, c]:.2f} deg"
                       + (f" + IAM deficit {iam_here:.2f} deg" if iam_here else "")
                       + f" over {int(grid.count[r, c])} samples")
            n_evidence_driven += 1
        if proposed[r, c] >= ceiling[r, c] - 1e-9:
            why.append(f"ceiling {ceiling[r, c]:.1f} deg")
        rpm = table.y_axis.breakpoints[r] if table.y_axis else 0.0
        load = table.x_axis.breakpoints[c] if table.x_axis else 0.0
        edits.append(CellEdit(IGNITION_BASE_TIMING, r, c, float(proposed[r, c]),
                              f"{rpm:.0f} rpm / {load:.2f} g/rev: "
                              f"{current[r, c]:.2f} -> {proposed[r, c]:.2f} deg ({'; '.join(why)})"))

    pulled = current - proposed
    meta = {
        "n_cells": int(current.size),
        "n_edited": len(edits),
        "n_confident_cells": int(confident.sum()),
        "n_cells_with_data": int((grid.count > 0).sum()),
        "n_evidence_driven": n_evidence_driven,
        "n_ceiling_only": len(edits) - n_evidence_driven,
        "iam_deficit_max_deg": float(np.max(iam_deficit_deg)) if np.ndim(iam_deficit_deg)
                               else float(iam_deficit_deg),
        "max_measured_evidence_deg": float(measured.max()) if measured.size else 0.0,
        "max_pull_deg": float(pulled.max()) if pulled.size else 0.0,
        "evidence_deadband_deg": EVIDENCE_DEADBAND_DEG,
    }
    meta.update(metadata or {})
    prop = Proposal(f"timing-{state.iterations}", "timing_retard", tuple(edits),
                    "timing", provenance, meta)
    return prop, TimingState(state.iterations + 1)
