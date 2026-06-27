"""Map messy RomRaider/SSM2 CSV header strings to canonical channel roles.

RomRaider exports human column names with units in parens, e.g. "Mass Airflow (g/s)",
"AF Correction 1 (%)". The 219 SSM2 logger params already ingested in the corpus
(source="romraider_logger") are the authority for what these mean; this module collapses the
many spellings down to the handful of roles the algorithm + clamps actually consume.

First matching rule wins, so order matters: specific before generic (fine-knock before knock,
explicit wideband before anything else, learning/correction before any bare "af").
"""
from __future__ import annotations

import re

CANONICAL_ROLES = (
    "rpm", "maf_gs", "load", "wideband_afr", "af_correction", "af_learning",
    "knock_retard", "fine_knock_learn", "timing_total", "injector_duty",
    "iat", "coolant", "tps", "battery_v",
)

# (compiled pattern, role). Evaluated top-to-bottom; first hit wins.
_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"fine\s*knock", re.I), "fine_knock_learn"),
    (re.compile(r"knock", re.I), "knock_retard"),
    (re.compile(r"wideband|uego|\baem\b|\bwb\b|lambda", re.I), "wideband_afr"),
    (re.compile(r"a/?f\s*learn", re.I), "af_learning"),
    (re.compile(r"a/?f\s*correction|a/?f\s*corr", re.I), "af_correction"),
    (re.compile(r"engine\s*load|calculated\s*load|g/rev|\bload\b", re.I), "load"),
    (re.compile(r"mass\s*air|\bmaf\b|airflow|g/s", re.I), "maf_gs"),
    (re.compile(r"injector\s*duty|inj\s*duty|\bipw\b|injector\s*pulse|duty\s*cycle", re.I), "injector_duty"),
    (re.compile(r"ignition\s*total|total\s*timing|timing\s*advance|\btiming\b", re.I), "timing_total"),
    (re.compile(r"intake\s*air\s*temp|\biat\b", re.I), "iat"),
    (re.compile(r"coolant|\bclt\b|\bect\b|water\s*temp", re.I), "coolant"),
    (re.compile(r"throttle|\btps\b|pedal", re.I), "tps"),
    (re.compile(r"\brpm\b|engine\s*speed", re.I), "rpm"),
    (re.compile(r"battery|\bvolt", re.I), "battery_v"),
]


def map_header(header: str) -> str | None:
    """Return the canonical role for a header string, or None if it isn't one we consume."""
    h = header.strip()
    for pat, role in _RULES:
        if pat.search(h):
            return role
    return None
