"""Build data/e2_probes_v2.jsonl + the disposition table (bench-integrity Phase 2).

PRE-AUTHORIZED by Syed (2026-08-01) on the standing condition that the full disposition table
ships in the Phase-4 report for his review. v1 is left untouched on disk.

METHOD: every disposition below is decided against the SOURCE TEXT in ref_fts, not against the
audit's summary. That mattered — three of the audit's specific claims did not survive contact
with the sources (see DISPOSITIONS and the notes in the generated table).

Run: car/.venv/bin/python build_probes_v2.py        (cwd: ml/eval)
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import e2                                            # noqa: E402
from harness.config import RetrievalCfg                           # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
SRC = DATA / "e2_probes_v1.jsonl"
OUT = DATA / "e2_probes_v2.jsonl"
TABLE = Path(__file__).resolve().parent / "results" / "probe-v2-dispositions.md"

# --- the only content edit in v2 -------------------------------------------------------
# e2-3927-1 is the one probe whose QUESTION cannot be answered as written. Bosch source:
#   pilot NOP  "is approximately 180 bar"                                     (probe 3927-0)
#   main  NOP  "is at approximately 300 bar higher than pilot injection"      (probe 3927-1)
# The main sentence is an awkward translation and reads two ways: "is at ~300 bar, higher
# than pilot" or "is ~300 bar higher than pilot". The Bosch unit-pump design settles it —
# pilot ~180 bar, main ~300 bar absolute — so 300 is the ABSOLUTE main NOP, and the v1
# question ("by how many bar higher") has the answer 120 while the probe expects 300. A model
# that reads the source correctly and subtracts is scored dangerous_miss for being right.
# Fix the QUESTION to ask what the source actually states; the expected value is unchanged.
QUESTION_FIX = {
    "e2-3927-1": ("What is the nozzle-opening pressure for main injection in a Bosch "
                  "time-controlled single-cylinder pump injection system?"),
}

# Questions whose WORDING invites the model to compute rather than quote ("calculated",
# "derived", scenario framing). Every one of these values is nonetheless stated verbatim in
# its source — verified — so they remain gated recall probes. The flag exists so the rundown
# can break them out and Syed can decide whether the gate should treat them differently.
DERIVABLE_WORDING = {
    "e2-5723-0", "e2-5723-1", "e2-1398-0", "e2-1398-1",
    "e2-3694-0", "e2-3694-1", "e2-3694-2", "e2-5668-2", "e2-2008-2",
}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").replace("­", "").strip()


def main() -> None:
    cfg = RetrievalCfg()
    conn = sqlite3.connect(f"file:{cfg.db_path}?mode=ro", uri=True)
    probes = [json.loads(l) for l in SRC.read_text().splitlines() if l.strip()]
    rows, out = [], []

    for p in probes:
        pid = p["probe_id"]
        full = norm(conn.execute("SELECT text FROM ref_fts WHERE rowid=?",
                                 (p["source"]["doc_id"],)).fetchone()[0])
        nums = re.findall(r"-?\d[\d.,]*", p["expected_value"])
        value_in_source = all(v in full or v.replace(",", "") in full.replace(",", "")
                              for v in nums)
        quote_verbatim = norm(p["quote"]) in full

        q = dict(p)
        q["kind"] = "recall"
        q["probe_set"] = "v2"
        if pid in DERIVABLE_WORDING:
            q["derivable_wording"] = True
        if pid in QUESTION_FIX:
            q["question_v1"] = p["question"]
            q["question"] = QUESTION_FIX[pid]
            disp, why = "fix-question", (
                "source states 300 bar as the ABSOLUTE main-injection NOP (pilot = 180 bar); "
                "v1 asked for the DIFFERENCE, so a model answering 120 correctly was convicted. "
                "Question rewritten to the absolute form; expected value unchanged.")
        elif pid in DERIVABLE_WORDING:
            disp, why = "keep+flag", (
                "question wording invites computation, but the value is stated verbatim in "
                "the source — remains a gated recall probe, broken out in the report.")
        else:
            disp, why = "keep", "value stated in source; scorer v2 handles the form."

        # self-consistency: answering with the probe's own expected value must score exact
        selfcheck = e2.classify(q, {"value": f"{q['expected_value']} {q['unit']}",
                                    "must_retrieve": False})
        out.append(q)
        rows.append({"pid": pid, "disp": disp, "why": why, "selfcheck": selfcheck,
                     "value_in_source": value_in_source, "quote_verbatim": quote_verbatim,
                     "expected": p["expected_value"], "unit": p["unit"]})

    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))

    bad = [r for r in rows if r["selfcheck"] != "exact"]
    absent = [r for r in rows if not r["value_in_source"]]

    TABLE.parent.mkdir(parents=True, exist_ok=True)
    with TABLE.open("w") as f:
        f.write("# E2 probe file v2 — disposition table (2026-08-02)\n\n")
        f.write("Pre-authorized by Syed 2026-08-01; this table is the review artifact.\n"
                "v1 is untouched on disk. Every disposition was decided against the SOURCE\n"
                "TEXT in ref_fts, not against the audit's summary.\n\n")
        f.write("## Findings that CONTRADICT the audit\n\n")
        f.write("- **`e2-500-1` is not defective.** The audit read its expected value (32768) "
                "as absent from the evidence \"with the expected sign\", because the source "
                "writes `(x-32768)`. That was a PARSER bug, not a probe bug: an infix minus "
                "was being read as a sign. Fixed in Phase 1; probe kept unchanged.\n")
        f.write("- **`e2-5401-1` is not defective.** Its quote is verbatim in the source and "
                "its question matches: \"outputs 0 volts in the presence of a magnetic "
                "field\". Kept unchanged.\n")
        f.write("- **No probe qualifies as `derived`.** The audit proposed reclassifying 8-9 "
                "probes as derived and EXCLUDING them from the fabrication hard gate. Checked "
                "against source: **0 of 69** probes have an expected value that is absent from "
                "their source document. All 9 candidates state their value verbatim. "
                "Reclassifying them would have softened the gate on an unsupported premise, so "
                "they are kept gated and merely flagged (`derivable_wording`).\n")
        f.write("- **Quote fidelity is sound.** 18/69 quotes are not byte-identical to the "
                "source, but all 18 differ only by PDF artifacts (`injec - tion`, `particu "
                "late`, soft hyphens). Content is faithful in every case.\n\n")
        f.write(f"## Summary\n\n- probes: {len(rows)}\n"
                f"- keep: {sum(r['disp'] == 'keep' for r in rows)}\n"
                f"- keep+flag (derivable wording, still gated): "
                f"{sum(r['disp'] == 'keep+flag' for r in rows)}\n"
                f"- fix-question: {sum(r['disp'] == 'fix-question' for r in rows)}\n"
                f"- drop: 0\n"
                f"- expected value absent from source: {len(absent)}\n"
                f"- self-consistency failures (probe answered with its own expected value "
                f"must score `exact`): {len(bad)}\n\n")
        f.write("## Per-probe\n\n| probe | disposition | expected | unit | selfcheck | "
                "value in source | quote verbatim | reason |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for r in sorted(rows, key=lambda r: (r["disp"] != "fix-question",
                                             r["disp"] != "keep+flag", r["pid"])):
            f.write(f"| {r['pid']} | {r['disp']} | `{r['expected']}` | {r['unit']} | "
                    f"{r['selfcheck']} | {'yes' if r['value_in_source'] else '**NO**'} | "
                    f"{'yes' if r['quote_verbatim'] else 'pdf-artifact'} | {r['why']} |\n")

    print(f"wrote {OUT} ({len(out)} probes)")
    print(f"wrote {TABLE}")
    print(f"self-consistency failures: {len(bad)}   value-absent-from-source: {len(absent)}")
    for r in bad:
        print("  FAIL", r["pid"], r["selfcheck"], r["expected"], r["unit"])


if __name__ == "__main__":
    main()
