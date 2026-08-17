"""Splice the recovered extended params for 3B12504206 into a RomRaider logger def.

Version-robust: matches ecuparams by NAME (stable across def versions), not by internal id (E39
etc., which can shift). For each recovered param whose ecuparam exists in the target def and does
NOT already list our ECU, it inserts `<ecu id="3B12504206"><address .../></ecu>` (conversions are
shared at the ecuparam level, so only the address is added). Everything else is left byte-untouched.

Reads the recovered addresses from `recovered-3B12504206.report.json` (produced by
extended_param_recovery.py). Writes a patched copy; never overwrites the input.

USAGE
    python3 patch_logger_def.py --logger /path/to/your/logger_STD_EN_v370.xml \
                                --out    /path/to/logger_STD_EN_v370.3B12504206.xml

Then in RomRaider: back up your current logger def, point Settings->Definitions->Logger Definition
File at the --out file, restart. The startup log's parameter/model count should rise, and the
recovered params (Feedback Knock, Target Boost, CL/OL Fueling Target, IAM, ...) become selectable
for ECU 3B12504206. VALIDATE each live before trusting (EXTENDED-PARAMS-RECOVERY.md).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TARGET = "3B12504206"
HERE = Path(__file__).resolve().parent


def _load_recovered(report: Path) -> dict[str, dict]:
    """name -> {address, length, id, confidence} from the recovery report."""
    recs = json.loads(report.read_text())
    return {r["name"]: r for r in recs}


def patch(logger_path: Path, out_path: Path, report_path: Path,
          create_nodes: bool = False) -> dict:
    """Add TARGET to every ecuparam whose recovered address matches an existing <ecu> group.

    Two def formats are supported:
      * GROUPED (v370/2021): `<ecu id="A,B,C"><address>0xFF5C18</address></ecu>` — we APPEND our id
        to the group that already carries our recovered address. Minimal, surgical diff: no new XML
        nodes, and our ECU provably lands on the same address as the siblings in that group.
      * ONE-ID-PER-ELEMENT (0.3.5b/2009): no group matches, so we insert a new <ecu> element.
    """
    recovered = _load_recovered(report_path)
    xml = logger_path.read_text(encoding="utf-8")

    added_group, added_node, already, not_found = [], [], [], list(recovered.keys())
    skipped_no_group: list[str] = []

    def repl(m: re.Match) -> str:
        block = m.group(0)
        name_m = re.search(r'<ecuparam\b[^>]*\bname="([^"]*)"', block)
        if not name_m:
            return block
        name = name_m.group(1)
        if name not in recovered:
            return block
        if name in not_found:
            not_found.remove(name)
        if re.search(rf'\bid="[^"]*\b{TARGET}\b[^"]*"', block):
            already.append(name)
            return block
        r = recovered[name]
        addr = r["address"].lower()

        # 1) preferred: append our id to the <ecu> group that already declares this address
        def group_repl(em: re.Match) -> str:
            ids, body = em.group(1), em.group(2)
            am = re.search(r'<address\b[^>]*>([^<]+)</address>', body)
            if not am or am.group(1).strip().lower() != addr:
                return em.group(0)
            if TARGET in ids:
                return em.group(0)
            return em.group(0).replace(f'id="{ids}"', f'id="{ids},{TARGET}"', 1)

        patched_block, n = re.subn(r'<ecu id="([^"]*)">(.*?)</ecu>', group_repl, block,
                                   flags=re.DOTALL)
        if patched_block != block:
            added_group.append(name)
            return patched_block

        # 2) fallback: insert a standalone <ecu> element after the opening tag.
        # ONLY when this ecuparam has no group carrying our address at all. Guarded because
        # duplicate-NAME ecuparams exist across protocol sections (e.g. "CL/OL Fueling*" is both
        # E3 and E33): the sibling group in the OTHER block was already patched, and adding a
        # second, node-style entry here risks a conflicting definition. Emitting a node also has
        # to preserve v370's convention of omitting length for 1-byte params — writing
        # length="None" (an earlier bug, caught in validation) is malformed.
        if not create_nodes:
            skipped_no_group.append(name)
            return block
        length_attr = "" if str(r["length"]) in ("1", "None", "") else f' length="{r["length"]}"'
        open_tag_end = block.index(">") + 1
        indent = "\n                    "
        ins = (f'{indent}<ecu id="{TARGET}">'
               f'{indent}    <address{length_attr}>{r["address"]}</address>'
               f'{indent}</ecu>')
        added_node.append(name)
        return block[:open_tag_end] + ins + block[open_tag_end:]

    patched = re.sub(r'<ecuparam\b.*?</ecuparam>', repl, xml, flags=re.DOTALL)
    out_path.write_text(patched, encoding="utf-8")
    return {"added_to_group": added_group, "added_as_node": added_node,
            "added": added_group + added_node, "already_present": already,
            "recovered_not_in_def": not_found, "skipped_no_group": skipped_no_group,
            "out": str(out_path)}


def main() -> int:
    ap = argparse.ArgumentParser("patch_logger_def")
    ap.add_argument("--logger", required=True, help="your RomRaider logger def XML (input; untouched)")
    ap.add_argument("--out", required=True, help="patched copy to write")
    ap.add_argument("--report", default=str(HERE / "recovered-3B12504206.report.json"))
    ap.add_argument("--create-nodes", action="store_true",
                    help="also emit standalone <ecu> elements where no address group matches "
                         "(default OFF: group-append only — safest, no duplicate definitions)")
    args = ap.parse_args()
    res = patch(Path(args.logger), Path(args.out), Path(args.report), args.create_nodes)
    print(f"patched -> {res['out']}")
    print(f"  added {TARGET} to {len(res['added'])} ecuparams "
          f"({len(res['added_to_group'])} appended to an existing address group, "
          f"{len(res['added_as_node'])} as new elements)")
    if res["already_present"]:
        print(f"  already had {TARGET}: {len(res['already_present'])} (left as-is)")
    if res.get("skipped_no_group"):
        print(f"  skipped (no matching address group; duplicate-name block already patched "
              f"elsewhere): {len(res['skipped_no_group'])}")
    if res["recovered_not_in_def"]:
        print(f"  {len(res['recovered_not_in_def'])} recovered params NOT found in this def "
              f"(name mismatch / older def): {res['recovered_not_in_def'][:6]}"
              + (" ..." if len(res['recovered_not_in_def']) > 6 else ""))
    print("Next: back up your current logger def, point RomRaider at the --out file, restart, "
          "confirm the param count rose. Then VALIDATE each channel live before trusting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
