"""Read table values out of a ROM image using merged ECUFlash TableDefs.

Layout facts for the 05-06 32-bit Subaru family this targets:
- multi-byte storage is big-endian (SuperH);
- 3D data is stored row-major with the X axis fastest (rows = Y/rpm, cols = X/load);
- the calibration ID (internalidstring) sits at internalidaddress (0x2000 on 32-bit).

Because community defs lag ECU revisions (our A2WC411D has no def anywhere in SubaruDefs),
read_semantic_tables() supports reading through SIBLING defs and cross-validating: extract the
same tables via two or more neighbouring revision defs and require bit-identical results before
trusting the values. Address drift between revisions then shows up as a hard error, not silence.
"""
from __future__ import annotations

import numpy as np

from ..core.models import Table, TableAxis
from .defs import EcuFlashDefs, Scaling, TableDef

_DTYPES = {"uint8": ">u1", "int8": ">i1", "uint16": ">u2", "int16": ">i2",
           "uint32": ">u4", "int32": ">i4", "float": ">f4"}
_EXPR_OK = set("0123456789.x+-*/() ")


def _apply(expr: str, raw: np.ndarray) -> np.ndarray:
    """Evaluate an ECUFlash toexpr ('x*.00025', '2707090/x', ...) on the raw array."""
    if set(expr) - _EXPR_OK:
        raise ValueError(f"unsupported toexpr: {expr!r}")
    return np.asarray(eval(expr, {"__builtins__": {}}, {"x": raw.astype(np.float64)}),
                      dtype=np.float64)


class RomImage:
    def __init__(self, data: bytes):
        self.data = data

    @classmethod
    def load(cls, path) -> "RomImage":
        return cls(open(path, "rb").read())

    def internal_id(self, address: int, length: int = 8) -> str:
        return self.data[address:address + length].decode("ascii", errors="replace")

    def read_raw(self, address: int, elements: int, scaling: Scaling) -> np.ndarray:
        end = address + elements * scaling.byte_size
        if end > len(self.data):
            raise ValueError(f"read past end of ROM: 0x{address:x}+{elements}")
        return np.frombuffer(self.data[address:end], dtype=_DTYPES[scaling.storagetype])


def read_table(rom: RomImage, td: TableDef, scalings: dict[str, Scaling]) -> Table:
    """TableDef -> core Table (scalar / curve_1d / map_2d) with real axes."""
    if td.address is None:
        raise ValueError(f"{td.name}: no address in def")
    data_sc = scalings[td.scaling] if td.scaling in scalings else Scaling(name="raw")

    def axis_values(kind: str) -> tuple[np.ndarray | None, str]:
        ax = td.axis(kind)
        if ax is None or ax.address is None or not ax.elements:
            return None, ax.name if ax else ""
        sc = scalings.get(ax.scaling or "", Scaling(name="raw"))
        return _apply(sc.toexpr, rom.read_raw(ax.address, ax.elements, sc)), ax.name

    x_vals, x_name = axis_values("X")
    y_vals, y_name = axis_values("Y")

    if td.ttype == "3D":
        if x_vals is None or y_vals is None:
            raise ValueError(f"{td.name}: 3D table missing an axis address")
        n = len(x_vals) * len(y_vals)
        raw = rom.read_raw(td.address, n, data_sc)
        vals = _apply(data_sc.toexpr, raw).reshape(len(y_vals), len(x_vals))
        return Table(td.name, "map_2d", vals, units=data_sc.units,
                     x_axis=TableAxis(x_name or "x", tuple(x_vals)),
                     y_axis=TableAxis(y_name or "y", tuple(y_vals)))

    # 2D: data length follows the (single) real axis; static axis => scalar/fixed list
    static = td.axis("static")
    if y_vals is not None:
        vals = _apply(data_sc.toexpr, rom.read_raw(td.address, len(y_vals), data_sc))
        return Table(td.name, "curve_1d", vals, units=data_sc.units,
                     x_axis=TableAxis(y_name or "y", tuple(y_vals)))
    n = (static.elements if static and static.elements else 1)
    vals = _apply(data_sc.toexpr, rom.read_raw(td.address, n, data_sc))
    if n == 1:
        return Table(td.name, "scalar", vals.reshape(()), units=data_sc.units)
    return Table(td.name, "curve_1d", vals, units=data_sc.units)


def _monotonic(vals) -> bool:
    a = np.asarray(vals, dtype=float)
    if a.size < 2:
        return True
    d = np.diff(a)
    return bool(np.all(d > 0) or np.all(d < 0))


def plausible(t: Table, data_sc: Scaling) -> bool:
    """A read is plausible iff every real axis is strictly monotonic and the data sits
    inside the def's own declared min/max. A wrong address (revision drift) almost always
    breaks one of these; a correct one never should."""
    for ax in (t.x_axis, t.y_axis):
        if ax is not None and not _monotonic(ax.breakpoints):
            return False
    v = t.values.reshape(-1)
    if not np.all(np.isfinite(v)):
        return False
    if data_sc.vmin is not None and v.min() < data_sc.vmin - 1e-9:
        return False
    if data_sc.vmax is not None and v.max() > data_sc.vmax + 1e-9:
        return False
    return True


def read_semantic_tables(rom: RomImage, defs: EcuFlashDefs, def_ids: list[str],
                         semantic_map: dict[str, str],
                         variants: dict[str, tuple[str, ...]] | None = None,
                         ) -> tuple[dict[str, Table], dict]:
    """Read the semantic table set through sibling revision defs and reconcile.

    Per table: defs that read bit-identically corroborate each other; where they disagree
    (address drift between revisions), only a read that passes plausible() survives, and it
    must be UNIQUE — zero or multiple surviving candidates is a hard error, never a guess.
    Returns ({semantic_id: Table}, report with per-table provenance).
    """
    variants = variants or {}
    reads: dict[str, list[tuple[str, Table, Scaling]]] = {}
    report: dict = {"def_ids": def_ids, "internal_id": None, "matched": {}, "provenance": {}}
    for did in def_ids:
        tables, scalings = defs.tables(did)
        rid = defs.rom_id(did)
        report["internal_id"] = rom.internal_id(rid.internalidaddress)
        for sem_id, primary in semantic_map.items():
            for name in (primary, *variants.get(sem_id, ())):
                if name in tables and tables[name].address is not None:
                    td = tables[name]
                    sc = scalings.get(td.scaling or "", Scaling(name="raw"))
                    reads.setdefault(sem_id, []).append((did, read_table(rom, td, scalings), sc))
                    report["matched"][sem_id] = name
                    break

    out: dict[str, Table] = {}
    for sem_id, cands in reads.items():
        groups: list[tuple[Table, Scaling, list[str]]] = []   # distinct value-sets
        for did, t, sc in cands:
            for g in groups:
                if np.array_equal(g[0].values, t.values):
                    g[2].append(did)
                    break
            else:
                groups.append((t, sc, [did]))
        if len(groups) == 1:
            t, _, dids = groups[0]
            out[sem_id] = t
            report["provenance"][sem_id] = f"agree({','.join(dids)})"
            continue
        survivors = [(t, dids) for t, sc, dids in groups if plausible(t, sc)]
        if len(survivors) != 1:
            raise ValueError(
                f"{sem_id}: defs disagree ({[d for *_, d in groups]}) and plausibility "
                f"leaves {len(survivors)} candidates — refusing to guess")
        t, dids = survivors[0]
        out[sem_id] = t
        report["provenance"][sem_id] = f"plausible-only({','.join(dids)})"
    return out, report
