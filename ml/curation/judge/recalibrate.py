"""Re-calibrate a CANDIDATE judge model against the frozen adjudicated label set.

WHY THIS EXISTS
    The judge is a calibrated instrument. 3.6 was measured on 2026-07-05 against 111 adjudicated
    labels with pre-registered bars (keep/drop 93.1%, +/-1 97.7%, dangerous 0) and passed. Those
    numbers describe *3.6*. Swapping the model invalidates them, and an uncalibrated judge then
    silently gates what enters the RAG corpus.

    E1/E2/E4 are NOT evidence for the judging role — they measure diagnosis and value lookup.
    Agreement against human labels measures the actual job.

WHY IT DOESN'T TOUCH THE DATABASE
    `judge.cli --run` skips documents already marked 'judged', so re-scoring the calibration set
    would need a force path or a status reset — i.e. mutating the corpus to run a measurement.
    Unnecessary: `calibrate.agreement()` already accepts `judged_scores` directly. This module
    scores the docs in memory through the REAL judging path (same chunker, same prompt pack, same
    verdict parser, same aggregation) and hands the scores straight to `agreement()`.

    Nothing is written. Existing 3.6 judgments are untouched. Re-runnable, and safe to interrupt.

USAGE
    python -m judge.recalibrate --model-tag qwen3.8-27b-q8_0 [--limit N] [--out report.json]

    Point cfg.llm.base_url at whichever llama-server is serving the candidate. The --model-tag is
    recorded in the report only; it does not change any config or judgment row.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict

from corpus_pipeline.core.state import State

from . import calibrate, chunker, retrieval, verdict as verdict_mod
from .config import Config
from .prompts import PromptPack, load_prompt_pack
from .runner import _doc_synopsis, _judge_chunk

log = logging.getLogger("recalibrate")

# Pre-registered bars from the 2026-07-05 calibration. A candidate must MEET OR BEAT all three.
# `dangerous` is the one that matters most: truth <= 2 but judged >= keep threshold means junk
# promoted into the corpus.
BARS = {"keep_agree_pct": 93.1, "within1_pct": 97.7, "dangerous_max": 0}


def score_docs_in_memory(cfg: Config, state: State, doc_ids: list[int],
                         limit: int | None = None) -> tuple[dict[int, int], list[dict]]:
    """Judge each doc through the real path and return {doc_id: score} plus per-doc detail.

    Failures are SKIPPED, never defaulted to a score — a fabricated score would corrupt the
    very measurement this exists to produce.
    """
    pack = load_prompt_pack(cfg.resolve(cfg.judge.prompts_dir))
    scores: dict[int, int] = {}
    detail: list[dict] = []
    todo = doc_ids[:limit] if limit else doc_ids

    for n, doc_id in enumerate(todo, 1):
        row = state.conn.execute("SELECT * FROM document WHERE id=?", (doc_id,)).fetchone()
        if row is None:
            log.warning("doc %s not found, skipping", doc_id)
            continue
        t0 = time.monotonic()
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
    return scores, detail


def verdict_vs_bars(ag) -> tuple[bool, list[str]]:
    """Does the candidate meet every pre-registered bar? Returns (passed, per-bar lines)."""
    lines, ok = [], True
    for name, bar, got, cmp_ in (
        ("keep/drop agreement", BARS["keep_agree_pct"], ag.keep_agree_pct, ">="),
        ("within +/-1", BARS["within1_pct"], ag.within1_pct, ">="),
        ("dangerous (truth<=2 judged>=thr)", BARS["dangerous_max"], ag.dangerous, "<="),
    ):
        passed = (got >= bar) if cmp_ == ">=" else (got <= bar)
        ok &= passed
        lines.append(f"  {'PASS' if passed else 'FAIL'}  {name}: {got} (bar {cmp_} {bar})")
    return ok, lines


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser("recalibrate")
    ap.add_argument("--model-tag", required=True, help="recorded in the report only")
    ap.add_argument("--limit", type=int, default=None, help="first N docs (smoke)")
    ap.add_argument("--out", default=None, help="write a JSON report here")
    ap.add_argument("--truth-rater", default="adjudicated")
    args = ap.parse_args()

    cfg = Config()
    state = State(cfg.resolve(cfg.corpus.db_path))
    label_set = cfg.calibration.set_name

    truth = {r["doc_id"]: r["score"] for r in state.labels(label_set, rater=args.truth_rater)}
    if not truth:
        sys.exit(f"no '{args.truth_rater}' labels for set={label_set}")
    log.info("calibration set=%s truth labels=%d (candidate=%s)",
             label_set, len(truth), args.model_tag)

    scores, detail = score_docs_in_memory(cfg, state, sorted(truth), limit=args.limit)
    if not scores:
        sys.exit("no documents scored — nothing to compare")

    ag = calibrate.agreement(state, cfg, label_set=label_set,
                             truth_rater=args.truth_rater, judged_scores=scores)
    passed, bar_lines = verdict_vs_bars(ag)

    print("\n" + "=" * 72)
    print(f"CANDIDATE: {args.model_tag}   n={ag.n} of {len(truth)} labelled docs")
    print(calibrate.format_report(ag, cfg.judge.keep_threshold))
    print("\nagainst the PRE-REGISTERED bars (2026-07-05, measured on 3.6):")
    print("\n".join(bar_lines))
    print(f"\nVERDICT: {'PASS — candidate may replace the incumbent' if passed else 'FAIL — do NOT swap the judge'}")
    print("=" * 72)

    if args.out:
        with open(args.out, "w") as fh:
            json.dump({"model_tag": args.model_tag, "label_set": label_set,
                       "truth_rater": args.truth_rater, "bars": BARS,
                       "passed": passed, "agreement": asdict(ag), "detail": detail},
                      fh, indent=2, default=str)
        print(f"report -> {args.out}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
