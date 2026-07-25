"""Citation guard unit tests — the clamp must be boringly correct (2026-07-25)."""
import pytest

from harness import citation_guard as cg

EVIDENCE = ["Injector dead time at 14.0V is typically 1.0 ms; at 12.0V expect 1.24 ms.",
            "Target idle AFR 14.7:1, warm idle 750 rpm. Fuel pressure 43.5 psi (3 bar)."]


def test_cited_value_passes():
    ans, rec = cg.apply({"value": "1.24 ms", "must_retrieve": False}, EVIDENCE)
    assert rec["verdict"] == "cited" and ans["value"] == "1.24 ms"


def test_tolerance_match_counts_as_cited():
    assert cg.verify("1.245 ms", EVIDENCE)["verdict"] == "cited"       # within 1% of 1.24


def test_fabricated_value_blocked_and_converted_to_decline():
    ans, rec = cg.apply({"value": "2.6 ms", "must_retrieve": False}, EVIDENCE)
    assert rec["verdict"] == "blocked" and rec["unverified"] == [2.6]
    assert ans == {"value": None, "must_retrieve": True}


def test_every_stated_number_must_be_grounded():
    assert cg.verify("750 rpm at 43.5 psi", EVIDENCE)["verdict"] == "cited"
    assert cg.verify("750 rpm at 99 psi", EVIDENCE)["verdict"] == "blocked"


def test_decline_and_qualitative_pass_untouched():
    assert cg.verify(None, EVIDENCE)["verdict"] == "declined"
    assert cg.verify("", EVIDENCE)["verdict"] == "declined"
    assert cg.verify("richer than stock", EVIDENCE)["verdict"] == "no_numbers"


def test_comma_and_ratio_forms():
    ev = ["Rev limit 6,700 rpm. Compression ratio 8.4:1 on the EJ255."]
    assert cg.verify("6700", ev)["verdict"] == "cited"
    assert cg.verify("8.4:1", ev)["verdict"] == "cited"                # 8.4 and 1 both present


def test_pdf_mangled_digits_healed():
    ev = ["boost target 18­.5 psi table row 2 5​00 rpm"]     # soft hyphen / zero-width
    assert cg.verify("2500 rpm", ev)["verdict"] == "cited"


def test_no_evidence_blocks_any_number():
    ans, rec = cg.apply({"value": "14.7", "must_retrieve": False}, [])
    assert rec["verdict"] == "blocked" and ans["must_retrieve"] is True


def test_leading_dot_number_parses_and_cites():
    # scorer-v1.1 sibling fix: '.84' is 0.84, not 84 (retro-test catch, probe e2-466-0)
    ev = ["stoich lambda display resolution .84 under boost"]
    assert cg.numbers_in(".84") == [0.84]
    assert cg.verify("0.84", ev)["verdict"] == "cited"


def test_ref_citation_ids_are_not_values():
    # retro-test false-block: model embedded '[REF 644]' in its value string
    ev = ["timing advance 20 degrees at light load"]
    v = cg.verify('{"value": 20, "citation": "[REF 644]"}', ev)
    assert v["verdict"] == "cited"
