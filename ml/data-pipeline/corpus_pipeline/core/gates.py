"""Cheap, deterministic pre-filters, the CPU-side quality gate before the LLM judge.

This is the corpus-pipeline analog of Hardware Parser's matcher.py, but far simpler: it
does NOT decide substance (that's the Stage-B judge). It only drops obvious junk (empty /
pure-markup fragments) and tags flags the judge will use (has_numbers, has_table). Pure
functions, fully unit-testable.
"""
from __future__ import annotations

import re

from .config import GatesCfg
from .models import Document

_ALPHA = re.compile(r"[A-Za-z]")
_DIGIT = re.compile(r"\d")
# Tuning-relevant signal: numbers, tables, or domain terms suggest a substantive doc.
_TUNING_TERMS = re.compile(
    r"\b(afr|lambda|knock|boost|timing|ignition|fuel|injector|maf|map|vvt|avcs|"
    r"trim|duty|psi|rpm|wideband|dyno|scaling|throttle|load|ecu|rom)\b",
    re.IGNORECASE,
)


def evaluate(doc: Document, gates: GatesCfg) -> tuple[bool, str | None, list[str]]:
    """Return (kept, reject_reason, flags). Sets nothing, caller assigns to the Document."""
    flags: list[str] = []
    text = doc.text or ""

    if len(text.strip()) < gates.min_chars:
        return False, "too_short", flags
    if gates.require_alpha and not _ALPHA.search(text):
        return False, "no_alpha", flags

    if _DIGIT.search(text):
        flags.append("has_numbers")
    if "\t" in text or re.search(r"\|.*\|", text) or doc.kind in {"ecu_definition", "logger_param", "datalog"}:
        flags.append("has_table")
    if _TUNING_TERMS.search(text) or _TUNING_TERMS.search(doc.title or ""):
        flags.append("tuning_signal")
    if doc.domain == "subaru":
        flags.append("subaru")

    return True, None, flags


def apply(doc: Document, gates: GatesCfg) -> Document:
    """Run gates and stamp the result onto the Document."""
    kept, reason, flags = evaluate(doc, gates)
    doc.gate_status = "kept" if kept else f"rejected:{reason}"
    doc.gate_flags = flags
    return doc
