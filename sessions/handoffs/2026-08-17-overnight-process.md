# 2026-08-16/17: Overnight autonomous run: PROCESS DOCUMENT

Running commentary of everything executed tonight, what, why, exact commands, how it wires in.
The *results* are in `2026-08-17-overnight-morning-report.md`; this file is the how.
Plan followed: `~/.claude/plans/read-the-newest-checklist-bright-sunbeam.md` (approved by Syed 06:2x UTC).

## T0: Preflight (06:29 UTC)

- `curl -sf http://127.0.0.1:8080/v1/models` → serving `unsloth/Qwen3.8-27B-Q8_0.gguf` (PID 1446703, up since Aug 14).
- `git status` clean, HEAD `5543b71` (the runbook commit). Nothing from the runbook had been executed.
- Read-only sqlite (`?mode=ro` URI): `ref_fts` = 5638 rows, `meta.ref_fts_doc_count` = 5638,
  reference-kept-not-gone = **5649** (so the next unguarded `judge.cli --run` would rebuild `ref_fts` +11,
  see C2-fix `--no-reindex`). `meta['calibration-100:pass_bars']` = **90/90/0** (the real pre-registration).
- Backups (before any DB write, WAL-safe, `.backup` copies a consistent snapshot even with an open WAL,
  unlike `cp` of the main file):
  - `sqlite3 ml/data-pipeline/data/corpus.sqlite ".backup data-backups/corpus-pre-overnight-20260816.sqlite"`
    → `integrity_check ok`, 6290 documents.
  - `cp -p ml/eval/data/ref_dense_v2.npz data-backups/ref_dense_v2-20260816.npz`;
    sha256 `9ad0c5a4…fddc18`: to be re-checked at the end to prove the dense index was untouched.
- Baseline test counts: **car 91 · ml/eval 116 · ml/curation 26** (car+eval from `car/.venv`, curation
  from `ml/curation/.venv`).

## T1: recalibrate.py made trustworthy, smoked, launched (06:31–06:37 UTC)

**Why first:** the judge track is the GPU long pole, and exploration found `recalibrate.py:119`
did `cfg = Config()`: pydantic defaults, so a full run would have measured Qwen3.8 under
**rubric r1 with a 1500-token budget** (3.6 was calibrated on r2 with a thinking budget). Any
number it produced would have been an invalid comparison; more likely it would have starved the
thinking model and produced no verdicts at all. Fixed to `load_config(--config)` (what `judge.cli`
does), plus per-doc atomic checkpointing/`--resume` (a multi-hour run must not lose everything
at doc 60), `--doc-ids`, and both bar sets recorded, commit `70d9da9`.

**Bars, honestly:** the DB carries the real pre-registration `meta['calibration-100:pass_bars']`
= 90/90/0 (2026-07-05, "pre-results"); 93.1/97.7/0 are what 3.6 *achieved* that day. The old file
(and the runbook, and the checklist) called the latter "pre-registered". Syed's ruling tonight:
3.8 becomes judge only if it clears the pre-registration AND matches-or-beats 3.6's like-for-like
recalibration on the same engine AND has zero dangerous cells.

Verification: `ml/curation` suite 26 → **33 green**. Live smoke `--limit 3` (docs 332/880/881 →
3/2/2, 27–83 s each, r2, 24576, served model recorded).

Launched (06:37): `nohup .venv/bin/python -m judge.recalibrate --model-tag qwen3.8-27b-q8_0
--resume --out ../eval/results/recal-qwen3.8-20260816.json` → PID **1579556**, log in the session
scratchpad `recal38.log`; a persistent Monitor watches for `FAILED|Traceback|LlmError|context`
and every 10th doc, and reports process exit. Doc 960 (330 kB, ~14 chunks) is 6th in order,
that is the ctx-32768 vs 24576-token budget risk; if it errors it stays retryable via `--resume`.

## Track A: MVEM baseline provenance + refusal guard (06:38–06:43 UTC, CPU, commit `58c8ec2`)

**Design decisions (explained so they can be reversed):**
- The estimator never imported `NOMINAL_MAF_IDLE`; the nominal reaches it only through
  `Observation.nominal_maf`. So provenance was attached *there*, `Observation.nominal_validated`,
  default **False** ("untrusted unless stated"). The sim harness and the test fixture set it True
  because inside the sim the seeded baseline is the truth by construction (synth_log builds
  `maf_gs` from it), which is exactly why E4 sees zero change.
- `mvem.MafBaseline` is the rpm-indexed lookup the three-hold capture will populate:
  `points=((rpm, g/s), …)`, `.at(rpm)` linear-interpolates and clamps (never extrapolates),
  `from_capture()` is the *only* validated constructor. `SIM_MAF_BASELINE` seeds 2.50@850 /
  5.00@1500, `validated=False`. `NOMINAL_MAF_IDLE` stays a scalar (= baseline at 850) for the
  eval consumers; `OperatingPoint.maf_gs` now derives from it (there was a second hard-coded 2.5).
