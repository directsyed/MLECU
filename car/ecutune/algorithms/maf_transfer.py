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
                    y_breaks=(0.0,), min_samples=min_samples)


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
                           metadata: dict | None = None) -> tuple[Proposal, MafState]:
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
    applied = _interpolated_correction(frac) * cfg.damping

    edits: list[CellEdit] = []
    for i, f in enumerate(applied):
        if f == 0.0:
            continue                      # untouched: outside the measured span, or no signal
        new = fueling.corrected_maf(float(stock[i]), float(f))
        edits.append(CellEdit(SENSOR_MAF_TRANSFER, 0, i, new,
                              f"airflow bin {stock[i]:.2f} g/s: trim {f / cfg.damping * 100:+.1f}% "
                              f"-> applied {f * 100:+.1f}% (damping {cfg.damping})"))

    measured = frac[np.isfinite(frac)]
    meta = {
        "n_breakpoints": int(stock.size),
        "n_corrected": len(edits),
        "n_confident_bins": int(np.isfinite(frac).sum()),
        "damping": cfg.damping,
        "max_measured_correction": float(measured.max()) if measured.size else 0.0,
        "sample_counts": [int(c) for c in count],
    }
    meta.update(metadata or {})
    prop = Proposal(f"maf-{state.iterations}", "maf_transfer", tuple(edits),
                    "sensor", provenance, meta)
    return prop, MafState(state.iterations + 1)
