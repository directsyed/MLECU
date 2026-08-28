"""Parse a RomRaider Logger CSV export into a LogTable of canonical channels.

Tolerant by design: unknown columns are ignored, missing channels are simply absent (no crash),
non-numeric cells become NaN. Accepts a path, a Path, or raw CSV text.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .schema import map_header, prefer


@dataclass
class LogTable:
    """One parsed datalog: canonical role -> column of float samples (aligned by row)."""
    channels: dict[str, np.ndarray]
    raw_headers: tuple[str, ...] = ()
    sample_hz: float = 0.0
    source_path: str | None = None
    # role -> the headers that ALL claimed it, when more than one did. Empty is the healthy
    # case. Recorded rather than silently resolved: a collision means a role's MEANING depends
    # on column order, and RomRaider's column order is not stable between logging sessions.
    collisions: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def __len__(self) -> int:
        return max((len(v) for v in self.channels.values()), default=0)

    def has(self, role: str) -> bool:
        return role in self.channels

    def get(self, role: str, default=None):
        return self.channels.get(role, default)


def _looks_like_path(src) -> bool:
    if isinstance(src, Path):
        return True
    return isinstance(src, str) and "\n" not in src and len(src) < 4096 and Path(src).exists()


def _sample_hz(header: list[str], data: list[list[str]]) -> float:
    for ci, h in enumerate(header):
        if re.search(r"time", h, re.I):
            try:
                ts = np.array([float(r[ci]) for r in data if ci < len(r)])
            except ValueError:
                return 0.0
            if len(ts) < 2:
                return 0.0
            dt = float(np.median(np.diff(ts)))
            if dt <= 0:
                return 0.0
            if re.search(r"msec|millis|\bms\b", h, re.I):
                return 1000.0 / dt
            if re.search(r"\bsec\b|\bs\b", h, re.I):
                return 1.0 / dt
            return 1000.0 / dt  # default assumption: RomRaider logs time in msec
    return 0.0


def parse_romraider_csv(src, source_path: str | None = None) -> LogTable:
    if _looks_like_path(src):
        path = Path(src)
        text = path.read_text(encoding="utf-8")
        source_path = source_path or str(path)
    else:
        text = src

    rows = [r for r in csv.reader(io.StringIO(text)) if r and any(c.strip() for c in r)]
    if not rows:
        return LogTable({}, (), 0.0, source_path, {})

    header, data = rows[0], rows[1:]

    # Resolve columns -> roles (first column wins a role if duplicated).
    claims: dict[str, list[str]] = {}
    col_of: dict[str, int] = {}
    for ci, h in enumerate(header):
        role = map_header(h)
        if not role:
            continue
        claims.setdefault(role, []).append(h)
        col_of.setdefault(h, ci)
    role_col = {r: col_of[prefer(r, hs)] for r, hs in claims.items()}
    collisions = {r: tuple(hs) for r, hs in claims.items() if len(hs) > 1}

    channels: dict[str, np.ndarray] = {}
    for role, ci in role_col.items():
        col = np.empty(len(data), dtype=float)
        for ri, r in enumerate(data):
            try:
                col[ri] = float(r[ci])
            except (ValueError, IndexError):
                col[ri] = np.nan
        channels[role] = col

    return LogTable(channels, tuple(header), _sample_hz(header, data), source_path,
                    collisions)