- Guard semantics: when the baseline is unvalidated, the MAF-reading term is dropped from **every**
  hypothesis' residual (it was poisoning `healthy` too, `_sse` adds it whenever `nominal_maf` is
  set). Then, if the verdict would *still* rest on the MAF term (the ratio lands inside a
  `maf_low`/`maf_high` band, or the trims-only best is a MAF fault) → `identifiable=False` with a
  reason carrying the ratio, the band, the trims-only ranking and the pointer to
  `CAPTURE-PROTOCOL.md`. Ratio ≈ 1 with an unvalidated baseline still diagnoses from trims. A
  refusal is visible and blocks the write path via `clamp_diagnosis_agreement`; a down-weight
  would not be; that was the runbook's requirement.
- **Bluntness flag for Syed:** with the seeded baseline, *any* real log whose MAF ratio is outside
  0.999–1.001 will refuse (the bands are that tight). Until the capture populates a validated
  baseline the layer effectively says "no MAF verdicts on this car", which is what the checklist
  already said in prose. Reversible by widening a tolerance band around 1.0 if he prefers.

Verification: `car` suite **91 → 101** (10 new in `tests/test_maf_baseline.py`: real-log-shaped
values → refusal naming the baseline; same values validated → guard silent; seeded MAF faults
refused unvalidated / identified validated; default-untrusted; interpolate/clamp;
`from_capture`); `ml/eval/tests/test_e4.py` 18/18 (consumer of `NOMINAL_MAF_IDLE`).

## Track B: 3.6 doc-collapse (06:43–06:46 UTC, CPU, commit `5636759`)

Nothing to reuse existed (the 3.8 number had been computed ad hoc), so the counter is now a
committed module: `ml/eval/doc_collapse.py`: a `collections.Counter` over each row's
`retrieved_doc_ids` giving distinct docs, per-doc query coverage, distinct ordered id-tuples and k
(inferred from row length; July rows predate the `top_k`/`index_stale` provenance keys).
Run from `car/.venv` (the eval venv lacks numpy; this module is stdlib-only but the habit holds).

