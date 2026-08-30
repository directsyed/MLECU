"""Value -> raw bytes: the exact inverse of `romread.reader._apply`.

The read path evaluates a def's `toexpr` on raw storage to get engineering units. Writing needs
the other direction, and ECUFlash ships it: every numeric scaling carries a `frexpr` alongside
its `toexpr` (`Latency(ms)`: `toexpr="x*.00025"`, `frexpr="x/.00025"`). `defs.Scaling.frexpr`
parses it, and because every frexpr in the base def passes the same `_EXPR_OK` charset
allowlist the reader enforces, `_apply` evaluates it verbatim. We never invert an expression
ourselves.

TWO SAFETY PROPERTIES THIS MODULE OWES

1. ROUND-TRIP OR REFUSE. `encode` re-decodes what it just encoded and checks the result lands
   within half a quantisation step of the value asked for. If it does not — a scaling whose
   frexpr is not actually the inverse of its toexpr, an out-of-range value, a storage type
   that cannot represent it — it RAISES. A write path that silently stores something other
   than what was approved is the specific failure this project exists to prevent.

2. INTEGER ROUNDING IS EXPLICIT. Float tables (our MAF curve) are lossless. uint8/uint16
   tables (timing, injector latency) are not: `np.rint` to nearest, then a hard range check
   against the dtype. Rounding is where "byte-exact inverse" stops being free, so it is
   surfaced in `EncodedCells.max_quantisation_error` for the change report rather than hidden.
"""
from __future__ import annotations

import numpy as np

from ...romread.defs import Scaling
from ...romread.reader import _DTYPES, _apply

_INT_RANGES = {
    "uint8": (0, 2**8 - 1), "int8": (-2**7, 2**7 - 1),
    "uint16": (0, 2**16 - 1), "int16": (-2**15, 2**15 - 1),
    "uint32": (0, 2**32 - 1), "int32": (-2**31, 2**31 - 1),
}


class EncodingError(ValueError):
    """A value cannot be stored faithfully in this scaling. Never downgraded to a warning."""


def quantisation_step(scaling: Scaling, near: float) -> float:
    """Size of one storage LSB in engineering units, measured at `near`.

    Computed from the def rather than assumed, so it stays correct for non-linear scalings
    (the AFR table's `14.7/(1+x*.0078125)` has a step that varies across its range).
    """
    if scaling.storagetype == "float":
        return 0.0
    raw = float(_apply(scaling.frexpr, np.asarray(near, dtype=np.float64)))
    lo, hi = _apply(scaling.toexpr, np.asarray([raw, raw + 1.0], dtype=np.float64))
    return abs(float(hi) - float(lo))


def encode(values: np.ndarray, scaling: Scaling,
           round_mode: str = "nearest") -> tuple[bytes, float]:
    """Engineering values -> big-endian raw bytes. Returns (bytes, max round-trip error).

    Raises EncodingError rather than storing an approximation it was not asked for.

    `round_mode` controls what happens when a value falls between two storage steps:

      "nearest"    — closest representable value (default). Correct when the error is
                     symmetric, i.e. everywhere the approved value is a TARGET.
      "no_greater" — never store a value ABOVE the one approved. Required for ignition
                     timing: `Base Timing` is uint8 at 0.3516 deg/step, so rounding to
                     nearest can land up to +0.176 deg ADVANCED of the number the clamps
                     allowed. A clamp ceiling that the storage layer then exceeds is not a
                     ceiling, and advance is the direction that breaks engines.

    "no_greater" is expressed in ENGINEERING units, not raw ones: the correcting step is
    taken in whichever raw direction actually decreases the decoded value, so it stays right
    for a decreasing scaling like `2707090/x` where flooring the raw value would raise it.
    """
    if scaling.storagetype not in _DTYPES:
        raise EncodingError(f"unsupported storage type {scaling.storagetype!r}")
    if round_mode not in ("nearest", "no_greater"):
        raise EncodingError(f"unknown round_mode {round_mode!r}")
    vals = np.asarray(values, dtype=np.float64).ravel()
    if not np.all(np.isfinite(vals)):
        raise EncodingError("cannot encode non-finite values")

    raw = _apply(scaling.frexpr, vals)
    if not np.all(np.isfinite(raw)):
        raise EncodingError(f"frexpr {scaling.frexpr!r} produced a non-finite result")

    if scaling.storagetype != "float":
        lo, hi = _INT_RANGES[scaling.storagetype]
        raw = np.rint(raw)
        if round_mode == "no_greater":
            # Direction of increasing ENGINEERING value in raw space, measured from the def
            # itself rather than assumed. +1 for a rising toexpr, -1 for a falling one.
            step_up = _apply(scaling.toexpr, raw + 1.0) - _apply(scaling.toexpr, raw)
            direction = np.sign(step_up)
            over = _apply(scaling.toexpr, raw) > vals + 1e-12
            raw = np.where(over, raw - direction, raw)
        if raw.min() < lo or raw.max() > hi:
            raise EncodingError(
                f"raw value out of range for {scaling.storagetype}: "
                f"[{raw.min():.1f}, {raw.max():.1f}] outside [{lo}, {hi}]")

    blob = raw.astype(_DTYPES[scaling.storagetype]).tobytes()

    # Round-trip check — decode exactly as reader.read_table would, and prove we stored what
    # was approved. `endian` is parsed by defs.py but ignored by _DTYPES (hardcoded big), so
    # assert rather than inherit that inconsistency silently.
    if scaling.endian != "big":
        raise EncodingError(f"only big-endian scalings are supported, got {scaling.endian!r}")
    back = _apply(scaling.toexpr, np.frombuffer(blob, dtype=_DTYPES[scaling.storagetype]))
    err = float(np.max(np.abs(back - vals))) if vals.size else 0.0
    half_step = quantisation_step(scaling, float(vals[0])) / 2.0 if vals.size else 0.0
    # "no_greater" gives up the symmetric half-step: a value just above a storage step is
    # pushed a whole step DOWN rather than a half step up, so the honest bound is a full step.
    tol = max(half_step * (2.0 if round_mode == "no_greater" else 1.0), 1e-9)
    # Scale the tolerance with magnitude for float storage: float32 carries ~7 significant
    # digits, so a 296 g/s cell cannot round-trip to 1e-9 absolute.
    tol = max(tol, float(np.max(np.abs(vals))) * 1e-6) if vals.size else tol
    if round_mode == "no_greater" and vals.size and np.any(back > vals + 1e-9):
        worst = float(np.max(back - vals))
        raise EncodingError(
            f"round_mode='no_greater' but the stored value exceeds the approved one by "
            f"{worst:.6g} for scaling {scaling.name!r} — refusing to write a value more "
            "advanced than the clamps allowed")
    if err > tol:
        raise EncodingError(
            f"round-trip error {err:.6g} exceeds tolerance {tol:.6g} for scaling "
            f"{scaling.name!r} (toexpr={scaling.toexpr!r} frexpr={scaling.frexpr!r}) — "
            "the def's frexpr is not the inverse of its toexpr; refusing to write")
    return blob, err
