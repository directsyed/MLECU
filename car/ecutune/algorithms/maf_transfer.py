"""MAF transfer-curve correction — the first stage that tunes a real CURVE, not a scalar.

WHY THIS EXISTS (2026-08-27). Six vacuum drives showed the car's fuel trim tracks *measured
airflow* far better than it tracks load or rpm (corr +0.85 vs +0.71 / +0.75), and the decisive
test settles it: hold MAF fixed and swing load/rpm hard, trim moves 0.3-5.0 pp; hold load fixed
and swing MAF, trim moves 3.1-15.3 pp. The error is a function of airflow alone, so the wrong
table is the MAF transfer curve (`sensor.maf_transfer`), not the fuel maps.

This matters beyond fuelling: LOAD is derived from airflow, so an under-reading MAF also makes
the ECU index the ignition map at the wrong cell and never cross the load threshold that
triggers open-loop enrichment. One curve fixes three symptoms.

HOW IT DIFFERS FROM `idle_global_scalar`
  * That stage moves three global SCALARS at one operating point and uses a PI controller with
    an integral term to separate degenerate knobs over many iterations.
  * This stage moves 48 CELLS of one curve, each informed by its own independent bin of samples.
    There is no degeneracy to resolve, so there is no integral term: an integrator here would
    only add overshoot. Each iteration measures the CURRENT residual trim and corrects by
    `damping x residual`, which converges geometrically on its own.

TWO RULES THAT ARE NOT NEGOTIABLE
  1. NEVER EXTRAPOLATE. Breakpoints outside the measured airflow range are left untouched. The
     measured curve is non-monotonic at the top (+36.3% at 25-30 g/s falling to +30.3% at
     30-45 g/s), so a blind trend extrapolation would be actively wrong in the boost region --
     exactly where lean is dangerous.
  2. ONLY CONFIDENT BINS. A breakpoint is corrected only where `grid.confidence` is True
     (>= `GridSpec.min_samples` steady samples). Everything else keeps its stock value.
  3. DEADBAND. A measured correction below `AlgoCfg.sensor_deadband` emits no edit. Fuel trims
     are noisy and a +/-1% bin mean is not distinguishable from zero -- correcting it is
     chasing noise. It also protects regions independently validated as healthy: the idle band
     measured -0.86% trim on the three-hold capture, and the first uncorrected run of this
     stage was proposing -1% to -3% there off 367 drive samples.

Pure, like every stage: it returns a Proposal and NEVER applies it (`safety.apply_proposal`
does that). `targets_kind="sensor"` routes it to `clamp_sensor_calibration` rather than to the
fuel clamps, whose +/-3%-per-iteration velocity bound was designed for idle convergence and is
the wrong instrument for a one-shot sensor recalibration backed by ~20k samples.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.config import AlgoCfg
from ..core.models import CellEdit, Proposal, Table, TableSet
from ..core.tables import SENSOR_MAF_TRANSFER
from ..logparse.binning import BinnedGrid, GridSpec
from . import fueling


@dataclass
class MafState:
    """Per-stage state. Deliberately just a counter — see the module docstring on why there is
    no integrator here (48 independent bins, no degeneracy, integral would only overshoot)."""
    iterations: int = 0


def grid_spec_for(table: Table, min_samples: int = 20) -> GridSpec:
    """Build the GridSpec that bins a log against THIS ROM's own MAF breakpoints.

    The stock curve's g/s values become the x breakpoints, so every sample is assigned to the
    cell whose calibration it actually informs (`bin_log` uses nearest-assignment). A single y
    breakpoint collapses rpm: the correction is a function of airflow only, which is the whole
    finding this stage acts on.
    """
    vals = np.asarray(table.values, dtype=float).ravel()
    if vals.size == 0:
        raise ValueError("MAF transfer table is empty")
    return GridSpec(x_role="maf_gs", x_breaks=tuple(float(v) for v in vals),
                    y_breaks=(0.0,), min_samples=min_samples, require_closed_loop=True)


def _measured_correction(grid: BinnedGrid) -> tuple[np.ndarray, np.ndarray]:
    """Collapse the grid to per-breakpoint (fuel_fraction, sample_count).

    `mean_trim` is PERCENT (af_correction + af_learning); `trim_to_fuel_fraction` converts.
    Non-confident bins come back as NaN so callers cannot silently treat them as zero.
    """
    trim = np.asarray(grid.mean_trim, dtype=float)
    count = np.asarray(grid.count, dtype=float)

    # Count-weighted collapse of the rpm axis. `grid_spec_for` uses a single y breakpoint so this
    # is normally a no-op, but doing it properly keeps the stage correct if a caller ever bins
    # against a real rpm axis -- and an unweighted sum over empty cells would propagate the NaN
    # that bin_log writes wherever count == 0.
    ok = np.isfinite(trim)
    num = np.where(ok, trim * count, 0.0).sum(axis=0)
    den = np.where(ok, count, 0.0).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.divide(num, den, out=np.full(den.shape, np.nan), where=den > 0)

    total = count.sum(axis=0)
    # Confidence is judged on TOTAL samples per breakpoint after collapsing, not per (rpm, maf)
    # cell: this correction is one-dimensional, so samples at different rpm all inform the same
    # breakpoint and should be pooled before the threshold is applied.
    confident = total >= grid.grid_spec.min_samples
    frac = np.where(confident, fueling.trim_to_fuel_fraction(mean), np.nan)
    return frac, total


def plateau_ratio(total_ratio: np.ndarray, count: np.ndarray, confident: np.ndarray,
                  n_plateau: int = 3) -> tuple[float, list[int]]:
    """The settled correction ratio at the TOP of the measured span, for extrapolation.

    Returns (count-weighted mean ratio, the breakpoint indices it came from). The caller decides
    whether to use it; this function only reports what the data says.

    Uses the highest `n_plateau` CONFIDENT breakpoints, weighted by sample count, because that
    is where the error has stopped changing. On this car the measured total error rises to
    ~+37% around 30-39 g/s and then settles at ~+31-33% from 42-59 g/s -- a plateau, not a
    trend. Fitting a slope through it and projecting would be inventing a rise the data does
    not show, which is the specific mistake `maf_transfer`'s no-extrapolation rule was written
    to prevent.
    """
    idx = [i for i in np.flatnonzero(confident) if np.isfinite(total_ratio[i])]
    if not idx:
        return 1.0, []
    top = idx[-n_plateau:]
    w = np.asarray([max(count[i], 1.0) for i in top], dtype=float)
    r = np.asarray([total_ratio[i] for i in top], dtype=float)
    return float(np.average(r, weights=w)), [int(i) for i in top]


def _interpolated_correction(frac: np.ndarray) -> np.ndarray:
    """Smooth the per-bin corrections across breakpoints, WITHOUT extrapolating.

    Confident bins anchor a piecewise-linear correction curve; gaps BETWEEN anchors are
    interpolated (the physical error is smooth in airflow, so a gap between two measured points
    is genuinely known). Breakpoints outside the measured span get 0.0 — untouched, never
    extrapolated (rule 1 in the module docstring).
    """
    out = np.zeros_like(frac, dtype=float)
    idx = np.flatnonzero(np.isfinite(frac))
    if idx.size == 0:
        return out
    lo, hi = idx[0], idx[-1]
    span = np.arange(lo, hi + 1)
    out[span] = np.interp(span, idx, frac[idx])
    return out


def propose_maf_correction(grid: BinnedGrid, tables: TableSet, state: MafState,
                           cfg: AlgoCfg,
                           provenance: str = "algorithm:maf_transfer",
                           metadata: dict | None = None,
                           baseline: TableSet | None = None,
                           extrapolate: bool = False,
                           n_plateau: int = 3) -> tuple[Proposal, MafState]:
    """One bounded MAF-transfer Proposal from a log binned on this ROM's MAF breakpoints.

    Correction is DIRECT (`fueling.corrected_maf`): a positive trim means the ECU had to ADD
    fuel, i.e. real airflow exceeded what the sensor reported, so the curve moves UP.
    """
    table = tables.get(SENSOR_MAF_TRANSFER)
    if table is None:
        raise ValueError(f"{SENSOR_MAF_TRANSFER} absent from the table set")
    stock = np.asarray(table.values, dtype=float).ravel()

    frac, count = _measured_correction(grid)
    if frac.size != stock.size:
        raise ValueError(f"grid has {frac.size} breakpoints, table has {stock.size} — "
                         "the GridSpec was not built from this table (use grid_spec_for)")
    # Keep the PRE-deadband measurement: the deadband exists to stop the stage chasing noise in
    # the correction it applies, but zeroing a real +1.8% before averaging would bias the
    # extrapolation plateau low. Different questions, different inputs.
    raw_frac = frac.copy()
    # Deadband BEFORE interpolation, so a sub-noise anchor cannot drag its neighbours either.
    deadband = getattr(cfg, "sensor_deadband", 0.0)
    frac = np.where(np.isfinite(frac) & (np.abs(frac) < deadband), 0.0, frac)
    applied = _interpolated_correction(frac) * cfg.damping
    _anchors = np.flatnonzero(np.isfinite(frac))
    idx_hi = int(_anchors[-1]) if _anchors.size else None

    edits: list[CellEdit] = []
    for i, f in enumerate(applied):
        if f == 0.0:
            continue                      # untouched: outside the measured span, or no signal
        new = fueling.corrected_maf(float(stock[i]), float(f))
        edits.append(CellEdit(SENSOR_MAF_TRANSFER, 0, i, new,
                              f"airflow bin {stock[i]:.2f} g/s: trim {f / cfg.damping * 100:+.1f}% "
                              f"-> applied {f * 100:+.1f}% (damping {cfg.damping})"))

    # --- EXTRAPOLATION ABOVE THE MEASURED SPAN (opt-in, 2026-08-30) ---------------------
    # Rule 1 of this module is NEVER EXTRAPOLATE, and it is still the default. It was written
    # when the only data was vacuum-only and the curve looked non-monotonic at the top, so a
    # trend fit would have invented a correction in the boost region. Three flashes later the
    # top of the measured range is a FLAT PLATEAU (~+32% across 42-59 g/s, hundreds of samples),
    # and the situation it was protecting against has inverted:
    #
    #   * Above the span the curve is STOCK, i.e. still ~30% under-reading. That is not a
    #     neutral "no opinion" -- it is a known-wrong value.
    #   * In CLOSED loop the trims hide it. In OPEN loop nothing does, and this car has never
    #     been in power open loop, so the first full-throttle pull is the first time the error
    #     is exposed with no safety net: commanded 12.5 AFR arrives as roughly 18.
    #   * Every error mode of extrapolating is SAFE (over-correct -> rich, and load reads high
    #     so timing is indexed further into retard). Every error mode of NOT extrapolating is
    #     the fatal one, in both channels at once.
    #
    # So it is opt-in, it holds the measured plateau flat rather than fitting a slope, it is
    # measured against the ARCHIVED STOCK ROM rather than the partially-corrected current curve,
    # and every extrapolated cell says so in its reason string. Extrapolated cells are replaced
    # by measurement the moment a drive produces data there -- this is a bridge, not a result.
    extrap_meta: dict = {}
    if extrapolate and baseline is not None and idx_hi is not None:
        try:
            base = np.asarray(baseline.get(SENSOR_MAF_TRANSFER).values, dtype=float).ravel()
        except (KeyError, AttributeError):
            base = None
        if base is not None and base.size == stock.size:
            with np.errstate(invalid="ignore", divide="ignore"):
                cumulative = np.divide(stock, base, out=np.full(base.shape, np.nan),
                                       where=np.abs(base) > 0)
            total = cumulative * (1.0 + np.where(np.isfinite(raw_frac), raw_frac, 0.0))
            ratio, from_idx = plateau_ratio(total, count, np.isfinite(raw_frac), n_plateau)
            measured_max = float(np.nanmax(total)) if np.isfinite(total).any() else ratio
            for i in range(idx_hi + 1, stock.size):
                if not np.isfinite(base[i]) or base[i] <= 0:
                    continue
                new = float(base[i] * ratio)
                if new <= stock[i]:
                    continue                      # already at or above the plateau; leave it
                edits.append(CellEdit(SENSOR_MAF_TRANSFER, 0, i, new,
                                      f"airflow bin {base[i]:.2f} g/s: EXTRAPOLATED at the "
                                      f"measured plateau {(ratio - 1) * 100:+.1f}% "
                                      f"(from breakpoints {from_idx}, no samples of its own)"))
            extrap_meta = {
                "extrapolated": True,
                "extrapolated_from_index": int(idx_hi),
                "extrapolated_cells": int(sum(1 for e in edits if "EXTRAPOLATED" in e.reason)),
                "plateau_ratio": float(ratio),
                "plateau_from_breakpoints": from_idx,
                "max_measured_ratio": measured_max,
            }

    measured = frac[np.isfinite(frac)]
    meta = {
        "n_breakpoints": int(stock.size),
        "n_corrected": len(edits),
        "n_confident_bins": int(np.isfinite(frac).sum()),
        "damping": cfg.damping,
        "max_measured_correction": float(measured.max()) if measured.size else 0.0,
        "sample_counts": [int(c) for c in count],
    }
    meta.update(extrap_meta)
    meta.update(metadata or {})
    prop = Proposal(f"maf-{state.iterations}", "maf_transfer", tuple(edits),
                    "sensor", provenance, meta)
    return prop, MafState(state.iterations + 1)