Result: the ratified 3.6 headline retrieved **exactly 3 documents on 100% of 147 queries**: the
same three 3.8 got. Arm A vs arm B for 3.6: 83.7 → 93.9 from a *constant* three-page preamble;
k=6 → 83.7; 3.8 moved 0.0. E2 does not collapse (325 distinct docs). Written up in
`ml/eval/results/DOC-COLLAPSE-2026-08-16.md`, a `decisions.md` FINDING entry (not a decision,
the query-representation / community-index design is Syed's), checklist B2 ticked.

## C2-fix: judge runner hardening (06:46–06:48 UTC, CPU, commit `7e0c5d5`)

Three things that would have made tonight's 314-doc judge run silently wrong or fragile:
- **F2 gone filter.** `State.pending_for_judge()` (`ml/data-pipeline/corpus_pipeline/core/state.py`)
  and `judge.cli --status` both filtered `gone_at IS NULL`. The ratified 2026-07-22 policy says
  gone-ness affects scraping only. 303/314 pending community docs are gone-marked, so
  `judge.cli --run --sources forum_…` would have judged **11** docs and declared victory. Filter
  removed in exactly those two places; every *other* `gone_at` use (scraper sweep, `calibrate.py`
  sampling, `pairgen`/`e2gen`) is untouched and listed for Syed as the same policy gap.
  `--status` now: `community/judged=327, community/pending=314`.
- **F5 `--no-reindex`.** `runner.run(reindex=False)` skips `retrieval.ensure_index()` and logs the
  stamped-vs-live delta (5638 vs 5649). Without it the next `--run` would have rebuilt `ref_fts`
  (+11 reference docs) and left `ref_dense_v2.npz` stale, an index change the runbook forbids
  tonight. Syed can do it deliberately in the morning: `judge.cli --reindex`.
- **F3 dead server.** On `LlmError` the runner now re-checks `/v1/models`; server gone → run
  **stops** (`RunStats.stopped`, exit 2), doc stays `pending`. Previously every remaining doc
  would be marked `failed` at ~35 s each. A per-doc `LlmError` with a live server still parks
  that doc `failed` (unchanged).
- Bonus: `cli.py` lacked `from pathlib import Path` (`--harvest --out` NameError).
Verification: `ml/curation` 33 → **37**; `ml/data-pipeline` 37/37.

## Track D: community index + per-parent cap, INERT (06:48–06:56 UTC, CPU, commit `806ce68`)

How it wires in (so it can be switched on deliberately later):
- **Config seam:** `ml/eval/harness/config.py RetrievalCfg` gained `community_fts`,
  `community_index_path`, `community_top_k` (0 = off) and `max_per_parent` (0 = off). Frozen
  dataclass with defaults → every existing `RetrievalCfg()` / `dataclasses.replace(...)` is
  unchanged. There is deliberately no CLI flag yet: turning it on is a config decision.
- **Query path:** `retrieve_with_meta` still does BM25 + dense (bge-m3) → RRF → top-k on
  `ref_fts` exactly as before (`_rrf()` and `_take_top()` are refactors that are byte-identical
  when the cap is 0). If community is enabled, the *same* rankers run against `community_fts`
  + `community_dense_v2.npz`, results are tagged `tier="community"` and **appended after** the
  reference top-k, so the reference rows never move. Absent table/index → `meta.community_fallback`
  says so; never raises. The query is embedded once and shared.
- **Provenance on the row:** `RefSnippet.tier` / `.parent` (parent = `source_id` before `#`,
  i.e. the book) come from the `document` table by rowid. This is what the citation guard / prompt
  builder can use to tell a forum post from a textbook, and what the cap keys on.
- **Per-parent cap (checklist B7 idea):** `max_per_parent=N` runs after fusion, before the slice;
  skipped rowids land in `meta.capped_out`. Both E2 leaks were 4–6 adjacent pages of one book.
- **Builders, never run tonight:** `judge/retrieval.ensure_community_index(state, min_score)`
  (mirror of `ensure_index`, own `(count, min_score)` meta stamp, gone docs INCLUDED per NARROW,
  copying the reference predicate would have indexed 17 of 641) and
  `harness/embed_index.build(table=, out=)` / `--table community_fts --out …` (out required for a
  non-reference table so the reference npz can never be overwritten). Estimated CPU cost for 641
  docs ≈ 25–30 min; no GPU needed.
- **To switch on (Syed):** (1) `ensure_community_index(state, 4)`; (2) `python -m harness.embed_index
  --table community_fts --out data/community_dense_v2.npz`; (3) set `community_fts="community_fts"`,
  `community_index_path=…`, `community_top_k=N` on the eval `RetrievalCfg`. Nothing else changes.

Verification: `ml/eval` **116 → 124** (+8; +1 heavy oracle test gated by `MLECU_HEAVY_TESTS=1`
that replays the 08-02 reverify file's `retrieved_doc_ids`); byte-identical test compares ids,
snippets *and* meta between a default cfg and one with every new field explicitly off, on a tiny
DB and on the real DB (bm25 mode, real E1v2 prompts); `ml/curation` 37 → **38**. At commit:
`ref_fts` = 5638, `community_fts` does not exist in the real DB, `ref_dense_v2.npz` sha unchanged.

## C4 (part 1): the 95 existing score-3 community docs (06:57–07:07 UTC, CPU, commit `33bb379`)

- Pulled all 95 (`SELECT … WHERE tier='community' AND judge_score=3`) with their per-chunk judge
  rationales into scratch files (1.31 M chars; doc 960 alone 330 kB). Wrote ONE fixed rubric
  (`ml/curation/docs/community-3s-review-RUBRIC.md`): the question is *retrieval usefulness for the
  project's current gaps*, judged on markers of verifiability, not correctness, with the explicit
  example that a two-line "smoke test found a torn boot, trims +12 → +2" post is a KEEP.
- 8 reviewer subagents (batches sized ~110–330 kB), JSONL output per doc, aggregated by a small
  script; I spot-checked 15 verdicts (16 %) against the source text; all held.
- Result: **28 keep / 67 drop**. Value for current gaps: 2 high, 25 medium (all keeps), 68 low.
  Needs-alignment census: `megasquirt_speeduino` 33 and `generic_other` 30 dominate; the gap topics
  are a minority (`vacuum_leak` 12, `injector_latency` 9, `smoke_test` few); **`maf_baseline` = 0**,
  no forum thread at score 3 supplies the healthy-idle MAF number the layer most needs.
- Wrote `ml/curation/docs/community-3s-review-2026-08-16.md` (+ raw JSONL). **STOPPED.** Nothing
  indexed. The C2 run's *new* 3s need the same pass later.

## B1: Qwen3.8 RUNDOWN (07:00–07:07 UTC, commit `33bb379`)

Recomputed every number from the jsonl. E4 15/15 (3.6: 13/15) and E2 48/19/2 confirmed. **E1v2
"7 dangerous" is 0 under the codified `dangerous_flips()`**, the six `vacuum_leak →
injector_latency_lean` misses are lean→lean; the handoff applied the "edit authorised on a no-edit
fault" reading that the codified rule reserves for `healthy`. This decides whether 3.8 clears the E1
bar and it is Syed's to rule on (§7). Also: one `finish_reason=length` row per E1v2 arm.

## T3: 3.8 gated, server swapped to 3.6 (new build), 3.6 recal launched (10:40–10:45 UTC)

- **3.8 recal finished 10:39:31** (started 06:37 → 4.0 h of GPU, 0 errors, n=100, checkpointed
  throughout): exact 69.0 · within±1 **98.0** · Spearman 0.564 · keep/drop **91.0** · **dangerous 1**
  (doc 1081 "Dyno sheets", subaruforester, truth 2 → judged 4). Against the pre-registered 90/90/0:
  PASS/PASS/**FAIL** → **FAIL**. Against 3.6's July numbers: 91.0 < 93.1 as well. Judge stays 3.6,
  decided without needing the like-for-like. Aside: 3.8 under-scores adjudicated 4s (960/1031/1088/
  5773 → 3, 1127 → 2), and so does 3.6, identically (see T3 close-out); three of those are C4 keeps.
- Killed the 3.8 server by PID (1446703); VRAM 0/0. Started `/tmp/start_q36_newbuild.sh` (same
  flags as the 3.8 script, GGUF swapped; llama.cpp Aug-14 build; ctx 32768; split 3.5,1; draft-mtp).
  Note: my error-grep tripped on the benign `W common_fit_params: … n_gpu_layers already set` line,
  it is a warning, not a failure. Loaded in ~1 min, 22.8 GB + 7.9 GB, same as 3.8.
- Smoke `--limit 3` on 3.6: 43/44/41 s per doc, scores 3/2/2 (3.8 gave 3/2/2 for the same three).
- Launched full 3.6 recal (PID in scratchpad `recal36.pid`, log `recal36.log`, out
  `ml/eval/results/recal-qwen3.6-newengine-20260816.json`, `--resume`), Monitor armed. **Why before
  C2:** C2 writes 314 verdicts with *this* judge on *this* engine; if 3.6-on-new-engine also shows a
  dangerous cell, C2 should run on the certified July build instead. Syed's choice was to recalibrate
  3.6 too; sequencing it first is the honest order even though it pushes C2 later.


## T3 close-out + T4 launch (13:19–13:21 UTC)

- **3.6 like-for-like on the new engine finished 13:18** (2.55 h, 0 errors, n=100): exact 70.0 ·
  within±1 98.0 · Spearman 0.583 · keep/drop **90.0** · dangerous **0** → PASS pre-registered (by zero
  margin), below its July 93.1. Head-to-head vs 3.8: 90.0/98.0/0 vs 91.0/98.0/1. Judges disagree on
  28/100 (3.8 higher on 21). Both recall the same 4 of 9 adjudicated 4s.
- **Judge for C2 = 3.6 on the Aug-14 build** (passes the hard bar; config tag `qwen3.6-27b-q8_0` ==
  served `Qwen3.6-27B-Q8_0.gguf`; engine change disclosed, D18).
- Backup before the first write: `sqlite3 … ".backup data-backups/corpus-pre-c2-20260816-1320.sqlite"`
  (integrity ok, 6290 docs, ref_fts 5638). `--status` before: community/pending = 314.
- Launched 13:20: `judge.cli --run --no-reindex --sources forum_romraider,forum_legacygt,forum_msextra,
  forum_subaruforester` (python PID 2353503, found via `ps`, NOT `pgrep -f`, which earlier matched my
  own wrapper shell and briefly made the 3.6 recal look dead). Log `c2.log` in scratchpad; Monitor
  reports failures/STOP and every 20 docs. First log lines confirm: server up, *reindex SKIPPED
  (5638 vs 5649)*.

## C2 close-out, part-2 review, wrap-up (19:40–20:xx UTC, commit `b1ec161` + final)

- C2 finished 19:40: 314 judged, 0 failed, 391 chunks → 206/93/15. `judge.yield_report` (new, read-only)
  is the reproducible view. llama-server killed by PID 19:43 (Syed's ruling); GPUs 0 MiB.
- **Part-2 review**: exported the 93 new 3s + all 34 fours (127 docs, 1.0 M chars) with rationales,
  10 batches, same rubric. Syed asked mid-run which model the reviewers use, verified from the subagent
  transcripts (`"model":"claude-fable-5"` in every one, both rounds); batches 7–9 (and the relaunched
  1–6, which the interrupt had killed) were re-launched with `model: fable` pinned explicitly.
  Spot-checked 20/127 incl. every score-4 "drop" I could reach: those are mostly NEED-FIT verdicts on
  rubric-correct 4s (MegaSquirt threads), not judge errors, the aggregation labels them so and marks the
  6 genuine arc-missing cases ✱. Result 46 keep / 81 drop; 16 high-value keeps.
- Final integrity: `ref_fts` 5638, no `community_fts`, npz sha unchanged; suites car 101 / eval 124+1 /
  curation 38 / data-pipeline 37 all green. Commits, no push.
