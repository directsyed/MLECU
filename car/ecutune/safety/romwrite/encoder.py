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


def encode(values: np.ndarray, scaling: Scaling) -> tuple[bytes, float]:
    """Engineering values -> big-endian raw bytes. Returns (bytes, max round-trip error).

    Raises EncodingError rather than storing an approximation it was not asked for.
    """
    if scaling.storagetype not in _DTYPES:
        raise EncodingError(f"unsupported storage type {scaling.storagetype!r}")
    vals = np.asarray(values, dtype=np.float64).ravel()
    if not np.all(np.isfinite(vals)):
        raise EncodingError("cannot encode non-finite values")

    raw = _apply(scaling.frexpr, vals)
    if not np.all(np.isfinite(raw)):
        raise EncodingError(f"frexpr {scaling.frexpr!r} produced a non-finite result")

    if scaling.storagetype != "float":
        lo, hi = _INT_RANGES[scaling.storagetype]
        raw = np.rint(raw)
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
    tol = max(quantisation_step(scaling, float(vals[0])) / 2.0, 1e-9) if vals.size else 1e-9
    # Scale the tolerance with magnitude for float storage: float32 carries ~7 significant
    # digits, so a 296 g/s cell cannot round-trip to 1e-9 absolute.
    tol = max(tol, float(np.max(np.abs(vals))) * 1e-6) if vals.size else tol
    if err > tol:
        raise EncodingError(
            f"round-trip error {err:.6g} exceeds tolerance {tol:.6g} for scaling "
            f"{scaling.name!r} (toexpr={scaling.toexpr!r} frexpr={scaling.frexpr!r}) — "
            "the def's frexpr is not the inverse of its toexpr; refusing to write")
    return blob, err
