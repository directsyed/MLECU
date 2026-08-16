"""Re-calibrate a CANDIDATE judge model against the frozen adjudicated label set.

WHY THIS EXISTS
    The judge is a calibrated instrument. 3.6 was measured on 2026-07-05 against the adjudicated
    `calibration-100` labels and passed the PRE-REGISTERED bars. Those numbers describe *3.6*.
    Swapping the model invalidates them, and an uncalibrated judge then silently gates what enters
    the RAG corpus.

    E1/E2/E4 are NOT evidence for the judging role — they measure diagnosis and value lookup.
    Agreement against human labels measures the actual job.

TWO BAR SETS — kept distinct on purpose (found 2026-08-16)
    * PRE-REGISTERED (the real gate): stored in the corpus DB as `meta['calibration-100:pass_bars']`
      on 2026-07-05 *before* results — keep/drop >= 90, within +/-1 >= 90, dangerous == 0.
    * INCUMBENT: what 3.6 actually *achieved* on that day (93.1 / 97.7 / 0, rubric r2, n=87). An
      earlier revision of this file mislabelled these as "pre-registered". They are the number to
      beat, not the registration. Syed's ruling (2026-08-16): a candidate replaces the incumbent
      only if it clears the pre-registered bars AND matches-or-beats the incumbent's LIKE-FOR-LIKE
      recalibration on the same engine/n/rubric AND has zero dangerous cells.

WHY IT DOESN'T TOUCH THE DATABASE
    `judge.cli --run` skips documents already marked 'judged', so re-scoring the calibration set
    would need a force path or a status reset — i.e. mutating the corpus to run a measurement.
    Unnecessary: `calibrate.agreement()` already accepts `judged_scores` directly. This module
    scores the docs in memory through the REAL judging path (same chunker, same prompt pack, same
    verdict parser, same aggregation) and hands the scores straight to `agreement()`.

    Nothing is written to the corpus. Existing judgments are untouched. Re-runnable, and safe to
    interrupt: with `--out` the report is checkpointed after EVERY doc and `--resume` picks up.

USAGE
    python -m judge.recalibrate --model-tag qwen3.8-27b-q8_0 --out report.json [--resume]
                                [--limit N] [--doc-ids 960,881] [--config path]

    Point cfg.llm.base_url at whichever llama-server is serving the candidate. The --model-tag is
    recorded in the report only; the served model id (from /v1/models) is recorded alongside it so
    the report is self-describing.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from corpus_pipeline.core.state import State

from . import calibrate, chunker, llm
from .config import Config, load_config
from .prompts import load_prompt_pack
from .runner import _doc_synopsis, _judge_chunk

log = logging.getLogger("recalibrate")

# Fallback only — the authoritative pre-registration lives in the DB (see load_preregistered_bars).
PREREGISTERED_BARS_DEFAULT = {"keep_agree_pct": 90.0, "within1_pct": 90.0, "dangerous_max": 0}

# What the incumbent (Qwen3.6-27B Q8, rubric r2) ACHIEVED on 2026-07-05, n=87. Not a registration.
INCUMBENT_BARS = {"keep_agree_pct": 93.1, "within1_pct": 97.7, "dangerous_max": 0,
                  "note": "3.6 achieved 2026-07-05 (rubric r2, n=87) — beat-the-incumbent, "
                          "NOT the pre-registration"}


def load_preregistered_bars(state: State, label_set: str) -> dict:
    """The bars registered before results, from `meta['<set>:pass_bars']`.

    Stored shape: {"keep_drop_pct", "within1_pct", "dangerous_cells", ...}. Normalised here to the
    same keys as INCUMBENT_BARS so one comparator serves both."""
    raw = state.get_meta(f"{label_set}:pass_bars")
    if not raw:
        log.warning("no meta['%s:pass_bars'] — using default pre-registered bars %s",
                    label_set, PREREGISTERED_BARS_DEFAULT)
        return dict(PREREGISTERED_BARS_DEFAULT, source="default (meta missing)")
    d = json.loads(raw)
    return {"keep_agree_pct": float(d["keep_drop_pct"]),
            "within1_pct": float(d["within1_pct"]),
            "dangerous_max": int(d.get("dangerous_cells", 0)),
            "source": f"meta['{label_set}:pass_bars'] registered {d.get('registered', '?')}"}


def score_docs_in_memory(cfg: Config, state: State, doc_ids: list[int],
                         limit: int | None = None,
                         prior_scores: dict[int, int] | None = None,
                         prior_detail: list[dict] | None = None,
                         checkpoint: Callable[[dict[int, int], list[dict]], None] | None = None,
                         ) -> tuple[dict[int, int], list[dict]]:
    """Judge each doc through the real path and return {doc_id: score} plus per-doc detail.

    Failures are SKIPPED, never defaulted to a score — a fabricated score would corrupt the
    very measurement this exists to produce. Docs present in `prior_scores` are not re-judged
    (resume). `checkpoint(scores, detail)` is called after every doc so a crash loses one doc.
    """
    pack = load_prompt_pack(cfg.resolve(cfg.judge.prompts_dir))
    scores: dict[int, int] = dict(prior_scores or {})
    detail: list[dict] = list(prior_detail or [])
    todo = doc_ids[:limit] if limit else doc_ids
    todo = [d for d in todo if d not in scores]
    if prior_scores:
        log.info("resume: %d docs already scored, %d to go", len(prior_scores), len(todo))

    for n, doc_id in enumerate(todo, 1):
        row = state.conn.execute("SELECT * FROM document WHERE id=?", (doc_id,)).fetchone()
        if row is None:
            log.warning("doc %s not found, skipping", doc_id)
            continue
        t0 = time.monotonic()
        # drop any earlier error entry for this doc (resume after a failure retries it)
        detail = [d for d in detail if d.get("doc_id") != doc_id]
        try:
            chunks = chunker.chunk(row["text"], cfg.chunking.max_chars,
                                   cfg.chunking.overlap_chars)
            synopsis = (_doc_synopsis(cfg, pack, row, chunks[0].text)
                        if len(chunks) > 1 else "")
            chunk_scores, lengths = [], []
            for ch in chunks:
                v, _refs, _meta = _judge_chunk(cfg, pack, state, row, ch,
                                               policy="", doc_synopsis=synopsis)
                chunk_scores.append(v.score)
                lengths.append(len(ch.text))
            doc_score = chunker.aggregate(chunk_scores, lengths, cfg.chunking.aggregate)
            scores[doc_id] = doc_score
            detail.append({"doc_id": doc_id, "score": doc_score,
                           "chunk_scores": chunk_scores, "n_chunks": len(chunks),
                           "title": (row["title"] or "")[:80],
                           "source": row["source"], "tier": row["tier"],
                           "latency_s": round(time.monotonic() - t0, 1)})
            log.info("[%d/%d] doc %s -> %d (%d chunks, %.0fs)", n, len(todo), doc_id,
                     doc_score, len(chunks), time.monotonic() - t0)
        except Exception as e:                       # noqa: BLE001 - report, never fabricate
            log.error("[%d/%d] doc %s FAILED: %s: %s", n, len(todo), doc_id,
                      type(e).__name__, e)
            detail.append({"doc_id": doc_id, "error": f"{type(e).__name__}: {e}"})
        if checkpoint is not None:
            checkpoint(scores, detail)
    return scores, detail


def verdict_vs_bars(ag, bars: dict) -> tuple[bool, list[str]]:
    """Does the candidate meet every bar in `bars`? Returns (passed, per-bar lines)."""
    lines, ok = [], True
    for name, bar, got, cmp_ in (
        ("keep/drop agreement", bars["keep_agree_pct"], ag.keep_agree_pct, ">="),
        ("within +/-1", bars["within1_pct"], ag.within1_pct, ">="),
        ("dangerous (truth<=2 judged>=thr)", bars["dangerous_max"], ag.dangerous, "<="),
    ):
        passed = (got >= bar) if cmp_ == ">=" else (got <= bar)
        ok &= passed
        lines.append(f"  {'PASS' if passed else 'FAIL'}  {name}: {got} (bar {cmp_} {bar})")
    return ok, lines


def _load_prior(out: str | None, resume: bool) -> tuple[dict[int, int], list[dict]]:
    if not (resume and out and Path(out).exists()):
        return {}, []
    with open(out) as fh:
        rep = json.load(fh)
    scores = {int(k): int(v) for k, v in (rep.get("scores") or {}).items()}
    detail = [d for d in rep.get("detail", []) if "score" in d and d.get("doc_id") in scores]
    log.info("resume from %s: %d prior scores", out, len(scores))
    return scores, detail


def _write_report(out: str, payload: dict) -> None:
    tmp = f"{out}.tmp"
    with open(tmp, "w") as fh:
        json.dump(payload, fh, indent=2, default=str)
    Path(tmp).replace(out)                     # atomic — a crash mid-write cannot corrupt --out


def main(argv=None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser("recalibrate")
    ap.add_argument("--model-tag", required=True, help="recorded in the report only")
    ap.add_argument("--limit", type=int, default=None, help="first N docs (smoke)")
    ap.add_argument("--doc-ids", default=None,
                    help="comma-separated doc ids to score (subset of the label set)")
    ap.add_argument("--out", default=None, help="write/checkpoint a JSON report here")
    ap.add_argument("--resume", action="store_true",
                    help="reuse scores already in --out; re-judge only the rest")
    ap.add_argument("--truth-rater", default="adjudicated")
    ap.add_argument("--config", default=None, help="config.yaml path (default: ml/curation/config.yaml)")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)                 # NOT Config(): defaults are r1 / 1500 tokens
    state = State(cfg.resolve(cfg.corpus.db_path))
    label_set = cfg.calibration.set_name
    served = llm.health_check(cfg.llm)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    truth = {r["doc_id"]: r["score"] for r in state.labels(label_set, rater=args.truth_rater)}
    if not truth:
        sys.exit(f"no '{args.truth_rater}' labels for set={label_set}")
    todo = sorted(truth)
    if args.doc_ids:
        want = {int(x) for x in args.doc_ids.split(",") if x.strip()}
        unknown = want - set(truth)
        if unknown:
            sys.exit(f"--doc-ids not in label set {label_set}: {sorted(unknown)}")
        todo = [d for d in todo if d in want]
    log.info("calibration set=%s truth labels=%d candidate=%s served=%s rubric=%s "
             "max_completion_tokens=%d", label_set, len(truth), args.model_tag, served,
             cfg.rubric_version, cfg.llm.max_completion_tokens)

    prereg = load_preregistered_bars(state, label_set)
    prior_scores, prior_detail = _load_prior(args.out, args.resume)

    def report(scores, detail, *, complete: bool, agreement=None,
               passed_prereg=None, passed_incumbent=None) -> dict:
        return {"model_tag": args.model_tag, "served_model": served,
                "rubric_version": cfg.rubric_version,
                "max_completion_tokens": cfg.llm.max_completion_tokens,
                "label_set": label_set, "truth_rater": args.truth_rater,
                "started_at": started,
                "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "complete": complete,
                "n_truth": len(truth), "n_scored": len(scores),
                "bars_preregistered": prereg, "bars_incumbent": INCUMBENT_BARS,
                "passed_preregistered": passed_prereg, "passed_incumbent": passed_incumbent,
                # `passed` == the real gate (pre-registered incl. dangerous==0)
                "passed": passed_prereg,
                "agreement": asdict(agreement) if agreement is not None else None,
                "scores": {str(k): v for k, v in sorted(scores.items())},
                "detail": detail}

    checkpoint = None
    if args.out:
        def checkpoint(scores, detail):            # noqa: E306
            _write_report(args.out, report(scores, detail, complete=False))

    scores, detail = score_docs_in_memory(cfg, state, todo, limit=args.limit,
                                          prior_scores=prior_scores, prior_detail=prior_detail,
                                          checkpoint=checkpoint)
    if not scores:
        sys.exit("no documents scored — nothing to compare")

    ag = calibrate.agreement(state, cfg, label_set=label_set,
                             truth_rater=args.truth_rater, judged_scores=scores)
    passed_prereg, prereg_lines = verdict_vs_bars(ag, prereg)
    passed_incumbent, incumbent_lines = verdict_vs_bars(ag, INCUMBENT_BARS)

    print("\n" + "=" * 72)
    print(f"CANDIDATE: {args.model_tag}  served={served}  rubric={cfg.rubric_version}  "
          f"n={ag.n} of {len(truth)} labelled docs")
    print(calibrate.format_report(ag, cfg.judge.keep_threshold))
    print(f"\nagainst the PRE-REGISTERED bars ({prereg.get('source', '')}):")
    print("\n".join(prereg_lines))
    print(f"\nagainst the INCUMBENT's achieved numbers ({INCUMBENT_BARS['note']}):")
    print("\n".join(incumbent_lines))
    verdict = ("PASS pre-registered" if passed_prereg else "FAIL pre-registered — do NOT swap")
    verdict += (" · beats/matches incumbent's 2026-07-05 numbers" if passed_incumbent
                else " · below incumbent's 2026-07-05 numbers")
    print(f"\nVERDICT: {verdict}")
    print("NOTE: the swap decision also needs the incumbent's LIKE-FOR-LIKE recalibration on the "
          "same engine (Syed ruling 2026-08-16); compare the two reports' agreement blocks.")
    print("=" * 72)

    if args.out:
        _write_report(args.out, report(scores, detail, complete=True, agreement=ag,
                                       passed_prereg=passed_prereg,
                                       passed_incumbent=passed_incumbent))
        print(f"report -> {args.out}")
    sys.exit(0 if passed_prereg else 1)


if __name__ == "__main__":
    main()
