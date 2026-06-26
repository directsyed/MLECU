"""CLI entrypoint. Mirrors the Hardware Parser ergonomics.

  python -m corpus_pipeline.cli --once                       # ingest all enabled sources
  python -m corpus_pipeline.cli --once --sources romraider_defs --dry-run   # isolate, no writes
  python -m corpus_pipeline.cli --status                     # corpus counts by source/kind
"""
from __future__ import annotations

import argparse
import logging
import sys

from .core.config import load_config
from .core.state import State
from .ingest import one_pass


def _setup_logging(debug: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def cmd_status(config_path: str | None) -> int:
    cfg = load_config(config_path)
    state = State(cfg.resolve(cfg.state.db_path))
    rows = state.counts_by_source()
    if not rows:
        print("(corpus empty)")
    else:
        print(f"{'source':<18} {'tier':<10} {'kind':<16} {'docs':>6} {'kept':>6} {'pending':>8}")
        for r in rows:
            print(f"{r['source']:<18} {r['tier']:<10} {r['kind']:<16} {r['docs']:>6} {r['kept'] or 0:>6} {r['pending_judge'] or 0:>8}")
    state.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="corpus_pipeline")
    ap.add_argument("--once", action="store_true", help="run one ingestion pass")
    ap.add_argument("--status", action="store_true", help="print corpus counts and exit")
    ap.add_argument("--sources", help="comma-separated subset of sources to run")
    ap.add_argument("--dry-run", action="store_true", help="fetch + gate but do not write")
    ap.add_argument("--debug", action="store_true", help="verbose logging")
    ap.add_argument("--config", help="path to config.yaml")
    args = ap.parse_args(argv)
    _setup_logging(args.debug)

    if args.status:
        return cmd_status(args.config)
    if args.once:
        only = [s.strip() for s in args.sources.split(",")] if args.sources else None
        results = one_pass(only=only, dry_run=args.dry_run, config_path=args.config)
        total_new = sum(r["new"] for r in results)
        total_kept = sum(r["kept"] for r in results)
        total_fetched = sum(r["fetched"] for r in results)
        print(f"pass complete{' (dry-run)' if args.dry_run else ''}: "
              f"fetched={total_fetched} kept={total_kept} new={total_new} "
              f"across {len(results)} source(s)")
        return 0 if all(r["ok"] for r in results) else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
