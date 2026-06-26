"""rusEFI documentation ingester — open engine-management theory (general domain).

Clones github.com/rusefi/rusefi_documentation (GPL) and ingests each markdown doc. A mix of
conceptual engine-management material (AlphaN, acceleration enrichment, triggers, sensors)
and per-vehicle configs; the gates/judge sort relevance downstream.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Iterator

from ..core.config import Config, SourceCfg
from ..core.http import HttpClient
from ..core.models import Document

log = logging.getLogger(__name__)

name = "rusefi_docs"


def _ensure_repo(repo_url: str, local: Path, auto_update: bool) -> None:
    if (local / ".git").exists():
        if auto_update:
            subprocess.run(["git", "-C", str(local), "pull", "--ff-only"], capture_output=True, text=True)
    else:
        local.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", repo_url, str(local)], capture_output=True, text=True)


def _first_heading(md: str, fallback: str) -> str:
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return fallback


def fetch(cfg: Config, source_cfg: SourceCfg, http: HttpClient) -> Iterator[Document]:
    extra = source_cfg.model_extra or {}
    repo_url = extra.get("repo_url", "https://github.com/rusefi/rusefi_documentation.git")
    local = cfg.resolve(extra.get("local_path", "data/raw/rusefi_documentation"))
    min_chars = int(extra.get("min_chars", 200))   # skip stub/redirect docs
    _ensure_repo(repo_url, local, bool(extra.get("auto_update", False)))

    for md_path in sorted(local.rglob("*.md")):
        if ".git" in md_path.parts:
            continue
        try:
            text = md_path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception as e:
            log.warning("read failed %s: %s", md_path.name, e)
            continue
        if len(text) < min_chars:
            continue
        rel = md_path.relative_to(local).as_posix()
        yield Document(
            source=name,
            source_id=rel,
            title=_first_heading(text, md_path.stem),
            text=text,
            kind="theory",
            domain="general",
            tier="reference",
            url=f"https://github.com/rusefi/rusefi_documentation/blob/master/{rel}",
            meta={"path": rel, "filename": md_path.name},
        )
