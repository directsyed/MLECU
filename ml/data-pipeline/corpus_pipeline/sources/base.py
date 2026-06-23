"""Common types + helpers for source modules.

A source module sets `name` and defines `fetch(cfg, source_cfg, http) -> Iterator[Document]`,
yielding RAW Documents. It does NOT gate or judge — `gates.evaluate` and the Stage-B judge
own that. Wrap fetch bodies so one broken source never kills the pass (the orchestrator also
isolates per-source). Mirrors Hardware Parser's sources/base.py.
"""
from __future__ import annotations

import logging
from typing import Iterator, Protocol

from ..core.config import Config, SourceCfg
from ..core.http import HttpClient
from ..core.models import Document

log = logging.getLogger(__name__)


class Source(Protocol):
    name: str

    def fetch(
        self, cfg: Config, source_cfg: SourceCfg, http: HttpClient
    ) -> Iterator[Document]: ...


def safe_text(node) -> str:
    """bs4-node-or-string → clean text (lifted from Hardware Parser)."""
    if node is None:
        return ""
    return node.get_text(" ", strip=True) if hasattr(node, "get_text") else str(node).strip()
