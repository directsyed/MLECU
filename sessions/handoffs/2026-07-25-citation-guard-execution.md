# 2026-07-25 - Citation-guard execution (plan §1): every command, every finding

Companion to docs/PLAN-post-showdown-2026-07-25.md §1. Written to Syed's full-writeup
directive. Commits: 87afb45 (guard+fixes), 79bf270 (decisions), this session's tail.

## Sequence of actions, exactly

1. **Judge failure diagnosed** (one grep): `grep -B2 -A12 "STAGE 5" overnight-20260722.log`
   → `ModuleNotFoundError: corpus_pipeline`. Root cause: the overnight chain ran judge.cli
   with `car/.venv`, but the judge has ITS OWN venv (`ml/curation/.venv`, corpus_pipeline
   installed editable, found via `find -name "*.pth"`). Fix = one line in the new chain:
   `cd ml/curation && .venv/bin/python -m judge.cli --run`.

2. **Guard built**: `ml/eval/harness/citation_guard.py` (~90 lines). API:
   `verify(value, snippet_texts, rel_tol=0.01) -> {verdict, unverified}` with verdicts
   declined / no_numbers / cited / blocked; `apply()` converts blocked answers to
   `{"value": None, "must_retrieve": True}` and returns the record for the gauge.
   Details: number regex incl. leading-dot; commas stripped; `[REF n]` citation ids
   excluded; evidence gets a "healed" second pass joining digit runs split by
   space/soft-hyphen/zero-width (the 07-16 PDF lesson).

3. **Unit tests**: `ml/eval/tests/test_citation_guard.py`: 10 tests (cited/tolerance/
   blocked-conversion/all-numbers-must-ground/decline-passthrough/qualitative-passthrough/
   comma+ratio/PDF-mangling/no-evidence/leading-dot/[REF]-exclusion).
   Run: `car/.venv/bin/python -m pytest ml/eval/tests/test_citation_guard.py -q`.

4. **Wired into the harness**: `e2.run_arm(..., guard=True)`: for retrieval arms, re-runs
   the deterministic `retrieval.retrieve()` (identical snippets to what build_user
   injected), records `pre_guard_class` + `guard` per row, classifies the POST-guard
   answer. `e2.score()` gains `fabrications: {attempted, blocked, leaked}` +
   `guard_false_blocks` whenever guard rows are present, the clamp carries a gauge,
   pre-guard model quality is never hidden. CLI: `--guard`.

5. **Test suite exposed two REAL bugs while wiring** (33+11 green after):
   - BM25 tie nondeterminism: equal-score rows ordered differently under different LIMITs
     → `ORDER BY bm25(ref_fts), rowid` (total order).
   - Dense-index cache ignored `index_path` (first index loaded served to every config)
     → cache keyed by path. Both in retrieval.py, both committed with comments.

6. **Retro-test** (the measurement the plan demanded): guard applied to every KNOWN
   fabrication row in history + all of B-v2's correct rows, snippets reconstructed via the
   deterministic retrievers (hybrid@6 for B-v2 rows, bm25@3 for B-v1 rows).
   Results:
   - B-v1's 11 fabrications: **11/11 blocked, 0 would-leak** (incl. all 5 retrieval-induced).
   - B-v2's 2: one blocked... and one **exposed a SCORER BUG** (below); the other
     (e2-5723-1) is the real blind-spot case: `cited`.
   - False positives: 1 → fixed ([REF n] exclusion) → **0/26 final**.

7. **SCORER v1.1** (logged amendment, decisions.md): retro-test caught `parse_number`
   mis-scoring CORRECT answers as dangerous_miss: `'.84'` (leading-dot) parsed as 84 -
   probe e2-466-0's correct 0.84 scored dangerous in EVERY run that stated it; `'30 000'`
   (spaced thousands) parsed as 30, e2-3694-2's correct 30000 likewise. Fix applied to
   e2.py + guard; **all 12 historical E2 files re-scored uniformly, deltas published**
   (PROGRESS.md): B-v2@6 2→1 dangerous / 25→26 exact; C 45→44; D@6 15→14; B-v1 11→9.
   **No hard-gate verdict flipped by the amendment**: it passes nothing by itself.

8. **e2-5723-1 anatomy** (the last true fabrication): "40→50 psi regulator, % flow gain?"
   Expected 11.8 (√(50/40)=1.118, Banish ch26, judge score 5). The model retrieved the
   RIGHT chapter, did the RIGHT physics, stated **11%**: rounding, outside the 1%
   tolerance, and 11 appears in the evidence → guard verdict `cited`. Predicted pre-run:
   this would keep the gate red, and stands per the anti-benchmark-maxxing contract
   (tolerance is pre-registered; loosening it post-hoc was explicitly vetoed).

9. **B-v3 run** (`ml/eval/bv3-chain.sh`, detached setsid):
   server = certified judge config (base Q8, 3.5:1 split, -c 16384, MTP);
   `harness.cli --run-e2 --arm B --runs 2 --guard --top-k 6 --probes data/e2_probes_v1.jsonl
   --model-name "qwen3.6-27b-q8_0|hybrid-k6+guard-v1"`; then the judge batch on the
   correct venv; server down; logs ml/finetuning/logs/bv3-20260725.log.

## B-v3 VERDICT (both runs byte-identical, determinism now 9/9 batteries)

| metric | value |
|---|---|
| exact | **26/69 (37.7%)**: best base-model result on record |
| honest_decline | 42 |
| dangerous (leaked) | **1**: e2-5723-1 only |
| fabrications gauge | attempted 1 / blocked 0 / leaked 1 |
| guard false blocks | 0 |
| **hard gate** | **FAIL, by one rounding-precision case; result stands red** |

Note the gauge's honesty: the guard blocked ZERO here because this config's model only
ATTEMPTS one fabrication (the rider already tamed the base model); the guard's protective
value was proven on history (13/13) and is insurance against future arms, the fine-tune
attempted 45.

## Judge batch: FIXED and running
venv root cause above; batch live (first verdicts: doc 563 score=3, 567 score=5), ~400
docs incl. re-queued 5781 (the LGT thread), completion + 5781's verdict reported when done.

## On Syed's desk now
The gate hangs on one probe where the model is *approximately right and verifiably
grounded*. Three honest options: (a) accept the red gate as the standing record until
something changes materially; (b) a rider-v2 experiment (B-v4, logged): instruct verbatim
value quoting; no rounding/arithmetic on retrieved figures, legitimate behavior-shaping,
runs against the same gate; (c) leave tolerance untouched (pre-registered; not revisitable
without a decisions.md entry and fresh eyes, NOT recommended from inside this result).
