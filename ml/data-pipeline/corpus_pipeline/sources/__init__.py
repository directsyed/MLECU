"""Source registry. Maps source config keys to fetch callables.

Add a source: create sources/<x>.py with `name` + `fetch(cfg, source_cfg, http)`, import it
here, add it to REGISTRY, and add a `sources.<x>` block in config.yaml.
"""
from __future__ import annotations

from typing import Callable, Iterator

from ..core.config import Config, SourceCfg
from ..core.http import HttpClient
from ..core.models import Document
from . import romraider_defs, romraider_logger, rusefi_docs

FetchFn = Callable[[Config, SourceCfg, HttpClient], Iterator[Document]]

REGISTRY: dict[str, FetchFn] = {
    "romraider_defs": romraider_defs.fetch,
    "romraider_logger": romraider_logger.fetch,
    "rusefi_docs": rusefi_docs.fetch,
    # fsm_pdf, books_pdf, forum_legacygt, forum_nasioc, kaggle_datalogs — next.
}
