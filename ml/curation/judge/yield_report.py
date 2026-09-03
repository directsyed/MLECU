"""Yield of a judge run, score distribution of what it judged, by source, vs the prior state.

WHY (2026-08-16): no distribution tooling existed beyond `--status`'s corpus-wide histogram and
the end-of-run RunStats. Judging 314 community docs is only worth doing if the result is read
honestly: if the run yields very few >=4, the premise "forum threads hold diagnostic content the
reference corpus lacks" is weaker than assumed, and that has to be said, not spun.

Read-only (opens the corpus with ?mode=ro).

USAGE
    cd ml/curation && .venv/bin/python -m judge.yield_report --since 2026-08-16T13:00 [--tier community]
"""
from __future__ import annotations

import argparse
import collections
import sqlite3

from .config import load_config


def main(argv=None) -> int:
    ap = argparse.ArgumentParser("yield_report")
    ap.add_argument("--since", required=True, help="ISO timestamp; docs with judged_at >= this")
    ap.add_argument("--tier", default="community")
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    thr = cfg.judge.keep_threshold
    conn = sqlite3.connect(f"file:{cfg.resolve(cfg.corpus.db_path)}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    new = conn.execute(
        """SELECT source, judge_score, judge_model FROM document
           WHERE tier=? AND judgment_status='judged' AND judged_at >= ?""",
        (args.tier, args.since)).fetchall()
    prior = conn.execute(
        """SELECT source, judge_score FROM document
           WHERE tier=? AND judgment_status='judged' AND (judged_at < ? OR judged_at IS NULL)""",
        (args.tier, args.since)).fetchall()
    pending = conn.execute(
        """SELECT source, COUNT(*) FROM document
           WHERE tier=? AND judgment_status='pending' AND gate_status='kept' GROUP BY source""",
        (args.tier,)).fetchall()
    failed = conn.execute(
        """SELECT source, COUNT(*) FROM document
           WHERE tier=? AND judgment_status='failed' GROUP BY source""", (args.tier,)).fetchall()

    def hist(rows):
        return collections.Counter(int(r["judge_score"]) for r in rows if r["judge_score"] is not None)

    hn, hp = hist(new), hist(prior)
    print(f"tier={args.tier}  keep threshold >= {thr}")
    print(f"NEW since {args.since}: {len(new)} docs judged  by model {dict(collections.Counter(r['judge_model'] for r in new))}")
    print("  score histogram NEW  :", {k: hn.get(k, 0) for k in range(1, 6)},
          f" -> >= {thr}: {sum(v for k, v in hn.items() if k >= thr)} ({100*sum(v for k, v in hn.items() if k >= thr)/max(1,len(new)):.1f}%)")
    print("  score histogram PRIOR:", {k: hp.get(k, 0) for k in range(1, 6)},
          f" -> >= {thr}: {sum(v for k, v in hp.items() if k >= thr)} ({100*sum(v for k, v in hp.items() if k >= thr)/max(1,len(prior)):.1f}%) of {len(prior)}")
    by_src = collections.defaultdict(collections.Counter)
    for r in new:
        by_src[r["source"]][int(r["judge_score"])] += 1
    print("  NEW by source:")
    for s in sorted(by_src):
        c = by_src[s]
        n = sum(c.values())
        print(f"    {s:22s} n={n:3d}  {dict(sorted(c.items()))}  >= {thr}: {sum(v for k, v in c.items() if k >= thr)}")
    print("  still pending:", {r[0]: r[1] for r in pending} or "none")
    print("  failed:", {r[0]: r[1] for r in failed} or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
