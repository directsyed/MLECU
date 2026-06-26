"""EFI-reference HTML doc ingester — standalone-ECU / EFI manuals (reference tier).

Scrapes a curated list of doc pages (config `doc_sets`) into REFERENCE-tier Documents — the
canonical engine-management math that both informs the deterministic tuning algorithms AND
gives the Stage-B judge an authoritative tier to ground noisy forum claims against (no
circularity: the judge checks community claims against this trusted tier, never trains on the
data it filters).

First doc_set: the MegaSquirt MegaManual fundamentals (fuel equation, VE, tuning, injectors).
Public HTML, copyrighted → PRIVATE-corpus use only, not redistributed. (rusEFI is already
covered by the `rusefi_docs` source; Speeduino is redundant with rusEFI + MegaManual.)
"""
from __future__ import annotations

import logging
import re
import time
from typing import Iterator

from bs4 import BeautifulSoup

from ..core.config import Config, SourceCfg
from ..core.http import HttpClient
from ..core.models import Document

log = logging.getLogger(__name__)

name = "ecu_docs"


def _clean(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = (soup.title.get_text(strip=True) if soup.title else "") or ""
    text = (soup.body or soup).get_text("\n", strip=True)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text


def fetch(cfg: Config, source_cfg: SourceCfg, http: HttpClient) -> Iterator[Document]:
    extra = source_cfg.model_extra or {}
    doc_sets = extra.get("doc_sets", [])
    delay = max(0.3, 60.0 / max(1, source_cfg.rate_limit_per_min))
    for ds in doc_sets:
        ds_name = ds.get("name", "efi")
        base = ds["base_url"].rstrip("/") + "/"
        host = base.split("//", 1)[-1].split("/", 1)[0]
        kind = ds.get("kind", "efi_reference")
        domain = ds.get("domain", "general")
        min_chars = int(ds.get("min_chars", 600))
        http.configure_host(host, source_cfg.rate_limit_per_min)
        for page in ds.get("pages", []):
            url = base + page
            try:
                html = http.get_html(url, host=host)
            except Exception as e:
                log.warning("ecu_docs: %s failed: %s", url, e)
                continue
            title, text = _clean(html)
            if len(text) < min_chars:
                log.info("ecu_docs: %s thin (%d chars) — skip", page, len(text))
                continue
            yield Document(
                source=name, source_id=f"{ds_name}:{page}",
                title=title or f"{ds_name} {page}", text=text,
                kind=kind, domain=domain, tier="reference", url=url,
                meta={"doc_set": ds_name, "page": page},
            )
            time.sleep(delay)
