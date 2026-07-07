"""ROM comparison — table-level diff between two ROM images of the same family.

Purpose (ROADMAP Phase B): the first read of the car's actual ECU gets diffed against the
harvested stock 3B12504206. Differing cells, mapped to semantic table names, answer "is the
ROM really stock?" before any tuning assumption is made. Also reports the raw byte-level
difference so changes OUTSIDE the semantic table set can't hide.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .defs import EcuFlashDefs
from .reader import RomImage, read_semantic_tables


@dataclass
class TableDiff:
    semantic_id: str
    n_cells: int
    n_diff: int
    max_abs_delta: float
    examples: list[tuple[tuple, float, float]] = field(default_factory=list)  # (index, a, b)


@dataclass
class RomDiff:
    ids: tuple[str, str]                  # internal ids of A and B
    byte_diff_count: int                  # raw differing bytes across the whole image
    byte_diff_ranges: list[tuple[int, int]]   # [start, end) of differing runs (capped)
    table_diffs: list[TableDiff]          # semantic tables with differences
    tables_identical: int

    @property
    def is_identical(self) -> bool:
        return self.byte_diff_count == 0


def _byte_ranges(a: bytes, b: bytes, cap: int = 64) -> tuple[int, list[tuple[int, int]]]:
    arr_a = np.frombuffer(a, dtype=np.uint8)
    arr_b = np.frombuffer(b, dtype=np.uint8)
    n = min(len(arr_a), len(arr_b))
    neq = arr_a[:n] != arr_b[:n]
    count = int(neq.sum()) + abs(len(arr_a) - len(arr_b))
    idx = np.flatnonzero(neq)
    ranges: list[tuple[int, int]] = []
    for i in idx:
        if ranges and i == ranges[-1][1]:
            ranges[-1] = (ranges[-1][0], int(i) + 1)
        else:
            if len(ranges) >= cap:
                break
            ranges.append((int(i), int(i) + 1))
    return count, ranges


def diff_roms(path_a, path_b, defs: EcuFlashDefs, def_ids: list[str],
              semantic_map: dict[str, str],
              variants: dict[str, tuple[str, ...]] | None = None,
              max_examples: int = 8) -> RomDiff:
    rom_a, rom_b = RomImage.load(path_a), RomImage.load(path_b)
    tabs_a, rep_a = read_semantic_tables(rom_a, defs, def_ids, semantic_map, variants)
    tabs_b, rep_b = read_semantic_tables(rom_b, defs, def_ids, semantic_map, variants)

    byte_count, byte_ranges = _byte_ranges(rom_a.data, rom_b.data)

    table_diffs: list[TableDiff] = []
    identical = 0
    for sid in sorted(set(tabs_a) & set(tabs_b)):
        va, vb = tabs_a[sid].values, tabs_b[sid].values
        if va.shape != vb.shape:
            table_diffs.append(TableDiff(sid, int(va.size), -1, float("nan"),
                                         [((-1,), float(va.size), float(vb.size))]))
            continue
        neq = ~np.isclose(va, vb, rtol=0, atol=1e-12)
        nd = int(neq.sum())
        if nd == 0:
            identical += 1
            continue
        deltas = np.abs(va - vb)
        examples = []
        for index in np.argwhere(neq)[:max_examples]:
            key = tuple(int(x) for x in index) if index.size else ()
            examples.append((key, float(va[tuple(index)]) if index.size else float(va),
                             float(vb[tuple(index)]) if index.size else float(vb)))
        table_diffs.append(TableDiff(sid, int(va.size), nd, float(deltas.max()), examples))

    return RomDiff(ids=(rep_a["internal_id"], rep_b["internal_id"]),
                   byte_diff_count=byte_count, byte_diff_ranges=byte_ranges,
                   table_diffs=table_diffs, tables_identical=identical)


def byte_only_diff(path_a, path_b) -> RomDiff:
    """Defs-free fallback: byte-level comparison only (semantic decode unavailable/refused)."""
    a, b = RomImage.load(path_a), RomImage.load(path_b)
    count, ranges = _byte_ranges(a.data, b.data)
    return RomDiff(ids=("?", "?"), byte_diff_count=count, byte_diff_ranges=ranges,
                   table_diffs=[], tables_identical=0)


def format_report(d: RomDiff) -> str:
    lines = [f"ROM diff: {d.ids[0]} vs {d.ids[1]}"]
    if d.is_identical:
        lines.append("IDENTICAL — every byte matches. The ROM is exactly this reference image.")
        return "\n".join(lines)
    lines.append(f"raw differing bytes: {d.byte_diff_count} "
                 f"in {len(d.byte_diff_ranges)}{'+' if len(d.byte_diff_ranges) >= 64 else ''} runs")
    for s, e in d.byte_diff_ranges[:12]:
        lines.append(f"  bytes 0x{s:06x}..0x{e:06x}")
    lines.append(f"semantic tables identical: {d.tables_identical}; differing: {len(d.table_diffs)}")
    for t in d.table_diffs:
        lines.append(f"  {t.semantic_id}: {t.n_diff}/{t.n_cells} cells differ "
                     f"(max |delta| {t.max_abs_delta:g})")
        for idx, a, b in t.examples:
            lines.append(f"    cell {idx}: {a:g} -> {b:g}")
    if d.byte_diff_count and not d.table_diffs:
        lines.append("NOTE: byte differences exist OUTSIDE the semantic table set "
                     "(un-mapped regions — code, other tables, or checksums).")
    return "\n".join(lines)
