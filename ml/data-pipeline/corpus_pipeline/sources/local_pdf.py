"""Local PDF ingester — for owner-supplied copyrighted material (FSMs, tuning books).

Reads PDFs from drop folders under `base_dir` (one subfolder per "collection", each mapped to
a kind/domain in config). Emits one Document PER PAGE (granular + bounded; chunking is a Stage-C
concern). Pages with no extractable text are skipped by the gates.

NOTE: pypdf reads the TEXT layer. A *scanned* PDF (image-only, common for old FSMs) yields no
text → those pages drop out. If your FSM is a scan, it needs OCR first (a future add — e.g.
`ocrmypdf` to bake a text layer in, then re-run this source).
"""
from __future__ import annotations

import logging
from typing import Iterator

from pypdf import PdfReader

from ..core.config import Config, SourceCfg
from ..core.http import HttpClient
from ..core.models import Document

log = logging.getLogger(__name__)

name = "local_pdf"

_DEFAULT_COLLECTIONS = {
    "fsm": {"kind": "fsm_spec", "domain": "subaru"},
    "books": {"kind": "theory", "domain": "general"},
}


def fetch(cfg: Config, source_cfg: SourceCfg, http: HttpClient) -> Iterator[Document]:
    extra = source_cfg.model_extra or {}
    base = cfg.resolve(extra.get("base_dir", "data/raw/pdfs"))
    collections = extra.get("collections", _DEFAULT_COLLECTIONS)
    min_chars = int(extra.get("min_chars", 80))

    if not base.exists():
        log.warning("local_pdf: drop dir %s does not exist (nothing to ingest yet)", base)
        return

    for coll, spec in collections.items():
        cdir = base / coll
        if not cdir.exists():
            continue
        kind = spec.get("kind", "fsm_spec")
        domain = spec.get("domain", "general")
        for pdf in sorted(cdir.rglob("*.pdf")):
            try:
                reader = PdfReader(str(pdf))
            except Exception as e:
                log.warning("local_pdf: open failed %s: %s", pdf.name, e)
                continue
            n_pages = len(reader.pages)
            rel = pdf.relative_to(base).as_posix()
            kept_pages = 0
            for i, page in enumerate(reader.pages, start=1):
                try:
                    txt = (page.extract_text() or "").strip()
                except Exception:
                    txt = ""
                if len(txt) < min_chars:
                    continue
                kept_pages += 1
                yield Document(
                    source=name, source_id=f"{rel}#p{i}",
                    title=f"{pdf.stem} — p{i}/{n_pages}", text=txt,
                    kind=kind, domain=domain, tier="reference", url=f"file://{pdf}",
                    meta={"file": rel, "page": i, "n_pages": n_pages, "collection": coll},
                )
            log.info("local_pdf: %s — %d/%d pages with text (%s)", pdf.name, kept_pages, n_pages,
                     "OK" if kept_pages else "NO TEXT LAYER — needs OCR?")
