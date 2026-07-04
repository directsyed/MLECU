"""ECUFlash definition parser — revision XML + its include chain, merged into flat TableDefs.

ECUFlash splits a definition across files: the *base* (e.g. 32BITBASE) carries table metadata
(type, scaling, axis sizes/scalings); the *revision* file (e.g. A2WC410D) carries only the
addresses for that calibration, plus occasional element-count overrides. Merge rules used here,
matching how ECUFlash resolves them for the 05-06 32-bit Subaru family:

- files are indexed by <xmlid>; <include> names the parent; the chain is walked leaf -> base.
- tables merge by name; the leaf-most address wins.
- a revision's child <table name="X"/"Y"> rows map onto the base's "X Axis"/"Y Axis" children.
- "Static Y Axis" children carry labels, not data -> a 2D table with a static axis is a scalar
  (or a fixed-length list) whose element count comes from the static axis.
- element counts: revision override > base attr; a 2D table's data length = its axis length.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

_STORAGE_SIZES = {"uint8": 1, "int8": 1, "uint16": 2, "int16": 2, "uint32": 4, "int32": 4,
                  "float": 4}


@dataclass(frozen=True)
class Scaling:
    name: str
    storagetype: str = "uint8"
    endian: str = "big"
    toexpr: str = "x"
    units: str = ""
    vmin: float | None = None       # def-declared plausible range (used to vet reads)
    vmax: float | None = None

    @property
    def byte_size(self) -> int:
        return _STORAGE_SIZES[self.storagetype]


@dataclass
class AxisDef:
    kind: str                        # "X" | "Y" | "static"
    name: str = ""
    address: int | None = None
    elements: int | None = None
    scaling: str | None = None
    labels: tuple[str, ...] = ()     # static axes only


@dataclass
class TableDef:
    name: str
    ttype: str = ""                  # "1D" | "2D" | "3D"
    address: int | None = None
    scaling: str | None = None
    axes: list[AxisDef] = field(default_factory=list)

    def axis(self, kind: str) -> AxisDef | None:
        for a in self.axes:
            if a.kind == kind:
                return a
        return None


@dataclass(frozen=True)
class RomIdInfo:
    xmlid: str
    internalidaddress: int
    internalidstring: str
    ecuid: str


def _hex(s: str | None) -> int | None:
    return int(s, 16) if s else None


class EcuFlashDefs:
    """Index of an ECUFlash defs tree (e.g. SubaruDefs/ECUFlash/subaru metric)."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._by_xmlid: dict[str, Path] = {}
        for p in self.root.rglob("*.xml"):
            m = re.search(r"<xmlid>([^<]+)</xmlid>", p.read_text(encoding="utf-8",
                                                                 errors="replace")[:2000])
            if m:
                self._by_xmlid.setdefault(m.group(1).strip(), p)

    # -- public API ---------------------------------------------------------------------
    def rom_id(self, xmlid: str) -> RomIdInfo:
        rom = self._parse(self._path(xmlid))
        rid = rom.find("romid")
        return RomIdInfo(
            xmlid=rid.findtext("xmlid", "").strip(),
            internalidaddress=int(rid.findtext("internalidaddress", "0"), 16),
            internalidstring=rid.findtext("internalidstring", "").strip(),
            ecuid=rid.findtext("ecuid", "").strip(),
        )

    def tables(self, xmlid: str) -> tuple[dict[str, TableDef], dict[str, Scaling]]:
        """Merged (tables, scalings) for a revision def, base-first so the leaf wins."""
        chain: list[ET.Element] = []
        cur: str | None = xmlid
        seen: set[str] = set()
        while cur and cur not in seen:
            seen.add(cur)
            rom = self._parse(self._path(cur))
            chain.append(rom)
            cur = (rom.findtext("include") or "").strip() or None
        tables: dict[str, TableDef] = {}
        scalings: dict[str, Scaling] = {}
        for rom in reversed(chain):                      # base first, leaf overrides
            for sc in rom.findall("scaling"):
                def _f(attr: str) -> float | None:
                    try:
                        return float(sc.get(attr)) if sc.get(attr) else None
                    except ValueError:
                        return None
                s = Scaling(name=sc.get("name", ""), storagetype=sc.get("storagetype", "uint8"),
                            endian=sc.get("endian", "big"), toexpr=sc.get("toexpr", "x"),
                            units=sc.get("units", ""), vmin=_f("min"), vmax=_f("max"))
                scalings[s.name] = s
            for tb in rom.findall("table"):
                self._merge_table(tables, tb)
        return tables, scalings

    # -- internals ----------------------------------------------------------------------
    def _path(self, xmlid: str) -> Path:
        if xmlid not in self._by_xmlid:
            raise KeyError(f"no ECUFlash def with xmlid={xmlid!r} under {self.root}")
        return self._by_xmlid[xmlid]

    @staticmethod
    def _parse(path: Path) -> ET.Element:
        return ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))

    @staticmethod
    def _merge_table(tables: dict[str, TableDef], tb: ET.Element) -> None:
        name = tb.get("name", "")
        if not name:
            return
        td = tables.setdefault(name, TableDef(name=name))
        td.ttype = tb.get("type", td.ttype)
        td.address = _hex(tb.get("address")) if tb.get("address") else td.address
        td.scaling = tb.get("scaling", td.scaling)
        for child in tb.findall("table"):
            ctype = child.get("type", "")
            cname = child.get("name", "")
            if "Static" in ctype:
                kind = "static"
            elif "X Axis" in ctype or cname == "X":
                kind = "X"
            elif "Y Axis" in ctype or cname == "Y":
                kind = "Y"
            else:
                continue
            ax = td.axis(kind)
            if ax is None:
                ax = AxisDef(kind=kind)
                td.axes.append(ax)
            if cname and cname not in ("X", "Y"):
                ax.name = cname
            if child.get("address"):
                ax.address = _hex(child.get("address"))
            if child.get("elements"):
                ax.elements = int(child.get("elements"))
            if child.get("scaling"):
                ax.scaling = child.get("scaling")
            labels = tuple(d.text or "" for d in child.findall("data"))
            if labels:
                ax.labels = labels
                ax.elements = ax.elements or len(labels)
