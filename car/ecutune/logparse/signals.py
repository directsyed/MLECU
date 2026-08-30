"""Live signals for a ClampContext, computed from a real log instead of left at their defaults.

WHY THIS EXISTS (2026-08-30). `ClampContext.knock_active`, `.fuel_trims_converged` and
`.steady_state_ok` were never set anywhere in `ecutune/` — only in tests. That made three clamps
inert in production, including the one its own docstring calls *"the single most important
clamp"*, and it made `SafetyCfg.fuel_trim_converged_tol` a number nothing read. It also meant
`clamp_fuel_before_timing` deferred **every** timing proposal outright, since the flag it gates
on defaulted to False. A gate that always fires and a gate that never fires are the same bug.

Everything here is measured from the pooled log and the binned grid. Nothing is asserted by a
caller, and nothing is read from proposal metadata — a clamp input that the proposer can set is
not a safety input.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.config import SafetyCfg
from .binning import BinnedGrid, _steady_mask, weighted_mean_trim
from .romraider_csv import LogTable

# A knock ONSET is a step DOWN of at least this many degrees between consecutive samples. This
# is the project's own definition, established in logging/drive/ANALYSIS-2026-08-26-vacuum-
# drives.md: counting samples where retard is merely non-zero counts the slow ramp-back as new
# knock and inflates 31 onsets into thousands of "events".
KNOCK_ONSET_STEP_DEG = 1.5
# Retard beyond this is not physical on this ECU (worst genuine event measured: -12 deg). The
# 2026-08-26 capture contained a single -32.0 sample between neighbours of -8.12 and -7.94 --
# a link spike. Counting it as knock would be counting the K-line, not the engine.
KNOCK_SPIKE_FLOOR_DEG = -20.0


@dataclass(frozen=True)
class LiveSignals:
    knock_active: bool
    knock_onsets: int
    fuel_trims_converged: bool
    steady_state_ok: bool
    max_trim_abs: float          # FRACTION, not percent — ClampContext's unit
    worst_knock_deg: float

    def as_context_kwargs(self) -> dict:
        return {"knock_active": self.knock_active,
                "fuel_trims_converged": self.fuel_trims_converged,
                "steady_state_ok": self.steady_state_ok,
                "max_trim_abs": self.max_trim_abs}


def knock_onsets(knock: np.ndarray | None) -> tuple[int, float]:
    """(number of onsets, worst retard in degrees). A missing channel is (0, 0.0).

    Absence is NOT treated as knock: a log that never recorded the channel is no evidence
    either way, and manufacturing a hard abort out of a missing column would block work on
    every historical log rather than protect anything.
    """
    if knock is None:
        return 0, 0.0
    v = np.asarray(knock, dtype=float)
    v = np.where(v < KNOCK_SPIKE_FLOOR_DEG, np.nan, v)
    finite = v[np.isfinite(v)]
    if finite.size < 2:
        return 0, float(finite.min()) if finite.size else 0.0
    steps = np.diff(finite)
    return int(np.sum(steps <= -KNOCK_ONSET_STEP_DEG)), float(finite.min())


def live_signals(log: LogTable, grid: BinnedGrid, safety: SafetyCfg) -> LiveSignals:
    """Measure the four live clamp inputs from one pooled log and its binned grid.

    Trims are PERCENT in the grid (`af_correction + af_learning`) and FRACTIONS in
    `SafetyCfg` / `ClampContext` — the conversion happens here, once, rather than at each
    comparison where it is easy to forget.
    """
    # Knock is measured over the samples the GRID ACTUALLY SELECTED, not the whole file.
    # `knock_active` is present tense: it asks whether the engine is at risk in the operating
    # region this proposal is derived from. A MAF correction is built from closed-loop steady
    # samples, so knock in an open-loop boost pull elsewhere in the same file does not
    # contaminate it -- while knock among those very samples does, and must abort. Applying the
    # whole-file answer to both would make the clamp fire on the wrong proposition.
    knock = log.get("knock_retard")
    if knock is not None:
        sel = _steady_mask(log, grid.grid_spec)
        knock = np.asarray(knock, dtype=float)[sel] if sel.shape == knock.shape else knock
    onsets, worst = knock_onsets(knock)

    conf = np.asarray(grid.confidence, dtype=bool)
    trims = np.asarray(grid.mean_trim, dtype=float)
    usable = conf & np.isfinite(trims)
    max_trim_abs = float(np.max(np.abs(trims[usable])) / 100.0) if usable.any() else 0.0

    # No confident cell => convergence is UNPROVEN, not proven. The gate stays shut.
    converged = bool(usable.any() and max_trim_abs <= safety.fuel_trim_converged_tol)

    sampled = np.asarray(grid.count, dtype=float) > 0
    steady = bool(sampled.any()
                  and abs(weighted_mean_trim(grid)) / 100.0 <= safety.steady_tol)

    return LiveSignals(knock_active=onsets > 0, knock_onsets=onsets,
                       fuel_trims_converged=converged, steady_state_ok=steady,
                       max_trim_abs=max_trim_abs, worst_knock_deg=worst)
