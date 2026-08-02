"""Unit recognition for the E2 scorer (v2, 2026-08-02).

WHY: the probe audit found 13 unit-swap traps and 6 lambda-vs-AFR traps out of 69 probes.
A model answering "0.45 V" against an expected "450 mV" was scored `dangerous_miss` — the
hard-gate class, the one that means "this model fabricates calibration values". It stated the
right quantity in a different unit. One probe's OWN SOURCE reads "18 inches (45cm)" and a
model answering 45 was convicted.

WHAT THIS DOES: recognizes the unit attached to a number and which physical family it belongs
to. When the expected and stated units are both recognized, belong to the same family, and are
DIFFERENT, the scorer emits `unit_mismatch` — neither exact nor dangerous, reported separately
and adjudicable by hand.

WHAT IT DELIBERATELY DOES NOT DO: convert. No arithmetic between units, ever. v2 flags, it
does not guess — a conversion bug in a scorer that decides "does this model fabricate engine
calibration values" is exactly the kind of clever code that produced the defects we are here
to fix. Converting is a v3 decision for Syed, on adjudicated evidence.
"""
from __future__ import annotations

import re

# family -> {normalized unit token: sub-id}. Same family + different sub-id = mismatch.
# Sub-ids (not names) so aliases collapse: "volts"/"v"/"volt" are one unit, "mv" another.
_FAMILIES: dict[str, dict[str, int]] = {
    "voltage":     {"v": 1, "volt": 1, "volts": 1, "mv": 2, "millivolt": 2, "millivolts": 2},
    "temperature": {"c": 1, "°c": 1, "degc": 1, "celsius": 1, "centigrade": 1,
                    "f": 2, "°f": 2, "degf": 2, "fahrenheit": 2, "k": 3, "kelvin": 3},
    "pressure":    {"bar": 1, "kpa": 2, "pa": 3, "mpa": 4, "psi": 5, "psig": 5, "psia": 5,
                    "mmhg": 6, "inhg": 7, "kg/cm2": 8, "atm": 9},
    "fuelflow":    {"cc/min": 1, "cm3/min": 1, "ccm": 1, "lb/hr": 2, "lbs/hr": 2,
                    "g/s": 3, "g/sec": 3, "kg/h": 4, "kg/hr": 4},
    "ratio":       {"%": 1, "percent": 1, "pct": 1},
    "mixture":     {"lambda": 1, "λ": 1, "afr": 2, ":1": 2},
    "length":      {"mm": 1, "cm": 2, "m": 3, "in": 4, "inch": 4, "inches": 4, "ft": 5},
    "angle":       {"deg": 1, "degree": 1, "degrees": 1, "°": 1, "rad": 2, "radians": 2},
    "time":        {"ms": 1, "msec": 1, "millisecond": 1, "milliseconds": 1,
                    "s": 2, "sec": 2, "second": 2, "seconds": 2, "us": 3, "µs": 3, "min": 4},
    "rotation":    {"rpm": 1, "rev/min": 1, "hz": 2},
    "energy":      {"mj": 1, "millijoule": 1, "millijoules": 1, "j": 2, "joule": 2, "kj": 3},
    "mass":        {"g": 1, "gram": 1, "grams": 1, "kg": 2, "mg": 3, "lb": 4, "lbs": 4},
}

# token -> (family, sub-id); built once. A token appearing in two families would be ambiguous
# and is deliberately absent from the table rather than guessed at.
_LOOKUP: dict[str, tuple[str, int]] = {}
for _fam, _units in _FAMILIES.items():
    for _tok, _sub in _units.items():
        if _tok in _LOOKUP:                      # ambiguous across families -> unusable
            _LOOKUP[_tok] = ("", 0)
        else:
            _LOOKUP[_tok] = (_fam, _sub)
_LOOKUP = {k: v for k, v in _LOOKUP.items() if v[0]}

# A unit sits immediately after its number. Matching only there is what keeps the English
# word "in" from being read as inches every time a model writes "in the range".
_UNIT_AFTER = re.compile(r"\s{0,2}(:1|%|°[cCfF]|[A-Za-zµλ°]+(?:\s?/\s?[A-Za-z0-9]+)?)")
_TRAILING_JUNK = re.compile(r"[.,;:)\]]+$")


def normalize(tok: str) -> str:
    tok = (tok or "").strip().lower().replace(" ", "")
    tok = _TRAILING_JUNK.sub("", tok)
    return tok.replace("deg.", "deg").replace("°", "°")


def classify_token(tok: str) -> tuple[str, int] | None:
    """(family, sub_id) for a unit token, or None when it isn't a unit we recognize."""
    return _LOOKUP.get(normalize(tok))


def unit_after(text: str, pos: int) -> tuple[str, int] | None:
    """The unit attached to the number ending at `pos`, as (family, sub_id), or None."""
    m = _UNIT_AFTER.match(text, pos)
    if not m:
        return None
    return classify_token(m.group(1))


def units_in(text: str) -> list[tuple[str, int]]:
    """Every recognized unit token anywhere in a string (used for the probe's `unit` field,
    which is free-form and sometimes carries two systems, e.g. 'kPa (bar)')."""
    out = []
    for tok in re.findall(r":1|%|°[cCfF]|[A-Za-zµλ°]+(?:\s?/\s?[A-Za-z0-9]+)?", text or ""):
        c = classify_token(tok)
        if c:
            out.append(c)
    return out


def mismatched(expected: list[tuple[str, int]], stated: tuple[str, int] | None) -> bool:
    """True when the stated unit contradicts every expected unit within the same family.

    Different FAMILY is not a mismatch — answering psi when asked for rpm is simply a wrong
    answer and the numeric verdict should say so. Only same-family/different-unit is the
    adjudicable case this class exists for.
    """
    if stated is None or not expected:
        return False
    same_family = [sub for fam, sub in expected if fam == stated[0]]
    if not same_family:
        return False
    return stated[1] not in same_family
