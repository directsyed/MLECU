"""Recover this ECU's extended-parameter RAM addresses by sibling reconciliation.

WHY. ECU `3B12504206` (A2WC411D, 05 FXT AT rev 42) is absent from the RomRaider logger def; that
one AT calibration revision was never contributed, so RomRaider offers it ZERO extended params
(Feedback Knock, Target Boost, IAM, CL/OL Fueling Target, injector PW/latency, Turbo Dynamics, …).
Extended params are RAM addresses that vary per calibration. `IDLE-LOG-PROFILE.md` refused to graft
sibling addresses ("'often' is not 'provably'"; "do not before the ROM read is solved"). BOTH
conditions are now lifted (2026-08-16): the ROM is read, and the `3B125` family demonstrably shares
one RAM layout, so we reconcile addresses across the family the same way `romread` reconciles table
addresses across sibling revision defs, then Syed validates each channel live before it is trusted.

METHOD. For every `<ecuparam>`, read the address each family member declares. Our ECU's address =
the address the family AGREES on. We report the agreement level and flag any divergence (the rev-40
member is a known outlier for some params). This never asserts an address the family does not
corroborate; a divergent/uncorroborated param is emitted as NEEDS-VALIDATION, not as a safe graft.

OUTPUT (read-only; writes only under this script's own dir):
  - a human report to stdout (per-param: proposed address, votes, confidence)
  - `recovered-3B12504206.logger-fragment.xml`: the `<ecu id="3B12504206">` lines to splice into
    each ecuparam of the RomRaider logger def (conversions are shared, so only the address is added)
  - `recovered-3B12504206.report.json`: machine-readable, for the live-validation step

Nothing here is trusted until Syed's validation log confirms each channel reads sane
(IAM ≈ 1.00 healthy, CL/OL flips OL→CL, logged injector PW ≈ standard P21, Feedback Knock ~0).
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

TARGET = "3B12504206"                       # our ECU (A2WC411D, 05 FXT AT rev 42), absent
# The 3B125 family: same platform/MCU, adjacent calibration revisions. Ordered by proximity to the
# target (its AT neighbours first, then the same-rev MT twin, then the rest). The rev-40 members
# (…04006 / …84006) are the known RAM outlier and get least weight.
FAMILY = ("3B12504106", "3B12504306",        # AT rev 41, 43, nearest (same transmission)
          "3B12584206",                       # MT twin, SAME rev 42, best for shared RAM
          "3B12584106", "3B12584306",         # MT rev 41, 43
          "3B12504006", "3B12584006")         # rev 40, outlier, lowest weight
_OUTLIERS = {"3B12504006", "3B12584006"}

REPO = Path(__file__).resolve().parents[3]
LOGGER_XML = (REPO / "ml" / "data-pipeline" / "data" / "raw" / "SubaruDefs"
              / "RomRaider" / "logger" / "standard" / "logger.xml")
OUT_DIR = Path(__file__).resolve().parent


def _ecu_ids(ecu: ET.Element) -> list[str]:
    """The ECU ids this <ecu> element covers.

    Two formats in the wild: the 2009 def gives one id per element; the v370 (2021) def GROUPS ids
    that share an address into a comma-separated list (`id="1358171FFF,3B12504106,3B12504306,..."`).
    Handling both is what lets the same reconciliation read either file.
    """
    return [s.strip() for s in (ecu.get("id") or "").split(",") if s.strip()]


def _addr_for(ecuparam: ET.Element, ecu_id: str) -> tuple[str, str] | None:
    """(address, length) this ecuparam declares for ecu_id, or None."""
    for ecu in ecuparam.findall("ecu"):
        if ecu_id in _ecu_ids(ecu):
            a = ecu.find("address")
            if a is not None and (a.text or "").strip():
                return a.text.strip(), (a.get("length") or "1")
    return None


def reconcile(logger_xml: Path = LOGGER_XML) -> list[dict]:
    root = ET.parse(logger_xml).getroot()
    # ecuparams live under <logger><protocols><protocol><ecuparams>; find them anywhere.
    params = root.iter("ecuparam")
    out: list[dict] = []
    for p in params:
        pid, name = p.get("id"), p.get("name", "")
        if _addr_for(p, TARGET) is not None:
            continue                                    # already present (shouldn't be)
        votes: dict[str, list[str]] = {}                # address -> [family members]
        length = None
        for sib in FAMILY:
            hit = _addr_for(p, sib)
            if hit:
                addr, length = hit
                votes.setdefault(addr, []).append(sib)
        if not votes:
            continue                                    # no family member has it either
        # non-outlier consensus decides; outliers only corroborate
        strong = {a: [m for m in ms if m not in _OUTLIERS] for a, ms in votes.items()}
        strong = {a: ms for a, ms in strong.items() if ms}
        pool = strong or votes
        best_addr = max(pool, key=lambda a: len(pool[a]))
        agree = len(pool[best_addr])
        divergent = len(strong) > 1 if strong else len(votes) > 1
        out.append({
            "id": pid, "name": name, "address": best_addr, "length": int(length),
            "votes": {a: ms for a, ms in votes.items()},
            "agree_nonoutlier": agree,
            "confidence": ("high" if agree >= 3 and not divergent else
                           "medium" if agree >= 2 and not divergent else "NEEDS-VALIDATION"),
            "divergent": divergent,
        })
    return out


# High-value channels for the VE/timing/knock build: surfaced first in the report.
_PRIORITY = ("Feedback Knock", "Fine Knock", "IAM", "Knock Sum", "CL/OL Fueling",
             "Closed Loop Fueling Target", "Target Boost", "Boost Error", "Engine Load",
             "Injector", "Turbo Dynamics", "Requested Torque")


def _is_priority(name: str) -> bool:
    return any(k.lower() in name.lower() for k in _PRIORITY)


def main() -> int:
    recs = reconcile()
    recs.sort(key=lambda r: (not _is_priority(r["name"]), r["id"]))
    hi = [r for r in recs if r["confidence"] == "high"]
    nv = [r for r in recs if r["confidence"] == "NEEDS-VALIDATION"]
    print(f"Extended-param recovery for {TARGET}, {len(recs)} params found across the family")
    print(f"  high-confidence (>=3 non-outlier siblings agree, no divergence): {len(hi)}")
    print(f"  needs careful live validation (divergent / thin): {len(nv)}\n")
    print(f"{'id':>5} {'conf':>16} {'addr':>10} {'len':>3}  votes  name")
    for r in recs:
        vs = " ".join(f"{a}×{len(ms)}" for a, ms in sorted(r["votes"].items(),
                                                           key=lambda kv: -len(kv[1])))
        star = "★" if _is_priority(r["name"]) else " "
        print(f"{r['id']:>5} {r['confidence']:>16} {r['address']:>10} {r['length']:>3}  {vs:22} {star}{r['name']}")

    frag = ['<!-- Recovered ecuparam addresses for %s (A2WC411D), splice each <ecu> line into the'
            % TARGET,
            '     matching <ecuparam> of the RomRaider logger def. Conversions are shared, so only',
            '     the address is added. VALIDATE LIVE before trusting (see extended_param_recovery.py). -->']
    for r in recs:
        frag.append(f'<!-- {r["id"]} {r["name"]} [{r["confidence"]}] -->')
        frag.append(f'<ecu id="{TARGET}"><address length="{r["length"]}">{r["address"]}</address></ecu>')
    (OUT_DIR / "recovered-3B12504206.logger-fragment.xml").write_text("\n".join(frag) + "\n")
    (OUT_DIR / "recovered-3B12504206.report.json").write_text(json.dumps(recs, indent=2))
    print(f"\nwrote {OUT_DIR/'recovered-3B12504206.logger-fragment.xml'}")
    print(f"wrote {OUT_DIR/'recovered-3B12504206.report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
