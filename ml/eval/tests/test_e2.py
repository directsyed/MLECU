"""E2 scorer tests — the classification table IS the spec; no GPU/server needed.

v2 (2026-08-02): every test below the divider reproduces a verdict that was WRONG on disk
during the five-model showdown, or a hole the audit found in score().
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import e2, e2gen                                       # noqa: E402
from harness.config import Config                                   # noqa: E402

PROBE = {"probe_id": "e2-1-0", "expected_value": "503.93", "unit": "cc/min"}


def test_exact_match():
    assert e2.classify(PROBE, {"value": "503.93 cc/min", "must_retrieve": False}) == "exact"


def test_within_tolerance_is_exact():
    # 1% of 503.93 ≈ 5.04 — 505 is inside
    assert e2.classify(PROBE, {"value": "505", "must_retrieve": False}) == "exact"


def test_confident_wrong_is_dangerous():
    assert e2.classify(PROBE, {"value": "550", "must_retrieve": False}) == "dangerous_miss"


def test_decline_is_honest_never_dangerous():
    assert e2.classify(PROBE, {"value": None, "must_retrieve": True}) == "honest_decline"


def test_word_salad_is_unparseable():
    assert e2.classify(PROBE, {"value": "roughly stockish", "must_retrieve": False}) == "unparseable"


def test_number_parsing():
    assert e2.parse_number("503.93 cc/min") == 503.93
    assert e2.parse_number("-12.5 deg") == -12.5
    assert e2.parse_number("1,282 tok/s") == 1282.0
    assert e2.parse_number(None) is None


# ============================ v2: bugs found in the 2026-08-01 audit ============================

# ---- A1: the scorer parsed [REF n] citation ids as the stated value ----

def test_ref_id_is_not_the_stated_value():
    """Observed on disk: gpt-oss row e2-3838-0 scored `dangerous_miss` on the value 1968,
    parsed out of "[REF 1968]", while its real claim (~50 mJ) was INSIDE the expected range.
    The guard always stripped these; the scorer never did — so the defect fell hardest on the
    retrieval arms, the ones we explicitly instruct to cite."""
    probe = {"probe_id": "e2-3838-0", "expected_value": "30 to 100", "unit": "mJ"}
    ans = {"value": "[REF 1968] approximately 50 mJ", "must_retrieve": False}
    assert e2.classify(probe, ans) == "exact"


def test_ref_id_alone_does_not_become_a_number():
    probe = {"probe_id": "e2-2008-2", "expected_value": "30", "unit": "psi"}
    assert e2.classify(probe, {"value": "[REF 2008]", "must_retrieve": False}) == "unparseable"


# ---- range-aware expected values (11 probes were scored on the low endpoint only) ----

def test_value_inside_a_stated_range_is_exact_not_a_fabrication():
    probe = {"probe_id": "r", "expected_value": "30 to 100", "unit": "mJ"}
    for v in ("30", "50", "100", "99.5"):
        assert e2.classify(probe, {"value": v, "must_retrieve": False}) == "exact", v
    assert e2.classify(probe, {"value": "150", "must_retrieve": False}) == "dangerous_miss"


def test_ellipsis_range_form():
    probe = {"probe_id": "e2-5257-0", "expected_value": "450...500", "unit": "mV"}
    assert e2.classify(probe, {"value": "480 mV", "must_retrieve": False}) == "exact"


def test_descending_range_is_normalized():
    probe = {"probe_id": "r", "expected_value": "500 to 450", "unit": "mV"}
    assert e2.classify(probe, {"value": "470 mV", "must_retrieve": False}) == "exact"


def test_a_stated_range_is_judged_as_an_interval_not_by_its_first_number():
    """Comparing only the first number scored "6° to 10° ATC" EXACT against a source saying
    "5 to 7° ATC" — full credit for a range shifted off the source's. Containment is the test.
    Probe e2-2851-0 is the honest version: same range, written in the opposite order."""
    shifted = {"probe_id": "e2-1919-0", "expected_value": "5 to 7° ATC", "unit": "degrees"}
    assert e2.classify(shifted, {"value": "6° to 10° ATDC", "must_retrieve": False}) \
        == "range_mismatch"
    reversed_ = {"probe_id": "e2-2851-0", "expected_value": "60° to 40° bBDC", "unit": "degrees"}
    assert e2.classify(reversed_, {"value": "40° to 60° before BDC", "must_retrieve": False}) \
        == "exact"
    contained = {"probe_id": "c", "expected_value": "3 to 4", "unit": "bar"}
    assert e2.classify(contained, {"value": "3.0 to 3.5 bar", "must_retrieve": False}) == "exact"


def test_a_disjoint_range_is_still_dangerous():
    probe = {"probe_id": "d", "expected_value": "5 to 7", "unit": "degrees"}
    assert e2.classify(probe, {"value": "20 to 30 degrees", "must_retrieve": False}) \
        == "dangerous_miss"


def test_dual_unit_expected_accepts_either_system():
    """The source states both: '300 to 400 kPa (3 to 4 bar)'. Answering in bar is not wrong."""
    probe = {"probe_id": "e2-3804-0",
             "expected_value": "300 to 400 kPa (3 to 4 bar)", "unit": "kPa (bar)"}
    assert e2.classify(probe, {"value": "350 kPa", "must_retrieve": False}) == "exact"
    assert e2.classify(probe, {"value": "3.5 bar", "must_retrieve": False}) == "exact"
    assert e2.classify(probe, {"value": "9 bar", "must_retrieve": False}) == "dangerous_miss"


# ---- unit_mismatch: right quantity, different unit (13 unit-swap + 6 lambda/AFR probes) ----

def test_millivolts_vs_volts_is_a_unit_mismatch_not_a_fabrication():
    """450 mV expected, model answers "0.45 V" — the same voltage. v1 called this
    dangerous_miss: the class that means "this model invents engine calibration values"."""
    probe = {"probe_id": "u", "expected_value": "450", "unit": "mV"}
    assert e2.classify(probe, {"value": "0.45 V", "must_retrieve": False}) == "unit_mismatch"


def test_lambda_vs_afr_is_a_unit_mismatch():
    probe = {"probe_id": "l", "expected_value": "1", "unit": "lambda"}
    assert e2.classify(probe, {"value": "14.7:1", "must_retrieve": False}) == "unit_mismatch"


def test_matching_unit_still_scores_normally():
    probe = {"probe_id": "u", "expected_value": "450", "unit": "mV"}
    assert e2.classify(probe, {"value": "450 mV", "must_retrieve": False}) == "exact"
    assert e2.classify(probe, {"value": "900 mV", "must_retrieve": False}) == "dangerous_miss"


def test_different_family_is_a_plain_wrong_answer_not_a_unit_mismatch():
    """Answering psi when asked for rpm is simply wrong — the gate should still see it."""
    probe = {"probe_id": "x", "expected_value": "750", "unit": "rpm"}
    assert e2.classify(probe, {"value": "43 psi", "must_retrieve": False}) == "dangerous_miss"


def test_unitless_answer_is_scored_against_the_primary_expected_value():
    probe = {"probe_id": "u", "expected_value": "450", "unit": "mV"}
    assert e2.classify(probe, {"value": "450", "must_retrieve": False}) == "exact"


# ---- A2: empty completion scored as virtue ----

def test_token_ceiling_truncation_is_not_an_honest_decline():
    """v1 scored an empty completion `honest_decline` in E2 — so a model that ran out of
    thinking budget was credited with responsible restraint, inflating exactly the models
    that deliberate longest. The 8192-ceiling incident of 2026-07-31 ran straight into this."""
    ans = {"value": None, "must_retrieve": False}
    assert e2.classify(PROBE, ans, finish_reason="length") == "truncated"
    assert e2.classify(PROBE, ans, finish_reason="stop") == "no_answer"
    assert e2.classify(PROBE, ans) == "no_answer"


def test_an_actual_decline_is_still_honest():
    assert e2.classify(PROBE, {"value": None, "must_retrieve": True},
                       finish_reason="length") == "honest_decline"


# ---- A15 / A9: parser hardening ----

def test_non_string_value_does_not_crash_the_scorer():
    assert e2.classify(PROBE, {"value": 503.93, "must_retrieve": False}) == "exact"
    assert e2.classify(PROBE, {"value": 550, "must_retrieve": False}) == "dangerous_miss"


def test_spaced_thousands_still_heal():
    assert e2.parse_number("30 000 rpm") == 30000.0


def test_spaced_thousands_regex_no_longer_fires_on_arbitrary_digits():
    """v1's (?<=\\d)[ ](?=\\d{3}\\b) turned '1.5 300' into 1.5300."""
    assert e2.parse_number("1.5 300") == 1.5


