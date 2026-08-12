#!/usr/bin/env python3
"""Look up a Subaru SSM2 ECU ID in the RomRaider ROM definition file.

Answers the question "is this ECU the right part for this car?" by reporting the
exact match (if any), the whole ECU-ID family sharing its prefix, and every entry
for the same model across years -- so a MISSING id can be judged against the
structure around it rather than treated as an anomaly on its own.

Standard library only; no venv required.

    python3 car/ecu/defs/ecuid_lookup.py [ECU_ID]

Defaults to the test vehicle's id, 3B12504206 (2005 USDM Forester XT, 4EAT).
"""
import os
import sys
import xml.etree.ElementTree as ET

DEFS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ecu_defs.xml")
DEFAULT_ID = "3B12504206"

FIELDS = ("xmlid", "ecuid", "year", "market", "make", "model", "submodel",
          "transmission", "memmodel", "flashmethod", "filesize", "internalidstring")

COLS = (("ecuid", 12), ("year", 6), ("market", 7), ("model", 12),
        ("submodel", 10), ("transmission", 6), ("memmodel", 9),
        ("flashmethod", 12), ("xmlid", 10))


def load(path):
    """Stream the 7.8 MB defs file, keeping only romid metadata."""
    roms = []
    for _, el in ET.iterparse(path, events=("end",)):
        if el.tag == "romid":
            entry = {f: (el.findtext(f) or "").strip() for f in FIELDS}
            if entry["ecuid"]:
                roms.append(entry)
        elif el.tag == "rom":
            el.clear()
    return roms


def table(rows):
    header = " ".join(name.ljust(w) for name, w in COLS)
    out = [header, "-" * len(header)]
    for r in rows:
        out.append(" ".join(r.get(name, "").ljust(w) for name, w in COLS))
    return "\n".join(out)


def main():
    target = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ID).upper()

    if not os.path.exists(DEFS):
        sys.exit("ecu_defs.xml not found next to this script: %s" % DEFS)

    roms = load(DEFS)
    print("%d rom entries carrying an ecuid\n" % len(roms))

    exact = [r for r in roms if r["ecuid"].upper() == target]
    print("=== EXACT MATCH for %s: %d ===" % (target, len(exact)))
    print(table(exact) if exact else
          "  (absent -- judge this against the family below, not on its own)")
    print()

    # Family = ids sharing the leading 5 chars. For 3B125* that is the 2005
    # USDM Forester XT block; digit 6 encodes transmission (0=AT, 8=MT) and
    # digits 7-8 the calibration revision.
    prefix = target[:5]
    family = sorted((r for r in roms if r["ecuid"].upper().startswith(prefix)),
                    key=lambda r: r["ecuid"])
    print("=== FAMILY %s* : %d entries ===" % (prefix, len(family)))
    print(table(family))
    print()

    models = {r["model"] for r in family if r["model"]}
    for model in sorted(models):
        same = sorted((r for r in roms if r["model"] == model),
                      key=lambda r: (r["year"], r["ecuid"]))
        print("=== ALL %s entries : %d ===" % (model, len(same)))
        print(table(same))
        print()


if __name__ == "__main__":
    main()
