"""Local book/PDF ingester — for owner-supplied copyrighted material (FSMs, tuning books).

Reads PDFs AND EPUBs from drop folders under `base_dir` (one subfolder per "collection", each
mapped to a kind/domain in config). Emits one Document per PDF page / per EPUB chapter (granular +
bounded; chunking is a Stage-C concern). Empty units are dropped by the gates.

  - PDF  -> pypdf reads the TEXT layer, one Document per page. A *scanned* PDF (image-only, common
    for old FSMs) yields no text -> needs OCR first (`ocrmypdf`), then re-run.
  - EPUB -> an EPUB is a zip of XHTML; we read the OPF spine for chapter order and extract text via
    bs4. No extra dependency (stdlib zipfile + the bs4 we already use for HTML sources).
"""
from __future__ import annotations

import logging
import re
import warnings
import zipfile
from typing import Iterator

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from pypdf import PdfReader

# EPUB content docs are XHTML; parsing them with the lxml HTML parser works fine and is standard —
# silence bs4's "you used an HTML parser on XML" notice so it doesn't spam the ingest log per chapter.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from ..core.config import Config, SourceCfg
from ..core.http import HttpClient
from ..core.models import Document

log = logging.getLogger(__name__)

name = "local_pdf"

_DEFAULT_COLLECTIONS = {
    "fsm": {"kind": "fsm_spec", "domain": "subaru"},
    "books": {"kind": "theory", "domain": "general"},
}


def _epub_chapters(path) -> list[tuple[int, str, str]]:
    """Return [(index, chapter_name, text)] from an EPUB in spine (reading) order.

    Resolves the OPF via META-INF/container.xml, reads its <spine> against the <manifest> for
    ordered content docs, and extracts text from each XHTML with bs4. Falls back to all html files
    sorted if the spine can't be parsed."""
    out: list[tuple[int, str, str]] = []
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        opf_path = None
        try:
            cont = z.read("META-INF/container.xml").decode("utf-8", "replace")
            m = re.search(r'full-path="([^"]+)"', cont)
            if m:
                opf_path = m.group(1)
        except Exception:
            pass
        ordered: list[str] = []
        if opf_path and opf_path in names:
            try:
                opf = BeautifulSoup(z.read(opf_path).decode("utf-8", "replace"), "xml")
                base = opf_path.rsplit("/", 1)[0] if "/" in opf_path else ""
                manifest = {it.get("id"): it.get("href") for it in opf.find_all("item")}
                for ref in opf.find_all("itemref"):
                    href = manifest.get(ref.get("idref"))
                    if not href:
                        continue
                    full = re.sub(r"/+", "/", f"{base}/{href}" if base else href)
                    if full in names:
                        ordered.append(full)
            except Exception:
                ordered = []
        if not ordered:
            ordered = sorted(n for n in names if n.lower().endswith((".xhtml", ".html", ".htm")))
        for idx, cname in enumerate(ordered, start=1):
            try:
                soup = BeautifulSoup(z.read(cname).decode("utf-8", "replace"), "lxml")
            except Exception:
                continue
            for t in soup(["script", "style"]):
                t.decompose()
            text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))
            out.append((idx, cname, text))
    return out


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

        # --- PDFs (one Document per page) ---
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

        # --- EPUBs (one Document per chapter) ---
        for epub in sorted(cdir.rglob("*.epub")):
            rel = epub.relative_to(base).as_posix()
            try:
                chapters = _epub_chapters(epub)
            except Exception as e:
                log.warning("local_pdf: epub open failed %s: %s", epub.name, e)
                continue
            n = len(chapters)
            kept = 0
            for idx, _cname, txt in chapters:
                if len(txt) < min_chars:
                    continue
                kept += 1
                yield Document(
                    source=name, source_id=f"{rel}#c{idx}",
                    title=f"{epub.stem} — ch{idx}/{n}", text=txt,
                    kind=kind, domain=domain, tier="reference", url=f"file://{epub}",
                    meta={"file": rel, "chapter": idx, "n_chapters": n, "collection": coll},
                )
            log.info("local_pdf: %s — %d/%d chapters with text (%s)", epub.name, kept, n,
                     "OK" if kept else "empty/DRM?")
