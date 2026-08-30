"""Bin a LogTable into (x = airflow|load) x (y = rpm) cells — the input the tuning algorithm
consumes.

Two ideas do the real work:
  * `trim error` per cell = af_correction + af_learning (short-term + long-term fuel trim). This
    is exactly the signal the bounded-integral controller drives to zero: a +6% trim means the
    ECU is adding 6% fuel to hold stoich because the base map is 6% lean there.
  * confidence: a cell is only trustworthy once it has >= min_samples STEADY samples. Transient
    samples (rpm/throttle moving) are dropped — they poison fuel readings (wall-wetting, accel
    enrichment). This is the data-side of the safety layer's steady-state-before-transients rule.

Samples are assigned to the nearest axis breakpoint (the cell whose calibration they inform).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import schema
from .romraider_csv import LogTable


@dataclass(frozen=True)
class GridSpec:
    x_role: str                       # "maf_gs" or "load"
    x_breaks: tuple[float, ...]       # ECU axis breakpoints (cell centers), not bin edges
    y_breaks: tuple[float, ...]
    y_role: str = "rpm"
    min_samples: int = 20             # cells below this are low-confidence (excluded from proposals)
    require_steady: bool = True
    steady_rpm_tol: float = 100.0     # |d rpm/sample| above this => transient, dropped
    steady_tps_tol: float = 2.0       # |d tps/sample| above this => transient, dropped
    # Open-loop samples carry a FROZEN A/F Correction (measured sd 0.04 vs 9.75 in closed
    # loop), so pooling them drags a binned trim toward zero. Default False for back-compat
    # with the sim harness, which has no fuel_system_status channel; the real-log stages set
    # it True. Inert when the channel is absent -- we never silently discard a whole log.
    require_closed_loop: bool = False


@dataclass
class BinnedGrid:
    grid_spec: GridSpec
    count: np.ndarray       # (ny, nx) steady-sample count per cell
    mean_trim: np.ndarray   # (ny, nx) mean (af_correction + af_learning) — the error signal
    mean_afr: np.ndarray    # (ny, nx) mean wideband AFR (NaN where no wideband)
    mean_knock: np.ndarray  # (ny, nx) mean knock retard
    confidence: np.ndarray  # (ny, nx) bool: count >= min_samples
    # --- ignition-timing channels (2026-08-30) ------------------------------------------
    # All three are NaN where the cell has no VALID sample of that channel, never 0.0. The
    # distinction is load-bearing here in a way it is not for trim: `timing_base` is present
    # in exactly one of the ten drive logs, and a missing channel silently read as 0.0 would
    # make (base - total) evidence look like a colossal retard demand on every other log.
    mean_fine_knock: np.ndarray | None = None    # mean fine (learned) knock correction, deg
    mean_timing_total: np.ndarray | None = None  # mean FINAL commanded advance, deg BTDC
    mean_timing_base: np.ndarray | None = None   # mean BASE MAP output, deg BTDC


def _nearest_idx(vals: np.ndarray, breaks: tuple[float, ...]) -> np.ndarray:
    b = np.asarray(breaks, dtype=float)
    return np.abs(vals[:, None] - b[None, :]).argmin(axis=1)


def _steady_mask(log: LogTable, spec: GridSpec) -> np.ndarray:
    n = len(log)
    mask = np.ones(n, dtype=bool)
    if not spec.require_steady or n < 2:
        return mask
    rpm = log.get("rpm")
    tps = log.get("tps")
    if rpm is not None:
        mask &= np.abs(np.gradient(rpm)) <= spec.steady_rpm_tol
    if tps is not None:
        mask &= np.abs(np.gradient(tps)) <= spec.steady_tps_tol
    if spec.require_closed_loop:
        status = log.get("fuel_system_status")
        if status is not None:
            mask &= status == schema.CL_NORMAL
    return mask


def bin_log(log: LogTable, spec: GridSpec) -> BinnedGrid:
    n = len(log)
    x = log.get(spec.x_role)
    y = log.get(spec.y_role)
    if x is None or y is None:
        raise KeyError(f"log missing required channel(s): x={spec.x_role!r} y={spec.y_role!r}")

    corr = log.get("af_correction", np.zeros(n))
    learn = log.get("af_learning", np.zeros(n))
    trim = corr + learn
    afr = log.get("wideband_afr", np.full(n, np.nan))
    knock = log.get("knock_retard", np.zeros(n))

    ny, nx = len(spec.y_breaks), len(spec.x_breaks)
    count = np.zeros((ny, nx))
    sum_trim = np.zeros((ny, nx))
    sum_knock = np.zeros((ny, nx))
    sum_afr = np.zeros((ny, nx))
    count_afr = np.zeros((ny, nx))

    sel = np.nonzero(_steady_mask(log, spec) & ~np.isnan(x) & ~np.isnan(y))[0]
    xi, yi = _nearest_idx(x, spec.x_breaks), _nearest_idx(y, spec.y_breaks)
    cells = (yi[sel], xi[sel])
    np.add.at(count, cells, 1.0)
    np.add.at(sum_trim, cells, np.nan_to_num(trim[sel]))
    np.add.at(sum_knock, cells, np.nan_to_num(knock[sel]))
    afr_valid = sel[~np.isnan(afr[sel])]
    np.add.at(sum_afr, (yi[afr_valid], xi[afr_valid]), afr[afr_valid])
    np.add.at(count_afr, (yi[afr_valid], xi[afr_valid]), 1.0)

    with np.errstate(invalid="ignore", divide="ignore"):
        mean_trim = np.where(count > 0, sum_trim / count, np.nan)
        mean_knock = np.where(count > 0, sum_knock / count, np.nan)
        mean_afr = np.where(count_afr > 0, sum_afr / count_afr, np.nan)

    def _nan_mean(role: str) -> np.ndarray | None:
        """Per-cell mean of `role` over the selected samples, NaN where none were valid.

        Returns None when the log does not carry the channel at all, so a caller can tell
        "this log never measured it" apart from "measured, but not in this cell". Both are
        safer than the 0.0 that `log.get(role, zeros)` would hand back.
        """
        v = log.get(role)
        if v is None:
            return None
        s = np.zeros((ny, nx))
        c = np.zeros((ny, nx))
        valid = sel[~np.isnan(v[sel])]
        np.add.at(s, (yi[valid], xi[valid]), v[valid])
        np.add.at(c, (yi[valid], xi[valid]), 1.0)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(c > 0, s / c, np.nan)

    return BinnedGrid(spec, count, mean_trim, mean_afr, mean_knock,
                      count >= spec.min_samples,
                      mean_fine_knock=_nan_mean("fine_knock_learn"),
                      mean_timing_total=_nan_mean("timing_total"),
                      mean_timing_base=_nan_mean("timing_base"))


def weighted_mean_trim(grid: BinnedGrid) -> float:
    """Count-weighted mean trim over confident cells — the global steady-state fuel error the
    idle global-scalar algorithm corrects. Falls back to any sampled cell if none are confident
    (idle visits ~one cell, which may be below min_samples on a short log)."""
    conf = grid.confidence
    if not conf.any():
        conf = grid.count > 0
    if not conf.any():
        return 0.0
    return float(np.average(grid.mean_trim[conf], weights=grid.count[conf]))
