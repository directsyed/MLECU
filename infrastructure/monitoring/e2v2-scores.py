"""One line per completed e2v2 cell, for the cockpit's status pane.

Reads the ledger for done cells and scores each result file with the CURRENT scorer, so the
pane shows the live corrected matrix as it fills in rather than a progress bar. Cheap enough
to run on the pane's refresh (69 rows per file, no model, no GPU).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

MLECU = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(MLECU / "ml/eval"))
from harness import e2                                          # noqa: E402

DB = MLECU / "ml/eval/bench/bench.sqlite"

_ABBR = {"qwen27b-dense": "27B", "gpt-oss-120b": "oss120", "qwen35-moe": "35B",
         "qwen-next-80b-think": "80Bth", "mistral-small-4": "mistral"}


def short(tag: str) -> str:
    """Fit the cockpit's 68-column pane: `qwen27b-dense|e2v2-armB-k3-guard` -> `27B B-k3+g`."""
    model, _, cell = tag.partition("|")
    cell = (cell.replace("e2v2-", "").replace("e1v2-", "E1 ").replace("arm", "")
                .replace("-guard", "+g").replace("-reverify", "rv"))
    return f"{_ABBR.get(model, model[:7])} {cell}"[:28]


def main() -> None:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT model_tag, out_path, arm, suite FROM unit "
        "WHERE phase='e2v2' AND state='done' AND out_path IS NOT NULL ORDER BY seq").fetchall()
    conn.close()
    if not rows:
        print("  (no cells scored yet)")
        return
    print(f"  {'cell':<28} {'ex':>3} {'dg':>3} {'un':>3} {'tr':>3} "
          f"{'prec':>5} {'cov':>5} gate")
    for tag, out, arm, suite in rows:
        p = Path(out)
        if not p.exists():
            continue
        if suite == "e1v2":
            rs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
            ans = sum(1 for r in rs if r.get("answer"))
            print(f"  {short(tag):<28} {'-':>3} {'-':>3} {'-':>3} "
                  f"{sum(1 for r in rs if r.get('finish_reason') == 'length'):>3} "
                  f"{'-':>5} {ans / len(rs):>5.3f} E1")
            continue
        s = e2.score(p)
        print(f"  {short(tag):<28} {s['exact']:>3} {s['dangerous_miss']:>3} "
              f"{s['unit_mismatch']:>3} {s['truncated']:>3} {s['precision']:>5.3f} "
              f"{s['coverage']:>5.3f} {s['hard_gate'][:4]}")


if __name__ == "__main__":
    main()
