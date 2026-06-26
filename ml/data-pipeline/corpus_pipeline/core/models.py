"""Document dataclass + SQLite schema — THE data contract for the corpus pipeline.

A Document is one ingestible unit (an ECU definition, a forum thread, an FSM section,
a theory chunk). Sources emit RAW Documents; `gates` sets gate_status/flags; the Stage-B
LLM judge later sets judgment_status/judge_score. Mirrors the Hardware Parser models.py
convention (dataclass + SCHEMA_SQL + utcnow_iso), adapted from listings to documents.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Document:
    source: str                       # registry key, e.g. "romraider_defs"
    source_id: str                    # unique within source (dedup key)
    title: str
    text: str                         # normalized body (what gets gated / embedded / judged)
    kind: str = "doc"                 # ecu_definition | logger_param | forum_thread | fsm_spec | theory | efi_reference
    domain: str = "general"           # "subaru" | "general"
    tier: str = "community"           # "reference" (trusted/authoritative — judge grounds on it) | "community" (noisy, needs judging)
    url: str | None = None            # provenance link/path
    meta: dict = field(default_factory=dict)   # structured fields (make/model/year/ecuid/tables/...)
    # derived / pipeline-managed
    content_hash: str = ""            # change detection + content dedup
    token_est: int = 0
    gate_status: str = "pending"      # pending | kept | rejected:<reason>
    gate_flags: list = field(default_factory=list)
    judgment_status: str = "pending"  # pending | judged
    judge_score: int | None = None    # 1-5 once the Stage-B judge runs

    def __post_init__(self) -> None:
        if not self.content_hash:
            h = hashlib.sha1(f"{self.source}\x00{self.source_id}\x00{self.text}".encode("utf-8"))
            self.content_hash = h.hexdigest()
        if not self.token_est:
            self.token_est = max(1, len(self.text) // 4)  # ~4 chars/token rough estimate


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS document (
    id               INTEGER PRIMARY KEY,
    source           TEXT NOT NULL,
    source_id        TEXT NOT NULL,
    kind             TEXT NOT NULL DEFAULT 'doc',
    domain           TEXT NOT NULL DEFAULT 'general',
    tier             TEXT NOT NULL DEFAULT 'community',
    title            TEXT,
    text             TEXT NOT NULL,
    url              TEXT,
    meta_json        TEXT,
    content_hash     TEXT,
    token_est        INTEGER NOT NULL DEFAULT 0,
    gate_status      TEXT NOT NULL DEFAULT 'pending',
    gate_flags       TEXT,
    judgment_status  TEXT NOT NULL DEFAULT 'pending',
    judge_score      INTEGER,
    first_seen       TEXT NOT NULL,
    last_seen        TEXT NOT NULL,
    miss_streak      INTEGER NOT NULL DEFAULT 0,
    gone_at          TEXT,
    UNIQUE(source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_doc_source ON document(source);
CREATE INDEX IF NOT EXISTS idx_doc_gate ON document(gate_status);
CREATE INDEX IF NOT EXISTS idx_doc_judgment ON document(judgment_status, gate_status);

CREATE TABLE IF NOT EXISTS poll_run (
    id          INTEGER PRIMARY KEY,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    source      TEXT NOT NULL,
    ok          INTEGER NOT NULL DEFAULT 0,
    fetched     INTEGER NOT NULL DEFAULT 0,
    kept        INTEGER NOT NULL DEFAULT 0,
    new_count   INTEGER NOT NULL DEFAULT 0,
    error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_poll_started ON poll_run(started_at);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def loads(s: str | None):
    if not s:
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None
