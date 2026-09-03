"""Apply clamped CellEdits to a COPY of a ROM image, and prove afterwards that nothing else moved.

THE CONTRACT. `patch()` accepts a `ClampResult`, never a raw `Proposal`. Edits reach bytes only
after `safety.apply_clamps` has bounded them; this module cannot be used to bypass the clamps,
because it has no code path that takes unclamped input.

WHY IT LIVES UNDER safety/. `docs/OPEN-CHECKLIST.md` places romwrite here so the source-scan
invariant in `tests/test_write_path.py` keeps covering the whole write path. This module never
calls `TableSet.with_edits` and never mutates `Table.values` in place; it works on a `bytearray`
copy of the image and returns new bytes.

THE VERIFICATION STACK (ROADMAP Phase E.4), in order, all mandatory:
  (a) BYTE-DIFF WHITELIST, only bytes inside an edited table's own address range, plus the
      checksum record's `stored` field, may differ. ANY other differing byte aborts. This is
      the check that catches an address resolved from the wrong def revision.
  (b) READ-BACK, decode the patched image through the ordinary read path and confirm the
      intended values actually landed, and that no OTHER semantic table moved.
  (c) BOUNDS; every written value re-checked against the def's declared min/max.
  (d) CHECKSUM, repaired, then re-verified.

A failure at any stage raises. There is no partial write and no "written with warnings": the
function either returns an image that passed every check, or it raises and you still have your
stock ROM.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ...core.models import CellEdit, ClampResult, Table
from ...romread.defs import Scaling, TableDef
from ...romread.reader import _DTYPES, _apply, ResolvedDef
from . import checksum
from .encoder import encode


class WriteVerificationError(RuntimeError):
    """A patched image failed verification. The image is discarded, never returned."""


@dataclass
class WriteResult:
    data: bytes
    edits: tuple[CellEdit, ...]
    byte_ranges: tuple[tuple[int, int], ...]          # [start, end) of every differing run
    checksum_repaired: tuple[int, ...] = ()           # record indices
    max_quantisation_error: float = 0.0
    notes: list[str] = field(default_factory=list)


def _cell_offset(td: TableDef, sc: Scaling, table: Table, edit: CellEdit) -> int:
    """Byte offset of one cell.

    3-D tables are stored row-major with X fastest (`reader.read_table` reshapes
    `(len(y), len(x))`), so the inverse index is `row * n_x + col`. For a curve the reader puts
    the *Y*-kind axis into `Table.x_axis`: a genuine trap, but the linear index is just `col`
    either way, so cell addressing does not depend on resolving that.
    """
    if table.kind == "scalar":
        idx = 0
    elif table.kind == "curve_1d":
        idx = edit.col
    else:
        n_x = table.values.shape[1]
        idx = edit.row * n_x + edit.col
    return td.address + idx * sc.byte_size


def patch(stock: bytes, result: ClampResult, tables: dict[str, Table],
          resolved: dict[str, ResolvedDef],
          round_modes: dict[str, str] | None = None) -> WriteResult:
    """Apply clamped edits to a copy of `stock`. Returns a verified image or raises.

    `round_modes` maps a semantic table id to the storage rounding policy for that table
    (see `encoder.encode`). Default is "nearest" for everything, which is right whenever the
    approved value is a target. `ignition.base_timing` needs "no_greater": it is uint8 at
    0.3516 deg/step, so rounding to nearest can store up to +0.176 deg MORE ADVANCE than the
    clamps approved, and a ceiling the storage layer is free to exceed is not a ceiling.
    """
    round_modes = round_modes or {}
    if not result.ok:
        raise WriteVerificationError(f"refusing to patch an aborted proposal "
                                     f"({result.aborted_by})")
    if not result.clamped_edits:
        raise WriteVerificationError("no surviving edits to write")

    buf = bytearray(stock)
    allowed: list[tuple[int, int]] = []
    max_err = 0.0
    notes: list[str] = []
    # (table_id, row, col) -> (byte offset, width, the value those bytes decode to). Checked
    # again at the end against the FINAL image, after the checksum repair has also written.
    expected: dict[tuple[str, int, int], tuple[int, int, float]] = {}

    by_table: dict[str, list[CellEdit]] = {}
    for e in result.clamped_edits:
        by_table.setdefault(e.table_id, []).append(e)

    for table_id, edits in by_table.items():
        rd = resolved.get(table_id)
        table = tables.get(table_id)
        if rd is None or table is None:
            raise WriteVerificationError(
                f"{table_id}: no resolved def, the write path must patch the address that WON "
                "reconciliation, and re-deriving it from a fixed def id risks the +0x20 drift "
                "between A2WC410D and A2WC412D")
        mode = round_modes.get(table_id, "nearest")
        notes.append(f"{table_id}: def {rd.def_id} @0x{rd.table_def.address:X} "
                     f"({rd.scaling.storagetype}, {rd.scaling.name}, rounding={mode})")
        for e in edits:
            blob, err = encode(np.asarray([e.new_value]), rd.scaling, mode)
            off = _cell_offset(rd.table_def, rd.scaling, table, e)
            if off + len(blob) > len(buf):
                raise WriteVerificationError(f"{table_id} cell ({e.row},{e.col}) at 0x{off:X} "
                                             "runs past the end of the ROM")
            buf[off:off + len(blob)] = blob
            allowed.append((off, off + len(blob)))
            max_err = max(max_err, err)
            expected[(table_id, e.row, e.col)] = (
                off, len(blob),
                float(_apply(rd.scaling.toexpr,
                             np.frombuffer(blob, dtype=_DTYPES[rd.scaling.storagetype]))[0]))

    # (d) checksum, must run before the whitelist check, since its own write is whitelisted
    repaired = checksum.repair(buf)
    for r in repaired:
        allowed.append((r.offset + 8, r.offset + 12))     # the `stored` field only

    # (a) byte-diff whitelist
    diffs = _diff_ranges(stock, buf)
    stray = [d for d in diffs if not _covered(d, allowed)]
    if stray:
        raise WriteVerificationError(
            f"{len(stray)} byte range(s) changed outside the whitelist: "
            + ", ".join(f"0x{a:X}..0x{b:X}" for a, b in stray[:5]))

    # (b) READ-BACK, structural half: a curve that was strictly ascending in the stock image
    # must still be strictly ascending after encoding. This is what caught the float32
    # collapse: the clamp guaranteed ordering in engineering units, but a 1e-9 separation is
    # not representable at float32 precision, so the promise died at the storage boundary.
    # An in-memory guarantee that does not survive encoding is not a guarantee.
    for table_id in by_table:
        t = tables[table_id]
        if t.kind != "curve_1d":
            continue
        before = np.asarray(t.values, float).ravel()
        if not np.all(np.diff(before) > 0):
            continue                        # stock already flat/decreasing here; not ours to fix
        rd = resolved[table_id]
        n = before.size
        off = rd.table_def.address
        after_raw = np.frombuffer(bytes(buf[off:off + n * rd.scaling.byte_size]),
                                  dtype=_DTYPES[rd.scaling.storagetype])
        after = np.asarray(_apply(rd.scaling.toexpr, after_raw), float)
        bad = np.flatnonzero(np.diff(after) <= 0)
        if bad.size:
            raise WriteVerificationError(
                f"{table_id}: stock curve was strictly ascending but the ENCODED curve is not "
                f"(cells {bad[:5].tolist()}), the storage type cannot represent the ordering "
                "the clamp promised")

    # (b) READ-BACK, per-cell half, applies to EVERY table kind, not just curves.
    # The ordering check above only covers curve_1d, so before 2026-08-30 a map_2d write had
    # no value-level read-back at all: it was protected by the byte whitelist and the checksum,
    # neither of which can tell a correct cell from one written at the wrong index. Decoding
    # each edited cell out of the FINAL image (after the checksum repair has also written)
    # closes that, and it is the check that would catch a _cell_offset regression on a 2-D map.
    for (table_id, row, col), (off, width, want) in expected.items():
        rd = resolved[table_id]
        got = float(_apply(rd.scaling.toexpr,
                           np.frombuffer(bytes(buf[off:off + width]),
                                         dtype=_DTYPES[rd.scaling.storagetype]))[0])
        if not np.isclose(got, want, rtol=0.0, atol=1e-9):
            raise WriteVerificationError(
                f"{table_id} cell ({row},{col}) at 0x{off:X} reads back as {got:.6g}, not the "
                f"{want:.6g} that was written; the image does not contain what was approved")

    # (d, cont.) checksum re-verified on the final image
    if checksum.verify(buf):
        raise WriteVerificationError("checksum still failing after repair")

    return WriteResult(bytes(buf), tuple(result.clamped_edits), tuple(diffs),
                       tuple(r.index for r in repaired), max_err, notes)


def _diff_ranges(a: bytes, b: bytes) -> list[tuple[int, int]]:
    """Coalesce differing bytes into [start, end) runs."""
    if len(a) != len(b):
        raise WriteVerificationError(f"size changed: {len(a)} -> {len(b)}")
    d = np.frombuffer(a, dtype=np.uint8) != np.frombuffer(b, dtype=np.uint8)
    idx = np.flatnonzero(d)
    if idx.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate(([idx[0]], idx[breaks + 1]))
    ends = np.concatenate((idx[breaks], [idx[-1]])) + 1
    return [(int(s), int(e)) for s, e in zip(starts, ends)]


def _covered(rng: tuple[int, int], allowed: list[tuple[int, int]]) -> bool:
    lo, hi = rng
    return any(a <= lo and hi <= b for a, b in _merge(allowed))


def _merge(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for lo, hi in sorted(ranges):
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out
