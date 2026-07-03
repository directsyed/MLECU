"""TunerStudio INI ECU-definition ingester — cross-platform table vocabulary (reference tier).

Clones speeduino/speeduino (GPL) and parses reference/speeduino.ini — the TunerStudio
definition that names every tunable table/curve of a *generic* open ECU (VE table, AFR target,
warmup enrichment, dead time, accel enrich, timing map...). One Document per [TableEditor] /
[CurveEditor] entry. This is the CROSS-PLATFORM analogue of romraider_defs: it gives the judge
and the future semantic table layer a universal vocabulary for "the tables every ECU has",
independent of the Subaru names. (rusEFI's ini is skipped — rusefi_docs already covers its
semantics; logged in decisions.md.)
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterator

from ..core.config import Config, SourceCfg
from ..core.http import HttpClient
from ..core.models import Document
from .romraider_defs import _ensure_repo

log = logging.getLogger(__name__)

name = "tunerstudio_ini"

_SECTION = re.compile(r"^\s*\[(\w+)\]")
_TABLE = re.compile(r'^\s*table\s*=\s*(\w+)\s*,\s*(\w+)\s*,\s*"([^"]*)"')
_CURVE = re.compile(r'^\s*curve\s*=\s*(\w+)\s*,\s*"([^"]*)"')
_BINS = re.compile(r"^\s*([xyz]Bins)\s*=\s*([\w,\s]+)")


def _parse_ini(text: str, url: str) -> Iterator[Document]:
    section = ""
    block_lines: list[str] = []
    block_id = block_title = block_kind = ""
    bins: dict[str, str] = {}

    def flush() -> Document | None:
        if not block_id:
            return None
        body = [f"TunerStudio {block_kind} definition: {block_title}",
                f"ini name: {block_id}", f"section: [{section}]", ""]
        body += [ln.strip() for ln in block_lines]
        return Document(
            source=name, source_id=f"{block_kind}:{block_id}",
            title=f"Speeduino {block_kind}: {block_title or block_id}",
            text="\n".join(body),
            kind="ecu_definition", domain="general", tier="reference", url=url,
            meta={"section": section, "ini_name": block_id, "label": block_title, **bins},
        )

    for line in text.splitlines():
        sec = _SECTION.match(line)
        if sec:
            doc = flush()
            if doc:
                yield doc
            block_id = ""
            block_lines = []
            bins = {}
            section = sec.group(1)
            continue
        if section not in ("TableEditor", "CurveEditor"):
            continue
        t = _TABLE.match(line)
        c = _CURVE.match(line)
        if t or c:
            doc = flush()
            if doc:
                yield doc
            bins = {}
            if t:
                block_id, _map, block_title = t.group(1), t.group(2), t.group(3)
                block_kind = "table"
            else:
                block_id, block_title = c.group(1), c.group(2)
                block_kind = "curve"
            block_lines = [line.strip()]
            continue
        if block_id and line.strip():
            block_lines.append(line)
            b = _BINS.match(line)
            if b:
                bins[b.group(1)] = b.group(2).strip()
    doc = flush()
    if doc:
        yield doc


def fetch(cfg: Config, source_cfg: SourceCfg, http: HttpClient) -> Iterator[Document]:
    extra = source_cfg.model_extra or {}
    repo_url = extra.get("repo_url", "https://github.com/speeduino/speeduino.git")
    local = cfg.resolve(extra.get("local_path", "data/raw/speeduino"))
    ini_rel = extra.get("ini_path", "reference/speeduino.ini")

    _ensure_repo(repo_url, Path(local), bool(extra.get("auto_update", True)))
    ini_path = Path(local) / ini_rel
    if not ini_path.exists():
        log.warning("tunerstudio_ini: %s missing after clone", ini_path)
        return
    text = ini_path.read_text(encoding="utf-8", errors="replace")
    url = f"https://github.com/speeduino/speeduino/blob/master/{ini_rel}"
    n = 0
    for doc in _parse_ini(text, url):
        n += 1
        yield doc
    log.info("tunerstudio_ini: %d table/curve definitions", n)
