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
    "iat", "coolant", "tps", "battery_v", "fuel_system_status", "target_afr", "final_fueling_base", "af_learning_range",
    # --- added 2026-08-30 for the ignition-timing stage ---------------------------------
    # Both were logged by the car on 2026-08-30 and BOTH were being dropped or mis-assigned:
    #   "IAM (1-byte)** (multiplier)"      matched no rule at all -> silently absent
    #   "Ignition Base Timing* (degrees)"  matched r"\btiming\b" -> collided onto timing_total
    # The second is the dangerous one: it is the ignition map's OWN output, and it was landing
    # on the role that means FINAL commanded advance. It only lost to "Ignition Total Timing"
    # because that column happened to come first -- the exact accident that has now produced
    # five silent role collisions in this project.
    "iam", "timing_base",
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
    # MUST precede the bare knock rule only in spirit -- "IAM" contains no "knock" -- but it is
    # kept here because IAM *is* the knock subsystem's state: the multiplier the ECU applies to
    # its dynamic advance. It matched NO rule before 2026-08-30, so the channel that recorded
    # the car withdrawing all advance for 52 s was invisible to the layer.
    (re.compile(r"\biam\b", re.I), "iam"),
    (re.compile(r"knock", re.I), "knock_retard"),
    # MUST precede the wideband rule: "Closed Loop Fueling Target (2-byte)* (lambda)"
    # carries "lambda" in its units and was silently landing on wideband_afr, i.e. the
    # ECU's TARGET overwriting the MEASURED AFR. It only escaped notice because the AEM
    # happened to sit in an earlier column and first-column-wins saved us. Found 2026-08-27.
    # BOTH of these must precede the wideband rule, and for the same reason: they are ECU
    # COMMANDED values carrying "lambda" or "AFR" in their UNITS, and the wideband pattern
    # matches "lambda" anywhere. Left unhandled they land on wideband_afr -- the ECU's own
    # command silently replacing the MEASURED mixture. Both were found in real logs:
    #   Closed Loop Fueling Target (2-byte)* (lambda)   2026-08-27
    #   Final Fueling Base (4-byte)* (lambda)           2026-08-28
    # The second is why silent collisions are now DETECTED (see romraider_csv.LogTable.collisions)
    # rather than resolved by column order: the AEM sat in column 10 of the August 26 logs and
    # column 25 of the August 27 log, so first-column-wins quietly changed what wideband_afr
    # MEANT between two sessions of the same car.
    (re.compile(r"fuel\w*\s*target", re.I), "target_afr"),
    (re.compile(r"final\s*fuel\w*\s*base", re.I), "final_fueling_base"),
    (re.compile(r"wideband|uego|\baem\b|\bwb\b|lambda", re.I), "wideband_afr"),
    # MUST precede the a/f-learn rule. "A/F Learning Airflow Range (Current)*" is an INDEX
    # (1,2,3 = which airflow range is being learned), NOT a percentage — and it matched
    # `a/?f\s*learn`. It only ever lost to the real learning channel because it happened to sit
    # one column later; a reordered log would have put an integer index into af_learning and
    # silently corrupted every trim calculation downstream. Found 2026-08-28.
    (re.compile(r"learn\w*\s*airflow\s*range|airflow\s*range", re.I), "af_learning_range"),
    (re.compile(r"a/?f\s*learn", re.I), "af_learning"),
    (re.compile(r"a/?f\s*correction|a/?f\s*corr", re.I), "af_correction"),
    (re.compile(r"engine\s*load|calculated\s*load|g/rev|\bload\b", re.I), "load"),
    (re.compile(r"mass\s*air|\bmaf\b|airflow|g/s", re.I), "maf_gs"),
    # Bare "duty cycle" was removed: it caught the wastegate params. "Injector Duty Cycle" is
    # still matched by the injector-qualified alternative.
    (re.compile(r"injector\s*duty|inj\s*duty|\bipw\b|injector\s*pulse", re.I), "injector_duty"),
    # MUST precede the timing_total rule. "Ignition Base Timing*" is the BASE MAP's own output
    # -- the table this stage edits -- and r"\btiming\b" was sending it to timing_total, the
    # role that means FINAL commanded advance. Keeping them apart is what lets the timing stage
    # measure (base - total) directly instead of reconstructing it from the correction channels.
    (re.compile(r"base\s*timing", re.I), "timing_base"),
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


# When two headers legitimately describe the SAME quantity, which one wins must be a DECISION,
# not an accident of column order. RomRaider's column order is not stable between sessions: the
# AEM wideband sat in column 10 of the 2026-08-26 logs and column 25 of the 2026-08-27 log, which
# is how "Final Fueling Base (lambda)" quietly took over wideband_afr for one session.
# Most-preferred pattern first; anything unlisted falls back to first-column-wins.
_PREFER: dict[str, tuple[re.Pattern, ...]] = {
    # The ECU's own 4-byte internal load, not RomRaider's value derived from MAF and rpm.
    "load": (re.compile(r"4-?byte", re.I),),
    # Live knock feedback beats the IAM-scaled advance correction for "is it knocking NOW".
    # NOTE this one is load-bearing, not cosmetic: on the 2026-08-30 log THREE headers claim
    # knock_retard, and one of them is "Knock Sum* (count)" -- a cumulative COUNTER that was
    # non-zero on 6425 of 7402 samples. Without this preference a reordered export would put a
    # monotonically rising count into the role the timing evidence is computed from.
    "knock_retard": (re.compile(r"feedback\s*knock", re.I),),
    # The 4-byte extended parameter. idle-20260819 carries both the 1-byte and 4-byte IAM and
    # they agree exactly (max|diff| = 0.0), so this is a determinism choice, not a data choice.
    "iam": (re.compile(r"4-?byte", re.I),),
    # The DBW throttle PLATE angle, not the pedal-derived "Throttle Opening Angle". They track
    # each other (r = 0.9992) but differ by up to 12.6 points during transitions, and the plate
    # is what actually meters air -- it is also the channel the 86.03% open-loop trigger is
    # defined against. Only the 2026-08-30 log carries both, so no earlier result moves.
    "tps": (re.compile(r"plate", re.I),),
}


def prefer(role: str, headers: list[str]) -> str:
    """Pick the winning header for a role deterministically. Returns headers[0] if unlisted."""
    for pat in _PREFER.get(role, ()):
        for h in headers:
            if pat.search(h):
                return h
    return headers[0]