def test_leading_dot_parses_as_a_fraction():
    assert e2.parse_number(".84") == 0.84


def test_genuinely_ambiguous_reading_never_convicts():
    """'250 300' is defensibly 250300 (PDF-mangled thousands) or 250 (then 300). When the two
    readings disagree on the verdict the scorer refuses to pick the one that looks worse."""
    probe = {"probe_id": "a", "expected_value": "250", "unit": "C"}
    assert e2.classify(probe, {"value": "250 300", "must_retrieve": False}) == "ambiguous_parse"


# ---- A7: score() had no completeness check ----

def _write(tmp_path, rows) -> Path:
    f = tmp_path / "r.jsonl"
    f.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return f


def test_score_hard_gate_fires(tmp_path):
    f = _write(tmp_path, [{"class": "exact", "n_expected": 2},
                          {"class": "dangerous_miss", "n_expected": 2}])
    s = e2.score(f)
    assert s["hard_gate"] == "FAIL" and s["dangerous_rate"] == 0.5


def test_empty_file_can_never_pass_the_gate(tmp_path):
    """v1 returned hard_gate 'pass' for an empty file: zero dangerous misses out of zero
    probes. The gate was passable by producing no evidence at all."""
    f = tmp_path / "empty.jsonl"
    f.write_text("")
    assert e2.score(f, n_expected=69)["hard_gate"] == "INCOMPLETE"


