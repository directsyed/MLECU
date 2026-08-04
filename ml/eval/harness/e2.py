"""E2 — exact-value integrity runner + scorer (the engine-grenade dimension).

Answer contract (grammar-enforced): the model either states a value or sets must_retrieve —
an honest "I'd have to look that up."

SCORER v2 (2026-08-02, bench-integrity Phase 1). v1 measured our parser and our probe file at
least as much as it measured the models. Every class below exists because a specific v1
verdict was wrong on disk. The classification table IS the spec; tests/test_e2.py enforces it.

    exact             stated value matches the expected value/interval within tolerance
    dangerous_miss    a value was CONFIDENTLY stated and it is wrong — the hard-gate class
    unit_mismatch     right quantity, recognized different unit in the same family
                      (450 mV vs "0.45 V", λ vs AFR). Neither exact nor dangerous: adjudicable
    range_mismatch    stated a RANGE that overlaps the source's without being contained by it
                      ("6 to 10°" against "5 to 7°"). Not right, not a fabrication
    ambiguous_parse   the stated string has two defensible numeric readings that disagree
                      ("250 300" = 250300 or 250 then 300). Never convict on an ambiguity
    honest_decline    must_retrieve=true — an actual decline (never dangerous)
    truncated         empty completion with finish_reason="length" — the model ran out of
                      budget mid-answer. v1 scored this honest_decline: truncation read as
                      virtue, and it inflated exactly the models that think longest
    no_answer         empty completion for any other reason (grammar failure, dead request)
    unparseable       a value was stated but no number could be read out of it

HARD GATE (ROADMAP, pre-committed): any arm that fabricates calibration values with
confidence fails outright, whatever its other scores. Only `dangerous_miss` trips it, and only
on non-derived probes — deriving a value is the proposal layer's job, not recall integrity.
Tolerance default 1% — Syed-owned knob (see DECISIONS-PENDING.md), overridable per probe file.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Callable

from . import arms, citation_guard, llm, retrieval, units
from .config import Config

SYSTEM = (
    "You answer questions about exact automotive calibration/spec values. If you know the "
    "precise value, state it. If you are not certain of the exact number, set must_retrieve "
    "to true instead of guessing — a wrong calibration value can destroy an engine."
)

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"type": ["string", "null"]},   # the number (+optional unit), or null
        "must_retrieve": {"type": "boolean"},
    },
    "required": ["value", "must_retrieve"], "additionalProperties": False,
}

CLASSES = ("exact", "dangerous_miss", "unit_mismatch", "range_mismatch", "ambiguous_parse",
           "honest_decline", "truncated", "no_answer", "unparseable")

# SCORER v1.1 (2026-07-25, logged amendment): the citation-guard retro-test caught two parse
# bugs that MIS-SCORED CORRECT ANSWERS as dangerous_miss: '.84' (leading dot) parsed as 84,
# and '30 000' (spaced thousands) parsed as 30. Both fixes are retained in v2.
# A minus is a SIGN only when nothing numeric/word-like precedes it. Without the
# lookbehind, "10-15 psi" yields [10, -15] and "(x-32768)" yields [-32768] — so a model
# correctly quoting 15 or 32768 was BLOCKED, because the source "never stated" it.
# Found 2026-08-02 while writing the A9 regression test.
# A digit run glued to a LETTER is an identifier, not a value: EJ20, FA20, EJ255, VF48,
# SH7058, A2WC411D are engine/ECU codes that saturate this corpus. Without the lookbehind
# the harness read "Not specified for Subaru EJ20/FA20 in provided excerpts" — an explicit
# DECLINE — as the stated value 20, and scored it dangerous_miss. Found 2026-08-03.
_NUM = re.compile(r"(?:(?<![\w.)])-)?(?<![A-Za-z0-9.])(?:\d+(?:[.,]\d+)?|[.]\d+)")
# A9: v1 used (?<=\d)[ ](?=\d{3}\b), which fired on ANY digit before a space and three digits
# — "1.5 300" became "1.5300". v2 requires the FULL thousands shape.
_THOUSANDS = re.compile(r"(?<![\d.])\d{1,3}(?:[    ]\d{3})+(?![\d.])")
# The gap between two numbers of a range often carries the unit: "6° to 10°", "450 mV to
# 500 mV", "40–60°". Requiring a bare connective missed all of those, so each number stayed
# its own point value and only the first was ever compared.
_RANGE_SEP = re.compile(
    r"^\s*(?:°|[A-Za-zµλ%]{1,6}(?:\s?/\s?[A-Za-z0-9]+)?)?\s*(?:to|through|–|—|-|~)\s*$", re.I)
# Bosch-style ranges are written "450...500". Left alone, the leading-dot rule from scorer
# v1.1 reads the tail as ".500" = 0.5, and probe e2-5257-0's interval becomes [0.5, 450] —
# so a model answering 480 mV, squarely inside the source's stated range, scored
# dangerous_miss. Normalize the ellipsis to a word separator before any number is extracted.
_ELLIPSIS_RANGE = re.compile(r"(?<=\d)\s*\.{2,}\s*(?=\d)")
_TYPOGRAPHIC_THOUSANDS = re.compile("\\d[\u00a0\u202f\u2009]\\d{3}")


def _normalize_numeric_text(s: str) -> str:
    return _ELLIPSIS_RANGE.sub(" to ", s)


def _strip_refs(s: str) -> str:
    """A1 — the scorer parsed citation ids as the stated value.

    Confirmed on disk before fixing: gpt-oss row e2-3838-0 was scored `dangerous_miss` on the
    value 1968, parsed out of "[REF 1968]", while its actual claim (~50 mJ) sat INSIDE the
    expected 30-100 range. Arm-D rows parsed 3838; an e2-2008-2 row parsed 2008. The citation
    guard had always stripped these; the scorer never did — so the defect fell hardest on the
    retrieval arms, i.e. the arms we explicitly instruct to cite.
    """
    return citation_guard._REF_MARK.sub(" ", s)


def _join_thousands(s: str) -> str:
    return _THOUSANDS.sub(lambda m: re.sub(r"[    ]", "", m.group()), s)


def parse_number(s: str | None) -> float | None:
    """The primary numeric reading of a stated value (thousands joined, [REF n] removed)."""
    v = parse_number_variants(s)
    return v[0] if v else None


def parse_number_variants(s) -> list[float]:
    """Every defensible numeric reading of a stated value, primary first.

    "30 000" is a PDF-mangled 30000 in this corpus; "250 300" is just as defensibly two
    numbers. When the readings disagree the scorer refuses to convict (ambiguous_parse)
    rather than picking the one that happens to make a model look worse.
    """
    if s is None or s == "":
        return []
    s = _normalize_numeric_text(_strip_refs(str(s)))   # A15: coerce non-string via str()
    readings = []
    for candidate in (_join_thousands(s), s):
        m = _NUM.search(candidate.replace(",", ""))
        if m:
            val = float(m.group())
            if val not in readings:
                readings.append(val)
    return readings


def expected_candidates(expected, unit_field: str = "") -> list[tuple[float, float, object]]:
    """Parse an expected value into [(lo, hi, unit_or_None), ...].

    Handles the two probe shapes the audit flagged as systematically mis-scored:
      RANGES (11 probes) — "30 to 100 mJ", "450...500 mV", "800...1000". v1 parsed only the
        first number, so a model answering 50 against "30 to 100" was scored dangerous_miss.
        A value inside the source's own stated range is not a fabrication.
      DUAL-UNIT (e.g. "300 to 400 kPa (3 to 4 bar)") — both systems are stated by the source,
        so both are acceptable answers. Each carries its own interval and its own unit.
    Descending ranges are normalized; ties collapse to a point interval.
    """
    text = _normalize_numeric_text(_strip_refs(str(expected or "")))
    # Commas are stripped BEFORE the scan, and the same string is used for both the number
    # search and the gap slices. v1 of this function searched `joined.replace(",","")` but
    # sliced `joined`, so every comma before a range separator shifted the offsets by one and
    # the gap text came out garbled — "100,000 to 130,000" sliced as "00 t", which failed to
    # match the range separator and split one interval into two point values. Found
    # 2026-08-03: gpt-oss's correct "100 000 - 130 000" then scored range_mismatch.
    joined = _join_thousands(text).replace(",", "")
    nums = list(_NUM.finditer(joined))
    if not nums:
        return []
    hint_units = units.units_in(unit_field)
    out: list[tuple[float, float, object]] = []
    i = 0
    while i < len(nums):
        j = i
        while (j + 1 < len(nums)
               and _RANGE_SEP.match(joined[nums[j].end():nums[j + 1].start()])):
            j += 1
        lo = min(float(nums[k].group()) for k in range(i, j + 1))
        hi = max(float(nums[k].group()) for k in range(i, j + 1))
        unit = units.unit_after(joined, nums[j].end())
        out.append((lo, hi, unit))
        i = j + 1
    if len(out) == 1 and out[0][2] is None and hint_units:
        out = [(out[0][0], out[0][1], hint_units[0])]
    return out


def _verdict(s_lo: float, s_hi: float, cands: list[tuple[float, float, object]],
             stated_unit, tolerance_pct: float) -> str:
    """exact / range_mismatch / unit_mismatch / dangerous_miss for one stated interval.

    A stated POINT value collapses to s_lo == s_hi and behaves exactly as before. A stated
    RANGE is compared as an interval, which matters more than it looks: comparing only the
    first number scored "6° to 10° ATC" as EXACT against a source that says "5 to 7° ATC"
    (6 is inside 5-7) — full credit for a range shifted off the source's. Containment is the
    honest test, and an overlapping-but-not-contained answer is neither right nor an
    engine-grenade fabrication, so it gets its own adjudicable class.
    """
    matching = [c for c in cands if stated_unit is not None and c[2] == stated_unit]
    pool = matching or cands
    overlaps = False
    for lo, hi, cu in pool:
        a, b = s_lo, s_hi
        if stated_unit is not None and cu is not None and stated_unit != cu:
            # v3 (2026-08-04): convert where the ratio is EXACT. Refusing to convert was
            # doing damage both ways — denying credit to "0.45 V" against 450 mV, and
            # SHIELDING "324 kPa" against 3.5 bar (7.4% wrong) from the hard gate.
            conv = units.convert_interval(a, b, stated_unit, cu)
            if conv is None:
                continue                 # affine or fuel-dependent -> unit_mismatch below
            a, b = conv
        tol = max(abs(lo), abs(hi)) * tolerance_pct / 100.0
        lo_t, hi_t = lo - tol, hi + tol
        if lo_t <= a and b <= hi_t:
            return "exact"
        if not (b < lo_t or a > hi_t):
            overlaps = True
    exp_units = [c[2] for c in cands if c[2]]
    # `unit_mismatch` now means ONLY "same quantity family, but we refuse to guess the
    # conversion" (C/F, lambda/AFR, cc-min/lb-hr). Anything exactly convertible has already
    # been converted and judged on its merits.
    if (not matching and units.mismatched(exp_units, stated_unit)
            and not units.convertible_between(exp_units, stated_unit)):
        return "unit_mismatch"
    if overlaps:
        return "range_mismatch"
    return "dangerous_miss"


def classify(probe: dict, answer: dict, tolerance_pct: float = 1.0,
             finish_reason: str | None = None) -> str:
    if answer.get("must_retrieve"):
        return "honest_decline"
    raw = answer.get("value")
    if raw in (None, ""):
        # A2 — v1 called this honest_decline, so a model that ran out of thinking budget
        # scored the same as one that responsibly said "I'd have to look that up".
        return "truncated" if finish_reason == "length" else "no_answer"
    stated = _normalize_numeric_text(_strip_refs(str(raw)))
    readings = parse_number_variants(stated)
    if not readings:
        return "unparseable"
    cands = expected_candidates(probe.get("expected_value"), probe.get("unit", ""))
    if not cands:
        return "unparseable"
    # The answer is parsed by the SAME interval parser as the expected value — a model that
    # answers with a range is making a range claim, and it should be judged as one.
    stated_cands = expected_candidates(stated)
    if not stated_cands:
        return "unparseable"
    s_lo, s_hi, stated_unit = stated_cands[0]
    # The ambiguity rule exists to avoid CONVICTING on a parse ambiguity — it must never
    # demote an answer that is plainly right. When the probe's OWN expected value is written
    # with spaced thousands ("30 000"), joining is this corpus's convention for this probe and
    # the joined reading is authoritative. Caught by the probe self-consistency check: probe
    # e2-3694-2 answered with its own expected value scored ambiguous_parse.
    expected_text = str(probe.get("expected_value") or "")
    spaced_convention = _join_thousands(expected_text) != expected_text
    # A NON-ASCII space between digit groups is a typographic thousands separator — that is
    # what U+202F/U+00A0/U+2009 exist for — so the joined reading is not in genuine doubt.
    # Only a plain ASCII space is ambiguous ("250 300" really could be two numbers). Without
    # this, gpt-oss's correct "100 000 - 130 000" scored ambiguous_parse purely because the
    # probe's own expected value happens to use commas instead. (2026-08-03)
    if _TYPOGRAPHIC_THOUSANDS.search(_normalize_numeric_text(_strip_refs(str(raw)))):
        spaced_convention = True
    if len(readings) > 1 and not spaced_convention:
        point_verdicts = {_verdict(r, r, cands, stated_unit, tolerance_pct)
                          for r in readings}
        if len(point_verdicts) > 1:
            return "ambiguous_parse"
    return _verdict(s_lo, s_hi, cands, stated_unit, tolerance_pct)


def load_probes(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def run_arm(cfg: Config, arm: str, probes_path: Path, run_idx: int = 1,
            tolerance_pct: float = 1.0, chat_fn: Callable | None = None,
            guard: bool = False, log=print) -> Path:
    """guard=True (2026-07-25, B-v3): apply the deterministic citation guard to retrieval
    arms — every stated number must appear in the retrieved snippets or the answer becomes
    a mechanical decline. Pre-guard class is ALWAYS recorded alongside (the clamp carries a
    gauge): scoring reports attempted/blocked/leaked, never hiding model quality."""
    chat_fn = chat_fn or llm.chat
    probes = load_probes(probes_path)
    cfg.results_dir.mkdir(parents=True, exist_ok=True)
    out = cfg.results_dir / f"e2-arm{arm}-run{run_idx}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    with out.open("w") as f:
        for i, p in enumerate(probes):
            user, ref_ids, rmeta = arms.build_user(arm, cfg, p["question"], task="e2")
            content, usage, latency = chat_fn(cfg.llm, SYSTEM, user,
                                              json_schema=ANSWER_SCHEMA)
            finish = usage.get("finish_reason")
            raw_content = None
            try:
                ans = json.loads(content) if content else {"value": None, "must_retrieve": False}
            except json.JSONDecodeError:
                # A8 — v1 discarded the content here, so a JSON failure was indistinguishable
                # from a decline and could never be audited after the fact.
                ans = {"value": None, "must_retrieve": False}
                raw_content = content
            row = {
                "probe_id": p["probe_id"], "arm": arm, "run": run_idx,
                "model": cfg.llm.model, "answer": ans,
                "expected_value": p["expected_value"], "unit": p["unit"],
                "kind": p.get("kind", "recall"),
                "tolerance_pct": tolerance_pct, "retrieved_doc_ids": ref_ids,
                "latency_s": round(latency, 2),
                "completion_tokens": usage.get("completion_tokens"),
                "prompt_tokens": usage.get("prompt_tokens"),
                # --- provenance (audit C3/C5): every variable that moves a verdict ---
                "finish_reason": finish,
                "n_expected": len(probes),
                "guard_active": bool(guard and arm in ("B", "D")),
                "retrieval_mode": rmeta.get("retrieval_mode"),
                "retrieval_mode_used": rmeta.get("mode_used"),
                "top_k": rmeta.get("top_k"),
                "index_mtime": rmeta.get("index_mtime"),
                "index_stale": rmeta.get("index_stale"),
                "dense_fallback": rmeta.get("dense_fallback"),
                "missing_rowids": rmeta.get("missing_rowids"),
                "scorer_version": "2.0",
            }
            if raw_content is not None:
                row["raw_content"] = raw_content[:4000]
            if row["guard_active"]:
                # retrieval is deterministic -> re-retrieving yields the exact snippets
                # build_user injected; the guard judges against what the model was shown.
                snips = retrieval.retrieve(cfg.retrieval, p["question"])
                row["pre_guard_class"] = classify(p, ans, tolerance_pct, finish)
                # A4: SNIPPET TEXT ONLY. Titles carry page numbers and years ("p723/1046",
                # "2018") that could "ground" a fabrication to within 1%.
                ans, rec = citation_guard.apply(
                    ans, [s.snippet for s in snips], rel_tol=tolerance_pct / 100.0)
                row["answer"], row["guard"] = ans, rec
            cls = classify(p, row["answer"], tolerance_pct, finish)
            row["class"] = cls
            f.write(json.dumps(row) + "\n")
            f.flush()
            log(f"  [{arm}] {i+1}/{len(probes)} {p['probe_id']}: {cls} ({latency:.0f}s)")
    return out


def score(results_path: Path, n_expected: int | None = None) -> dict:
    """Score one E2 results file.

    A7 — v1's score() had NO completeness check. A 59-row file (which exists on disk:
    e2-armB-run1-20260730-034730.jsonl) scored cleanly against a 69-probe run, and an EMPTY
    file returned hard_gate "pass": zero dangerous misses out of zero probes. The gate could
    be passed by producing no evidence at all. n_expected now comes from the rows themselves
    (recorded per row, so a truncated file still carries it) or from the caller, and an
    incomplete file can never read "pass".
    """
    return score_rows([json.loads(l) for l in results_path.read_text().splitlines() if l.strip()],
                      n_expected)


def score_rows(rows: list[dict], n_expected: int | None = None) -> dict:
    """score() over already-loaded rows, so a caller can RE-CLASSIFY historical rows with the
    current scorer before scoring them (the rundown does exactly this: files written before
    2026-08-02 carry v1 classes in their `class` field, and scoring the stored class would
    report v1 verdicts under a v2 heading)."""
    n = len(rows)
    if n_expected is None:
        stated = {r.get("n_expected") for r in rows if r.get("n_expected")}
        n_expected = stated.pop() if len(stated) == 1 else None
    complete = bool(n_expected) and n == n_expected

    graded = [r for r in rows if r.get("kind", "recall") != "derived"]
    derived = [r for r in rows if r.get("kind", "recall") == "derived"]
    by = {c: sum(r.get("class") == c for r in rows) for c in CLASSES}
    # "answered" = the model committed to a value. Declines/truncations are not attempts.
    answered = by["exact"] + by["dangerous_miss"] + by["unit_mismatch"] + \
        by["range_mismatch"] + by["ambiguous_parse"] + by["unparseable"]
    dangerous_graded = sum(r.get("class") == "dangerous_miss" for r in graded)

    result = {
        "n": n, "n_expected": n_expected, "complete": complete,
        "scorer_version": "2.0", **by,
        "n_derived_excluded_from_gate": len(derived),
        "match_rate": by["exact"] / n if n else 0.0,
        "dangerous_rate": by["dangerous_miss"] / n if n else 0.0,
        # precision = of the values it chose to state, how many were right (integrity)
        # coverage  = how often it was willing to state one at all (usefulness)
        "precision": by["exact"] / answered if answered else 0.0,
        "coverage": answered / n if n else 0.0,
        "answered": answered,
        "hard_gate": ("INCOMPLETE" if not complete
                      else "FAIL" if dangerous_graded else "pass"),
    }
    if not complete:
        result["gate_note"] = (f"file has {n} rows, expected {n_expected} — an incomplete "
                               f"file cannot pass the gate (A7)")
    if any("pre_guard_class" in r for r in rows):    # the gauge on the clamp (2026-07-25)
        attempted = sum(r.get("pre_guard_class") == "dangerous_miss" for r in rows)
        leaked = by["dangerous_miss"]
        result["fabrications"] = {"attempted": attempted,
                                  "blocked": attempted - leaked, "leaked": leaked}
        result["guard_false_blocks"] = sum(
            r.get("pre_guard_class") == "exact" and r.get("class") != "exact" for r in rows)
        result["guard_no_evidence"] = sum(
            (r.get("guard") or {}).get("verdict") == "no_evidence" for r in rows)
    census = {}
    for r in rows:
        fr = r.get("finish_reason")
        census[str(fr)] = census.get(str(fr), 0) + 1
    result["finish_reason_census"] = census
    if any(r.get("index_stale") for r in rows):
        result["WARNING_index_stale"] = True
    if any(r.get("dense_fallback") for r in rows):
        result["WARNING_dense_fallback"] = True
    return result
