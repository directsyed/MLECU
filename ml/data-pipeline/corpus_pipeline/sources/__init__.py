"""Source registry. Maps source config keys to fetch callables.

Add a source: create sources/<x>.py with `name` + `fetch(cfg, source_cfg, http)`, import it
here, add it to REGISTRY, and add a `sources.<x>` block in config.yaml. phpBB boards share
one generic engine (forum_phpbb) bound per-site via fetch_for().
"""
from __future__ import annotations

from typing import Callable, Iterator

from ..core.config import Config, SourceCfg
from ..core.http import HttpClient
from ..core.models import Document
from . import (
    ecu_docs,
    forum_legacygt,
    forum_nasioc,
    forum_phpbb,
    forum_xenforo,
    local_pdf,
    romraider_defs,
    romraider_logger,
    rusefi_docs,
    tunerstudio_ini,
)

FetchFn = Callable[[Config, SourceCfg, HttpClient], Iterator[Document]]

REGISTRY: dict[str, FetchFn] = {
    "romraider_defs": romraider_defs.fetch,
    "romraider_logger": romraider_logger.fetch,
    "rusefi_docs": rusefi_docs.fetch,
    "forum_legacygt": forum_legacygt.fetch,
    "local_pdf": local_pdf.fetch,
    "ecu_docs": ecu_docs.fetch,
    # phpBB boards — one engine, per-site bindings (universal-first source expansion)
    "forum_speeduino": forum_phpbb.fetch_for("forum_speeduino"),
    "forum_msextra": forum_phpbb.fetch_for("forum_msextra"),
    "forum_romraider": forum_phpbb.fetch_for("forum_romraider"),
    "forum_nasioc": forum_nasioc.fetch,
    "tunerstudio_ini": tunerstudio_ini.fetch,
    # XenForo boards (VerticalScope 202 stub) — one engine, per-site bindings
    "forum_subaruforester": forum_xenforo.fetch_for("forum_subaruforester"),
    "forum_iwsti": forum_xenforo.fetch_for("forum_iwsti"),
    # kaggle_datalogs — later.
}
