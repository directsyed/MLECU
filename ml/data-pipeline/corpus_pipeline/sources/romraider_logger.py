"""RomRaider logger param defs → the SSM2 telemetry schema (feeds car/logging).

Parses RomRaider/logger/standard/logger.xml from the already-cloned SubaruDefs repo. Each
loggable channel (`<parameter>` = standard SSM2 params; `<ecuparam>` = ECU-specific extended
params) becomes one Document: name + units + conversion expr + SSM2 location. These define
exactly which channels can be logged (RPM, MAF, AFR correction/learning, knock, etc.).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from lxml import etree

from ..core.config import Config, SourceCfg
from ..core.http import HttpClient
from ..core.models import Document

log = logging.getLogger(__name__)

name = "romraider_logger"


def _units_and_exprs(el) -> tuple[list[str], list[str]]:
    units, exprs = [], []
    for c in el.iter("conversion"):
        u = c.get("units")
        if u and u not in units:
            units.append(u)
        ex = c.get("expr")
        if ex:
            exprs.append(f"{u or '?'}: {ex}")
    return units, exprs


def _param_doc(p) -> Document | None:
    pid = p.get("id")
    nm = p.get("name")
    if not pid or not nm:
        return None
    addr_el = p.find("address")
    addr = addr_el.text.strip() if (addr_el is not None and addr_el.text) else None
    units, exprs = _units_and_exprs(p)
    meta = {
        "id": pid, "name": nm, "desc": p.get("desc") or "", "param_class": "standard",
        "units": units, "address": addr,
        "ecubyteindex": p.get("ecubyteindex"), "ecubit": p.get("ecubit"),
    }
    lines = [
        f"SSM2 loggable parameter: {nm}",
        f"  id: {pid}",
        f"  units: {', '.join(units) if units else '(none)'}",
    ]
    if p.get("desc"):
        lines.append(f"  description: {p.get('desc')}")
    if addr:
        lines.append(f"  ssm2 address: {addr}")
    if exprs:
        lines.append("  conversion(s): " + "; ".join(exprs))
    return Document(source=name, source_id=pid, title=nm, text="\n".join(lines),
                    kind="logger_param", domain="subaru", tier="reference",
                    url="https://github.com/RomRaider/SubaruDefs/blob/master/RomRaider/logger/standard/logger.xml",
                    meta=meta)


def _ecuparam_doc(e) -> Document | None:
    eid = e.get("id")
    nm = e.get("name")
    if not eid or not nm:
        return None
    units, exprs = _units_and_exprs(e)
    n_ecus = sum(1 for _ in e.iter("ecu"))
    meta = {"id": eid, "name": nm, "desc": e.get("desc") or "", "param_class": "ecu_specific",
            "units": units, "supported_ecu_count": n_ecus}
    lines = [
        f"SSM2 ECU-specific loggable parameter: {nm}",
        f"  id: {eid}",
        f"  units: {', '.join(units) if units else '(none)'}",
        f"  supported ECUs: {n_ecus}",
    ]
    if e.get("desc"):
        lines.append(f"  description: {e.get('desc')}")
    if exprs:
        lines.append("  conversion(s): " + "; ".join(exprs))
    return Document(source=name, source_id=eid, title=nm, text="\n".join(lines),
                    kind="logger_param", domain="subaru", tier="reference",
                    url="https://github.com/RomRaider/SubaruDefs/blob/master/RomRaider/logger/standard/logger.xml",
                    meta=meta)


def fetch(cfg: Config, source_cfg: SourceCfg, http: HttpClient) -> Iterator[Document]:
    extra = source_cfg.model_extra or {}
    local = cfg.resolve(extra.get("local_path", "data/raw/SubaruDefs"))
    logger_file = extra.get("logger_file", "RomRaider/logger/standard/logger.xml")
    path = local / logger_file
    if not path.exists():
        log.warning("logger def missing: %s (clone SubaruDefs first)", path)
        return
    root = etree.parse(str(path), etree.XMLParser(recover=True)).getroot()
    for p in root.iter("parameter"):
        try:
            doc = _param_doc(p)
        except Exception as e:
            log.warning("parameter parse failed: %s", e); continue
        if doc:
            yield doc
    for el in root.iter("ecuparam"):
        try:
            doc = _ecuparam_doc(el)
        except Exception as e:
            log.warning("ecuparam parse failed: %s", e); continue
        if doc:
            yield doc
