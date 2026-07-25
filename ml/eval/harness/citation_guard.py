"""Deterministic citation guard — cite-or-decline as CODE (plan of record 2026-07-25 §1).

Doctrine (pre-committed in ROADMAP 2026-07-10, empirically mandated by the showdown's
13-disobedience finding): a calibration value may be STATED only if it appears in the
retrieved evidence the model was shown. The prompt rider asks; this module enforces.
Instructions are requests, code is law — the ECU-clamp pattern applied at the data layer.

What it does, mechanically:
  1. Extract every number from the model's stated value.
  2. Extract every number from the retrieved snippet texts (raw + a "healed" variant that
     joins digit runs split by spaces/soft-hyphens — the PDF-mangling lesson of 2026-07-16).
  3. Every stated number must match some evidence number within rel_tol (default = E2's
     own 1%). Any unverified number -> the answer is mechanically converted to a decline.

What it deliberately does NOT do (anti-benchmark-maxxing contract):
  - It never sees probes, expected values, or the scorer — only (answer, evidence).
  - It cannot catch a present-but-wrong-selection number (right doc, wrong quantity) —
    named blind spot, measured by the retro-test, reported as leaked if it keeps the gate red.
  - Pre-guard behavior is always recorded alongside (attempted/blocked/leaked reporting):
    the clamp carries a gauge; model quality stays visible.
"""
from __future__ import annotations

import re

# leading-dot form included ('.84') — the 2026-07-25 retro-test caught probe e2-466-0's
# correct answer being mis-parsed for lack of it (same fix in e2.parse_number, scorer v1.1)
_NUM = re.compile(r"-?(?:\d+(?:[.,]\d+)?|[.]\d+)")
_REF_MARK = re.compile(r"\[REF\s+\d+\]")         # citation ids are not calibration values
_SPLIT_DIGITS = re.compile(r"(?<=\d)[  ­​\-](?=\d)")


def numbers_in(text: str | None) -> list[float]:
    """All numbers in a string, commas stripped ('1,500' -> 1500.0), [REF n] ids ignored."""
    if not text:
        return []
    text = _REF_MARK.sub(" ", text)
    return [float(m.group()) for m in _NUM.finditer(text.replace(",", ""))]


def _healed(text: str) -> str:
    """Join digit runs broken by spaces/soft-hyphens/zero-widths (PDF extraction damage)."""
    return _SPLIT_DIGITS.sub("", text)


def evidence_numbers(snippet_texts: list[str]) -> list[float]:
    pool: list[float] = []
    for t in snippet_texts:
        pool += numbers_in(t)
        healed = _healed(t)
        if healed != t:
            pool += numbers_in(healed)
    return pool


def _matches(stated: float, pool: list[float], rel_tol: float) -> bool:
    tol = max(abs(stated) * rel_tol, 1e-9)
    return any(abs(stated - p) <= tol for p in pool)


def verify(value: str | None, snippet_texts: list[str], rel_tol: float = 0.01) -> dict:
    """Verdict for a stated value against the evidence actually shown to the model.

    verdicts: declined (nothing stated — guard is a no-op), no_numbers (qualitative
    answer, passes), cited (every number grounded), blocked (>=1 unverified number).
    """
    if value in (None, ""):
        return {"verdict": "declined", "unverified": []}
    stated = numbers_in(value)
    if not stated:
        return {"verdict": "no_numbers", "unverified": []}
    pool = evidence_numbers(snippet_texts)
    unverified = [n for n in stated if not _matches(n, pool, rel_tol)]
    return {"verdict": "blocked" if unverified else "cited", "unverified": unverified}


def apply(answer: dict, snippet_texts: list[str], rel_tol: float = 0.01) -> tuple[dict, dict]:
    """(guarded_answer, guard_record). Blocked answers become mechanical declines; the
    original answer is preserved in the record for the attempted/blocked/leaked gauge."""
    rec = verify(answer.get("value"), snippet_texts, rel_tol)
    if rec["verdict"] == "blocked":
        return {"value": None, "must_retrieve": True}, rec
    return answer, rec
