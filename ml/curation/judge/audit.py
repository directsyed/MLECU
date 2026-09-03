"""Per-chunk JSONL audit trail, the forensic record independent of the DB.

One line per judged chunk with the RAW model output, token counts, ids and latency. If a
judgment ever looks wrong, this answers "what exactly did the model see and say" without
re-running anything. Files roll daily; the directory is gitignored.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class AuditLog:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        self.path = directory / f"judge-{day}.jsonl"

    def write(self, **record) -> None:
        record["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
