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


def patch(logger_path: Path, out_path: Path, report_path: Path) -> dict:
    recovered = _load_recovered(report_path)
    xml = logger_path.read_text(encoding="utf-8")

    # Work on the raw text so we preserve the file byte-for-byte except the inserted lines.
    # For each ecuparam, if its name is recovered and it lacks our ECU, insert our <ecu> right
    # after the opening <ecuparam ...> tag.
    added, already, not_found = [], [], list(recovered.keys())
    # iterate ecuparam blocks
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
        if f'id="{TARGET}"' in block:
            already.append(name)
            return block
        r = recovered[name]
        open_tag_end = block.index(">") + 1
        indent = "\n                    "   # match the file's <ecu> indentation
        ins = (f'{indent}<ecu id="{TARGET}">'
               f'{indent}    <address length="{r["length"]}">{r["address"]}</address>'
               f'{indent}</ecu>')
        added.append(name)
        return block[:open_tag_end] + ins + block[open_tag_end:]

    patched = re.sub(r'<ecuparam\b.*?</ecuparam>', repl, xml, flags=re.DOTALL)
    out_path.write_text(patched, encoding="utf-8")
    return {"added": added, "already_present": already, "recovered_not_in_def": not_found,
            "out": str(out_path)}


def main() -> int:
    ap = argparse.ArgumentParser("patch_logger_def")
    ap.add_argument("--logger", required=True, help="your RomRaider logger def XML (input; untouched)")
    ap.add_argument("--out", required=True, help="patched copy to write")
    ap.add_argument("--report", default=str(HERE / "recovered-3B12504206.report.json"))
    args = ap.parse_args()
    res = patch(Path(args.logger), Path(args.out), Path(args.report))
    print(f"patched -> {res['out']}")
    print(f"  added {TARGET} to {len(res['added'])} ecuparams")
    if res["already_present"]:
        print(f"  already had {TARGET}: {len(res['already_present'])} (left as-is)")
    if res["recovered_not_in_def"]:
        print(f"  {len(res['recovered_not_in_def'])} recovered params NOT found in this def "
              f"(name mismatch / older def): {res['recovered_not_in_def'][:6]}"
              + (" ..." if len(res['recovered_not_in_def']) > 6 else ""))
    print("Next: back up your current logger def, point RomRaider at the --out file, restart, "
          "confirm the param count rose. Then VALIDATE each channel live before trusting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
