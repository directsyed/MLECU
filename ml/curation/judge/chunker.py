"""Structure-aware splitter for over-length docs. Pure function, no I/O.

Fast path: median doc is ~2.7k chars -> one untouched chunk. For the ~50 long forum threads
(max 330k) we split on structure in priority order — post separators, then headings, then
blank-line paragraphs — greedily packing segments up to max_chars. Never split mid-paragraph;
a single pathological paragraph longer than max_chars is hard-split as a last resort.
`overlap_chars` carries the previous chunk's tail into the next so a claim that straddles a
boundary is seen with its context at least once.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Ordered coarse->fine. The ingest layer normalizes forum threads with "--- post N ---"-style
# separators and PDFs with markdown-ish headings; plain blank lines are the universal fallback.
_BOUNDARIES = [
    re.compile(r"\n-{3,}.*?-{3,}\n"),      # post/document separators
    re.compile(r"\n(?=#{1,4} )"),           # markdown headings
    re.compile(r"\n\s*\n"),                 # paragraph breaks
]


@dataclass(frozen=True)
class Chunk:
    index: int
    n_chunks: int
    text: str


def _segments(text: str, max_chars: int, level: int = 0) -> list[str]:
    """Split into segments each <= max_chars, using the coarsest boundary that works."""
    if len(text) <= max_chars:
        return [text]
    if level >= len(_BOUNDARIES):
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]  # pathological
    parts = _BOUNDARIES[level].split(text)
    out: list[str] = []
    for p in parts:
        if p and p.strip():
            out.extend(_segments(p, max_chars, level + 1))
    return out or [text[:max_chars]]


def chunk(text: str, max_chars: int = 24000, overlap_chars: int = 600) -> list[Chunk]:
    if len(text) <= max_chars:
        return [Chunk(0, 1, text)]
    segs = _segments(text, max_chars)
    packed: list[str] = []
    cur = ""
    for s in segs:
        if cur and len(cur) + len(s) + 2 > max_chars:
            packed.append(cur)
            cur = (cur[-overlap_chars:] + "\n\n" if overlap_chars else "") + s
        else:
            cur = f"{cur}\n\n{s}" if cur else s
    if cur.strip():
        packed.append(cur)
    return [Chunk(i, len(packed), t) for i, t in enumerate(packed)]


def aggregate(scores: list[int], lengths: list[int], mode: str = "min") -> int:
    """Doc-level rollup of per-chunk scores. 'min' = a doc is only as trustworthy as its
    worst chunk (pair harvesting still selects per-chunk, so good chunks aren't lost)."""
    if not scores:
        raise ValueError("no chunk scores to aggregate")
    if mode == "min":
        return min(scores)
    if mode == "mean":
        return round(sum(scores) / len(scores))
    if mode == "weighted_mean":
        total = sum(lengths)
        return round(sum(s * n for s, n in zip(scores, lengths)) / max(1, total))
    raise ValueError(f"unknown aggregate mode: {mode}")
