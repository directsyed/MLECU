"""Re-score every historical E2 result file with scorer v2 and publish the delta.

ANTI-BENCHMARK-MAXXING CONTRACT (decisions.md, 2026-07-25): when the scorer changes, every
affected result is re-scored and the OLD number is published beside the NEW one. A fix that
only ever moves numbers upward is a fix that needs auditing, so this reports movement in both
directions and names every probe whose class changed.

Run:  car/.venv/bin/python rescore_v1_vs_v2.py            (cwd: ml/eval)
      car/.venv/bin/python rescore_v1_vs_v2.py --md       (markdown table for the rundown)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import e2                                          # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"


def v1_classify(probe: dict, answer: dict, tol: float = 1.0) -> str:
    """Scorer v1.1 verbatim, the code that produced the showdown verdicts."""
    import re
    _NUM = re.compile(r"-?(?:\d+(?:[.,]\d+)?|[.]\d+)")
    _SPACED = re.compile(r"(?<=\d)[  ](?=\d{3}\b)")

    def parse(s):
        if not s:
            return None
        s = _SPACED.sub("", str(s).replace(",", ""))
        m = _NUM.search(s)
        return float(m.group()) if m else None

    if answer.get("must_retrieve") or answer.get("value") in (None, ""):
        return "honest_decline"
    got = parse(answer["value"])
    if got is None:
        return "unparseable"
    exp = parse(probe["expected_value"])
    if exp is None:
        return "unparseable"
    return "exact" if abs(got - exp) <= abs(exp) * tol / 100.0 else "dangerous_miss"


def main() -> None:
    md = "--md" in sys.argv
    rows_out = []
    flips: Counter = Counter()
    detail: list[str] = []

    for path in sorted(RESULTS.glob("e2-*.jsonl")):
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        if not rows:
            continue
        model = sorted({r.get("model", "?") for r in rows})[0]
        arm = rows[0].get("arm", "?")
        guard = any("pre_guard_class" in r for r in rows)
        old_c: Counter = Counter()
        new_c: Counter = Counter()
        for r in rows:
            probe = {"expected_value": r.get("expected_value"), "unit": r.get("unit", ""),
                     "probe_id": r.get("probe_id")}
            ans = r.get("answer") or {}
            tol = r.get("tolerance_pct", 1.0)
            old = r.get("class") or v1_classify(probe, ans, tol)
            new = e2.classify(probe, ans, tol, r.get("finish_reason"))
            old_c[old] += 1
            new_c[new] += 1
            if old != new:
                flips[(old, new)] += 1
                detail.append(f"{path.name}\t{r.get('probe_id')}\t{old} -> {new}\t"
                              f"exp={r.get('expected_value')!r}\tgot={ans.get('value')!r}")
        rows_out.append({
            "file": path.name, "model": model, "arm": arm, "guard": guard, "n": len(rows),
            "old_exact": old_c["exact"], "new_exact": new_c["exact"],
            "old_dang": old_c["dangerous_miss"], "new_dang": new_c["dangerous_miss"],
            "new_unit_mismatch": new_c["unit_mismatch"],
            "new_ambiguous": new_c["ambiguous_parse"],
            "new_no_answer": new_c["no_answer"], "new_truncated": new_c["truncated"],
        })

    if md:
        print("| file | model | arm | n | exact v1 | exact v2 | dang v1 | dang v2 | "
              "unit_mm | ambig | no_ans |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in rows_out:
            print(f"| {r['file']} | {r['model']} | {r['arm']}{'+g' if r['guard'] else ''} | "
                  f"{r['n']} | {r['old_exact']} | {r['new_exact']} | {r['old_dang']} | "
                  f"{r['new_dang']} | {r['new_unit_mismatch']} | {r['new_ambiguous']} | "
                  f"{r['new_no_answer']} |")
    else:
        for r in rows_out:
            d_ex = r["new_exact"] - r["old_exact"]
            d_dg = r["new_dang"] - r["old_dang"]
            print(f"{r['file'][:46]:46s} {r['model'][:26]:26s} arm{r['arm']}"
                  f"{'+g' if r['guard'] else '  '} n={r['n']:3d}  "
                  f"exact {r['old_exact']:2d}->{r['new_exact']:2d} ({d_ex:+d})  "
                  f"dang {r['old_dang']:2d}->{r['new_dang']:2d} ({d_dg:+d})  "
                  f"unit_mm={r['new_unit_mismatch']} amb={r['new_ambiguous']} "
                  f"noans={r['new_no_answer']}")

    print("\n=== class transitions (v1 -> v2), all files ===")
    for (o, n), c in flips.most_common():
        print(f"  {o:16s} -> {n:16s}  {c}")

    tot_old_d = sum(r["old_dang"] for r in rows_out)
    tot_new_d = sum(r["new_dang"] for r in rows_out)
    tot_old_e = sum(r["old_exact"] for r in rows_out)
    tot_new_e = sum(r["new_exact"] for r in rows_out)
    print(f"\nTOTAL across {len(rows_out)} files: exact {tot_old_e} -> {tot_new_e}, "
          f"dangerous {tot_old_d} -> {tot_new_d}")

    Path("results/rescore-v1-vs-v2-detail.tsv").write_text("\n".join(detail) + "\n")
    print(f"per-probe detail ({len(detail)} changed rows) -> "
          f"results/rescore-v1-vs-v2-detail.tsv")


if __name__ == "__main__":
    main()
