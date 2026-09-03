"""RomRaider SubaruDefs ingester, the vertical slice.

Clones/updates github.com/RomRaider/SubaruDefs (open, GPL-2.0) and parses the ECUFlash
per-ROM XML definitions. Each ROM file (`<romid>` + a list of `<table name=… address=…>`
maps) becomes one Document: the ECU's identity + its tunable parameter list, structured
"facts" for the retrieval store.

NOTE: the per-ROM files carry table NAMES + addresses; the numeric scaling/units live in the
referenced base defs (`<include>`, e.g. 32BITBASE). Resolving those is a follow-up; this
slice captures the per-ROM definition surface, which is already high-value.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Iterator

from lxml import etree

from ..core.config import Config, SourceCfg
from ..core.http import HttpClient
from ..core.models import Document

log = logging.getLogger(__name__)

name = "romraider_defs"

_ROMID_FIELDS = [
    "xmlid", "ecuid", "year", "market", "make", "model", "submodel",
    "transmission", "memmodel", "flashmethod", "checksummodule",
]


def _ensure_repo(repo_url: str, local: Path, auto_update: bool) -> None:
    if (local / ".git").exists():
        if auto_update:
            subprocess.run(["git", "-C", str(local), "pull", "--ff-only"],
                           capture_output=True, text=True)
    else:
        local.parent.mkdir(parents=True, exist_ok=True)
        log.info("cloning %s -> %s", repo_url, local)
        subprocess.run(["git", "clone", "--depth", "1", repo_url, str(local)],
                       capture_output=True, text=True)


def fetch(cfg: Config, source_cfg: SourceCfg, http: HttpClient) -> Iterator[Document]:
    extra = source_cfg.model_extra or {}
    repo_url = extra.get("repo_url", "https://github.com/RomRaider/SubaruDefs.git")
    local = cfg.resolve(extra.get("local_path", "data/raw/SubaruDefs"))
    subdirs = extra.get("ecuflash_subdirs", ["ECUFlash/subaru standard", "ECUFlash/subaru metric"])
    only_models = {m.lower() for m in extra.get("only_models", [])}  # optional filter

    _ensure_repo(repo_url, local, bool(extra.get("auto_update", True)))
    parser = etree.XMLParser(recover=True)

    for sub in subdirs:
        root_dir = local / sub
        if not root_dir.exists():
            log.warning("subdir missing: %s", root_dir)
            continue
        for xml_path in sorted(root_dir.rglob("*.xml")):
            try:
                doc = _parse_rom(xml_path, local, parser)
            except Exception as e:  # one bad file never kills the pass
                log.warning("parse failed %s: %s", xml_path.name, e)
                continue
            if doc is None:
                continue
            if only_models and (doc.meta.get("model") or "").lower() not in only_models:
                continue
            yield doc


def _parse_rom(xml_path: Path, base: Path, parser: etree.XMLParser) -> Document | None:
    tree = etree.parse(str(xml_path), parser)
    root = tree.getroot()
    if root is None:
        return None
    romid = root.find("romid")
    if romid is None:
        return None  # a base/scaling def (no romid), skip in this slice

    def g(tag: str) -> str | None:
        el = romid.find(tag)
        return el.text.strip() if (el is not None and el.text) else None

    meta = {f: g(f) for f in _ROMID_FIELDS}
    xmlid = meta.get("xmlid") or xml_path.stem
    meta["xmlid"] = xmlid

    tables = [t.get("name") for t in root.findall("table") if t.get("name")]
    meta["table_count"] = len(tables)
    meta["includes"] = [i.text.strip() for i in root.findall("include") if i.text]

    title_bits = [meta.get("make") or "Subaru", meta.get("model") or "", meta.get("submodel") or "",
                  meta.get("year") or "", f"({xmlid})"]
    title = " ".join(b for b in title_bits if b).strip() + ", ECUFlash definition"

    lines = [title, "", "ROM identity:"]
    for k in ["ecuid", "year", "market", "transmission", "memmodel", "flashmethod"]:
        if meta.get(k):
            lines.append(f"  {k}: {meta[k]}")
    lines += ["", f"Tunable tables ({len(tables)}):"] + [f"  - {t}" for t in tables]
    text = "\n".join(lines)

    rel = xml_path.relative_to(base).as_posix()
    return Document(
        source=name,
        source_id=xmlid,
        title=title,
        text=text,
        kind="ecu_definition",
        domain="subaru",
        tier="reference",
        url=f"https://github.com/RomRaider/SubaruDefs/blob/master/{rel}",
        meta=meta,
    )
