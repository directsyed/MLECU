"""Retro-test for the citation guard's context check — the 2026-07-25 protocol, reapplied.

The original guard was validated by exactly this shape: replay it over known fabrications
(how many does it block?) AND over known-correct cited answers (how many does it break?), and
publish both numbers. A blocker with no false-block measurement is not a validated blocker.

What is being tested now (2026-08-05): every fabrication that survived the guard in the E2 rerun
carried verdict `cited` — the number IS in the retrieved evidence but answers a DIFFERENT
question. The context check adds unit agreement + question anchoring. This measures whether it
closes that hole without breaking answers that were legitimately grounded.

Run: car/.venv/bin/python guard_retrotest.py     (cwd: ml/eval)
"""
from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import citation_guard as cg, e2, retrieval          # noqa: E402
from harness.config import Config                                # noqa: E402

PROBES = {json.loads(l)["probe_id"]: json.loads(l)
          for l in (Path("data/e2_probes_v2.jsonl")).read_text().splitlines() if l.strip()}


def corpus() -> tuple[list, list]:
    """(leaks, corrects) — rows the guard passed as `cited`, split by whether they were right."""
    conn = sqlite3.connect("file:bench/bench.sqlite?mode=ro", uri=True)
    leaks, corrects = [], []
    q = ("SELECT model_tag, out_path FROM unit WHERE phase='e2v2' AND state='done' "
         "AND suite='e2' AND model_tag LIKE '%guard%'")
    for tag, out in conn.execute(q):
        k = 6 if "k6" in tag else 3
        for r in [json.loads(l) for l in Path(out).read_text().splitlines() if l.strip()]:
            g = r.get("guard") or {}
            if g.get("verdict") != "cited":
                continue
            p = PROBES.get(r["probe_id"])
            if p is None:
                continue
            cls = e2.classify(p, r.get("answer") or {}, 1.0, r.get("finish_reason"))
            rec = (tag, r["probe_id"], (r.get("answer") or {}).get("value"), p["question"], k)
            if cls == "dangerous_miss":
                leaks.append(rec)
            elif cls == "exact":
                corrects.append(rec)
    conn.close()
    return leaks, corrects


def verdicts(rows, use_question: bool):
    out = []
    for tag, pid, val, question, k in rows:
        cfg = replace(Config().retrieval, top_k=k)
        snips = retrieval.retrieve(cfg, question)
        v = cg.verify(val, [s.snippet for s in snips],
                      question=question if use_question else None)
        out.append((pid, val, v["verdict"]))
    return out


def main() -> None:
    leaks, corrects = corpus()
    print(f"cited-and-WRONG   (leaks the guard must start catching): {len(leaks)}")
    print(f"cited-and-CORRECT (must NOT become false blocks)       : {len(corrects)}")
    print()

    for label, rows in (("LEAKS", leaks), ("CORRECT", corrects)):
        before = verdicts(rows, use_question=False)
        after = verdicts(rows, use_question=True)
        changed = sum(1 for b, a in zip(before, after) if b[2] != a[2])
        print(f"=== {label} ===")
        for (pid, val, vb), (_, _, va) in zip(before, after):
            mark = "  <-- CHANGED" if vb != va else ""
            print(f"  {pid:<13} {vb:<22} -> {va:<22} {str(val)[:44]!r}{mark}")
        print(f"  {changed}/{len(rows)} changed verdict")
        print()

    after_leaks = verdicts(leaks, use_question=True)
    after_ok = verdicts(corrects, use_question=True)
    caught = sum(1 for _, _, v in after_leaks if v != "cited")
    false_blocks = sum(1 for _, _, v in after_ok if v != "cited")
    print("RETRO-TEST RESULT")
    print(f"  fabrications caught : {caught}/{len(leaks)}")
    print(f"  false blocks        : {false_blocks}/{len(corrects)}")
    print()
    print("Both numbers are published together, per the anti-benchmark-maxxing contract: a")
    print("blocker measured only on what it blocks is not a validated blocker.")


if __name__ == "__main__":
    main()
