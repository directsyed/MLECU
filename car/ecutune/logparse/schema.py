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
    "iat", "coolant", "tps", "battery_v", "fuel_system_status", "target_afr",
)

# SSM2 fuel-system status codes (def E33: "[8 = CL (normal)][10 = OL (normal)]
# [7 = OL insufficient ECT][14 = OL due to system failure]"). Only CL_NORMAL carries a
# meaningful fuel trim -- in open loop A/F Correction is FROZEN (measured sd 0.04 vs 9.75
# in closed loop), so open-loop samples silently drag a binned trim toward zero.
CL_NORMAL = 8.0

# Headers that must NEVER map to a role, checked BEFORE _RULES.
#
# Every entry here was found (2026-08-12) to collide with a REQUIRED capture channel when the
# real RomRaider v370 parameter names are used instead of the idealised ones in the test fixture.
# A collision is silent and destructive: two columns map to one role and the later one wins, so a
# required channel ends up holding a physically unrelated quantity.
#
#   "Mass Airflow Sensor Voltage"          -> maf_gs      (volts overwriting g/s)
#   "Throttle Sensor Voltage"              -> tps         (volts overwriting %)
#   "Rear O2 Heater Voltage"               -> battery_v   (destroys the channel pull 3 depends on)
#   "A/F Adjustment Voltage"               -> battery_v   (same)
#   "Differential Pressure Sensor Voltage" -> battery_v   (same)
#   "Primary/Secondary Wastegate Duty Cycle" -> injector_duty  (boost duty read as fuelling)
_IGNORE: tuple[re.Pattern, ...] = (
    re.compile(r"sensor\s*voltage", re.I),
    re.compile(r"heater\s*voltage", re.I),
    re.compile(r"adjustment\s*voltage", re.I),
    re.compile(r"motor\s*voltage", re.I),
    re.compile(r"wastegate", re.I),
)

# (compiled pattern, role). Evaluated top-to-bottom; first hit wins.
_RULES: list[tuple[re.Pattern, str]] = [
    # RomRaider's real name is "Fine Learning Knock Correction" (P91), so the words are NOT
    # adjacent; the optional middle group is what makes the real export map correctly.
    # Matches "CL/OL Fueling*" and nothing else. Deliberately NOT r"closed\s*loop":
    # that would also swallow "Closed Loop Fueling Target", a different channel.
    (re.compile(r"\bcl\s*/\s*ol\b", re.I), "fuel_system_status"),
    (re.compile(r"fine\s*(learn\w*\s*)?knock", re.I), "fine_knock_learn"),
    (re.compile(r"knock", re.I), "knock_retard"),
    # MUST precede the wideband rule: "Closed Loop Fueling Target (2-byte)* (lambda)"
    # carries "lambda" in its units and was silently landing on wideband_afr, i.e. the
    # ECU's TARGET overwriting the MEASURED AFR. It only escaped notice because the AEM
    # happened to sit in an earlier column and first-column-wins saved us. Found 2026-08-27.
    (re.compile(r"fuel\w*\s*target", re.I), "target_afr"),
    (re.compile(r"wideband|uego|\baem\b|\bwb\b|lambda", re.I), "wideband_afr"),
    (re.compile(r"a/?f\s*learn", re.I), "af_learning"),
    (re.compile(r"a/?f\s*correction|a/?f\s*corr", re.I), "af_correction"),
    (re.compile(r"engine\s*load|calculated\s*load|g/rev|\bload\b", re.I), "load"),
    (re.compile(r"mass\s*air|\bmaf\b|airflow|g/s", re.I), "maf_gs"),
    # Bare "duty cycle" was removed: it caught the wastegate params. "Injector Duty Cycle" is
    # still matched by the injector-qualified alternative.
    (re.compile(r"injector\s*duty|inj\s*duty|\bipw\b|injector\s*pulse", re.I), "injector_duty"),
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
    for pat in _IGNORE:
        if pat.search(h):
            return None
    for pat, role in _RULES:
        if pat.search(h):
            return role
    return None