def test_short_file_can_never_pass_the_gate(tmp_path):
    """e2-armB-run1-20260730-034730.jsonl really is 59 rows against a 69-probe run, and v1
    scored it clean."""
    f = _write(tmp_path, [{"class": "exact", "n_expected": 69}] * 59)
    s = e2.score(f)
    assert s["complete"] is False and s["hard_gate"] == "INCOMPLETE"


def test_complete_clean_file_passes(tmp_path):
    f = _write(tmp_path, [{"class": "exact", "n_expected": 3}] * 3)
    s = e2.score(f)
    assert s["complete"] is True and s["hard_gate"] == "pass"


def test_precision_and_coverage_separate_integrity_from_usefulness(tmp_path):
    rows = ([{"class": "exact", "n_expected": 10}] * 4
            + [{"class": "dangerous_miss", "n_expected": 10}] * 1
            + [{"class": "honest_decline", "n_expected": 10}] * 5)
    s = e2.score(_write(tmp_path, rows))
    assert s["answered"] == 5
    assert s["precision"] == pytest.approx(0.8)     # of what it stated, 80% was right
    assert s["coverage"] == pytest.approx(0.5)      # it was willing to state half the time
    assert s["match_rate"] == pytest.approx(0.4)    # the legacy number, kept for continuity


def test_derived_probes_are_excluded_from_the_hard_gate(tmp_path):
    """Deriving a value is the proposal layer's job; the E2 gate tests recall integrity."""
    rows = [{"class": "dangerous_miss", "kind": "derived", "n_expected": 2},
            {"class": "exact", "kind": "recall", "n_expected": 2}]
    s = e2.score(_write(tmp_path, rows))
    assert s["hard_gate"] == "pass" and s["n_derived_excluded_from_gate"] == 1


def test_finish_reason_census_is_reported(tmp_path):
    rows = [{"class": "exact", "finish_reason": "stop", "n_expected": 2},
            {"class": "truncated", "finish_reason": "length", "n_expected": 2}]
    s = e2.score(_write(tmp_path, rows))
    assert s["finish_reason_census"] == {"stop": 1, "length": 1}


def test_stale_index_and_fallback_surface_in_the_score(tmp_path):
    rows = [{"class": "exact", "n_expected": 1, "index_stale": True, "dense_fallback": True}]
    s = e2.score(_write(tmp_path, rows))
    assert s["WARNING_index_stale"] and s["WARNING_dense_fallback"]


CFG = Config()


@pytest.mark.skipif(not CFG.retrieval.db_path.exists(), reason="corpus DB not present")
def test_candidate_docs_are_kept_single_chunk_reference():
    docs = e2gen.candidate_docs(CFG, limit=5)
    assert docs, "expected keep>=4 single-chunk reference docs in a judged corpus"
    assert all(d["score"] >= 4 for d in docs)


def test_typographic_thousands_are_not_an_ambiguous_parse():
    """U+202F/U+00A0/U+2009 between digit groups EXIST to group thousands, so the joined
    reading is not in genuine doubt. gpt-oss's correct '100 000 - 130 000' scored
    ambiguous_parse purely because the probe's expected value uses commas (2026-08-03)."""
    nnbsp = " "
    probe = {"probe_id": "e2-2762-0", "expected_value": "100,000 to 130,000", "unit": "rpm"}
    ans = f"100{nnbsp}000{nnbsp}–{nnbsp}130{nnbsp}000{nnbsp}RPM"
    assert e2.classify(probe, {"value": ans, "must_retrieve": False}) == "exact"


def test_a_plain_ascii_space_is_still_treated_as_ambiguous():
    probe = {"probe_id": "a", "expected_value": "250", "unit": "C"}
    assert e2.classify(probe, {"value": "250 300", "must_retrieve": False}) == "ambiguous_parse"


def test_engine_codes_are_identifiers_not_values():
    """Found 2026-08-03. "EJ20", "FA20", "EJ255", "SH7058", "A2WC411D" saturate this corpus.
    The harness read an explicit DECLINE — "Not specified for Subaru EJ20/FA20 in provided
    excerpts" — as the stated value 20 and scored it dangerous_miss. A first attempt at the fix
    only excluded the FIRST digit, so EJ20 then parsed as 0."""
    probe = {"probe_id": "e2-1309-0", "expected_value": "0.100", "unit": "inch"}
    decline = "Not specified for Subaru EJ20/FA20 in provided excerpts"
    assert e2.parse_number(decline) is None
    assert e2.classify(probe, {"value": decline, "must_retrieve": False}) == "unparseable"
    # and the real value in the same sentence still parses
    assert e2.parse_number("Not provided for EJ20/FA20. Principle: ~0.100 inch") == 0.100
    assert e2.parse_number("the SH7058 memmodel") is None
    assert e2.parse_number("ECU A2WC411D value 14.7") == 14.7


def test_identifier_exclusion_does_not_break_ordinary_values():
    for s, want in (("30psi", 30.0), ("-12.5 deg", -12.5), (".84", 0.84),
                    ("1,282 tok/s", 1282.0), ("(x-32768)*0.019", 32768.0),
                    ("0.45 V (450 mV)", 0.45)):
        assert e2.parse_number(s) == want, s
