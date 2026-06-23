"""Source registry. Maps source config keys to fetch callables.

Add a source: create sources/<x>.py with `name` + `fetch(cfg, source_cfg, http)`, import it
here, add it to REGISTRY, and add a `sources.<x>` block in config.yaml.
"""
from __future__ import annotations

from typing import Callable, Iterator

from ..core.config import Config, SourceCfg
from ..core.http import HttpClient
from ..core.models import Document
from . import romraider_defs

FetchFn = Callable[[Config, SourceCfg, HttpClient], Iterator[Document]]

REGISTRY: dict[str, FetchFn] = {
    "romraider_defs": romraider_defs.fetch,
    # rusefi_docs, fsm_pdf, books_pdf, forum_legacygt, forum_nasioc, forum_romraider,
    # kaggle_datalogs — added in the breadth phase.
}
