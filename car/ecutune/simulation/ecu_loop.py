"""The factory closed-loop fuel control, just enough of it to emit realistic trims.

The real ECU splits its fuel feedback into a fast short-term term (AF Correction) and a slow
long-term term it learns and stores (AF Learning). At steady state the learning term has absorbed
most of the error and the correction term carries the small remainder. We reproduce that split so
the synthetic log looks like a real RomRaider log — and so binning's `af_correction + af_learning`
recovers the full trim, exactly as on the car.
"""
from __future__ import annotations

LEARN_SHARE = 0.85   # long-term AF Learning absorbs most of the steady-state error
CORR_SHARE = 0.15    # short-term AF Correction carries the rest


def split_trim(trim_pct: float) -> tuple[float, float]:
    """(af_learning %, af_correction %) summing to the total trim."""
    return trim_pct * LEARN_SHARE, trim_pct * CORR_SHARE
