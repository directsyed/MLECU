"""Curation CLI, mirrors corpus_pipeline/cli.py ergonomics.

  python -m judge.cli --status                      # judged/pending/failed + score histogram
  python -m judge.cli --run [--limit N] [--sources a,b] [--dry-run]
  python -m judge.cli --reindex                     # force-rebuild the grounding FTS index
  python -m judge.cli --retry-failed
  python -m judge.cli --sample                      # freeze the calibration doc-id set
  python -m judge.cli --label --set NAME --rater syed   # terminal labeling loop
  python -m judge.cli --agreement --set NAME --truth adjudicated [--vs claude]
"""
from __future__ import annotations

import argparse
import logging
import sys
import textwrap
from pathlib import Path          # was missing: `--harvest --out X` raised NameError

from corpus_pipeline.core.state import State

from . import calibrate, retrieval, runner
from .config import load_config


def _state(cfg) -> State:
    return State(cfg.resolve(cfg.corpus.db_path))


def _status(cfg) -> int:
    s = _state(cfg)
    # No gone_at filter: gone-ness affects scraping only (decisions.md 2026-07-22, NARROW).
    # Counting only not-gone docs here under-reported the pending pool by ~300 (2026-08-16).
    rows = s.conn.execute(
        """SELECT judgment_status, COUNT(*) FROM document
           WHERE gate_status='kept' GROUP BY judgment_status""").fetchall()
    print("judge, corpus curation status")
    for st, n in rows:
        print(f"  {st:10s}: {n}")
    tiers = s.conn.execute(
        """SELECT tier, judgment_status, COUNT(*) FROM document
           WHERE gate_status='kept' GROUP BY tier, judgment_status ORDER BY tier, judgment_status"""
    ).fetchall()
    print("  by tier:", ", ".join(f"{t}/{st}={n}" for t, st, n in tiers))
    hist = s.conn.execute(
        """SELECT judge_score, COUNT(*) FROM document
           WHERE judge_score IS NOT NULL GROUP BY judge_score ORDER BY judge_score""").fetchall()
    if hist:
        print("  score histogram:", {int(k): v for k, v in hist})
    thr = cfg.judge.keep_threshold
    kept = s.conn.execute("SELECT COUNT(*) FROM document WHERE judge_score>=?", (thr,)).fetchone()[0]
    print(f"  keep (>={thr}): {kept}")
    s.close()
    return 0


def _run(cfg, args) -> int:
    s = _state(cfg)
    sources = set(args.sources.split(",")) if args.sources else None
    stats = runner.run(cfg, s, limit=args.limit, sources=sources, dry_run=args.dry_run,
                       reindex=not args.no_reindex)
    print(f"run complete: judged={stats.judged} auto_passed={stats.auto_passed} "
          f"failed={stats.failed} chunks={stats.chunks}")
    if stats.score_hist:
        print(f"scores: {dict(sorted(stats.score_hist.items()))}")
    if stats.stopped:
        print(f"RUN STOPPED EARLY: {stats.stopped}, remaining docs left 'pending'; "
              f"re-run to continue")
    s.close()
    if stats.stopped:
        return 2
    return 0 if stats.failed == 0 else 1


def _label(cfg, args) -> int:
    s = _state(cfg)
    ids = (calibrate.blind_subset(s, cfg) if args.blind
           else calibrate.freeze_sample(s, cfg))
    done = {r["doc_id"] for r in s.labels(args.set or cfg.calibration.set_name,
                                          rater=args.rater)}
    todo = [i for i in ids if i not in done]
    print(f"labeling as rater={args.rater} set={args.set or cfg.calibration.set_name}, "
          f"{len(todo)} of {len(ids)} remaining (resumable; q quits)")
    for doc_id in todo:
        row = s.conn.execute("SELECT * FROM document WHERE id=?", (doc_id,)).fetchone()
        print("=" * 78)
        print(f"[{doc_id}] {row['source']} | {row['tier']} | {row['title']}")
        print(row["url"] or "")
        print("-" * 78)
        # FULL text, never truncated, a 6k-char preview already skewed one guard read.
        # Long docs scroll; use terminal scrollback, or open the URL alongside.
        print(row["text"])
        print("-" * 78)
        print(f"[{len(row['text'])} chars | {row['tier']} | {row['source']}]")
        while True:
            ans = input("score 1-5 (n=note, s=skip, q=quit): ").strip().lower()
            if ans == "q":
                s.close(); return 0
            if ans == "s":
                break
            if ans in {"1", "2", "3", "4", "5"}:
                note = input("note (enter for none): ").strip()
                s.add_label(doc_id, score=int(ans),
                            label_set=args.set or cfg.calibration.set_name,
                            rater=args.rater, notes=note)
                break
    s.close()
    print("label set complete.")
    return 0


def _agreement(cfg, args) -> int:
    s = _state(cfg)
    ag = calibrate.agreement(s, cfg, label_set=args.set or cfg.calibration.set_name,
                             truth_rater=args.truth, other_rater=args.vs)
    print(calibrate.format_report(ag, cfg.judge.keep_threshold))
    s.close()
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="judge", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--status", action="store_true")
    p.add_argument("--run", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("--sources")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--reindex", action="store_true")
    p.add_argument("--no-reindex", action="store_true",
                   help="with --run: do NOT rebuild ref_fts even if the reference count moved "
                        "(leaves the retrieval index exactly as it is; logs the delta)")
    p.add_argument("--retry-failed", action="store_true")
    p.add_argument("--sample", action="store_true")
    p.add_argument("--label", action="store_true")
    p.add_argument("--blind", action="store_true", help="label only the blind subset")
    p.add_argument("--set")
    p.add_argument("--rater", default="syed")
    p.add_argument("--harvest", action="store_true",
                   help="extract training pairs from chunk>=threshold verdicts (JSONL)")
    p.add_argument("--out", help="harvest output path (default data/pairs/pairs-<rubric>.jsonl)")
    p.add_argument("--agreement", action="store_true")
    p.add_argument("--truth", default="adjudicated")
    p.add_argument("--vs", help="compare truth rater against another rater instead of the judge")
    p.add_argument("--config")
    p.add_argument("--debug", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config(args.config)

    if args.status:
        return _status(cfg)
    if args.run:
        return _run(cfg, args)
    if args.reindex:
        s = _state(cfg)
        s.set_meta("ref_fts_doc_count", "")      # invalidate
        rebuilt = retrieval.ensure_index(s, cfg)
        print(f"reindexed: {rebuilt}")
        s.close()
        return 0
    if args.retry_failed:
        s = _state(cfg)
        print(f"reset {s.reset_failed_judgments()} failed docs to pending")
        s.close()
        return 0
    if args.sample:
        s = _state(cfg)
        ids = calibrate.freeze_sample(s, cfg)
        print(f"calibration set {cfg.calibration.set_name}: {len(ids)} docs frozen")
        s.close()
        return 0
    if args.harvest:
        from .harvest import harvest
        s = _state(cfg)
        out = Path(args.out) if args.out else cfg.resolve(f"data/pairs/pairs-{cfg.rubric_version}.jsonl")
        st = harvest(s, cfg, out)
        print(f"harvest -> {out}")
        print(f"  chunks with pairs: {st['chunks_seen']}  pairs seen: {st['pairs_seen']}")
        print(f"  PAIRS KEPT: {st['pairs_kept']} (dropped {st['dropped_no_outcome']} without outcome)")
        print(f"  from {st['docs']} docs  by relevance: {st['by_relevance']}")
        s.close()
        return 0
    if args.label:
        return _label(cfg, args)
    if args.agreement:
        return _agreement(cfg, args)
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
