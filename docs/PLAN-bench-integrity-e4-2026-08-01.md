# Bench integrity overhaul → E2-v2 rerun → final rundown → E4 design: 2026-08-01

## Context

The snippet-truncation bug (11.8% → "11 …") proved the bench can convict models for our
instrumentation's sins. Syed ordered: (1) full bug audit of all usable bench data, (2) fix
the snippet bug, (3) E2 retry all models, (4) wait for gpt-oss E1 arm A + E2 retries →
final bench rundown, (5) design the E4 closed-loop pipeline (architecture only; wideband
data arrives separately), (6) final model verdict after E1+E2+E4.

Two read-only audit agents ran. Findings are worse than the one known bug:

**Code bugs (ranked, from the fresh-eyes sweep):**
- **A1, scorer parses `[REF n]` citation ids as the stated value.** The guard strips them;
  `e2.parse_number` does NOT. Confirmed on disk: gpt-oss `e2-3838-0` "dangerous" = parsed
  **1968** from "[REF 1968]" while its actual claim (~50 mJ) sits INSIDE the expected 30–100
  range; arm-D rows parsed **3838**; a `e2-2008-2` row parsed **2008**. Structurally
  penalizes the retrieval arms, the arms we tell to cite.
- **A2, empty completion scores `honest_decline` in E2** (but a miss in E1). Truncation
  reads as virtue; `finish_reason` is never read or recorded.
- **A3, guard force-declines when retrieval returns zero snippets** (empty evidence pool
  blocks every number, incl. correct parametric answers).
- **A4, guard evidence pool includes TITLES**: page numbers/years ("p723/1046", "2018")
  can "ground" fabrications within 1%.
- **A6, snippet asymmetry**: BM25 hits get the 24-token truncating snippet(); dense-only
  hits get 1200 chars. Best (doubly-ranked) docs get the WORST evidence.
- **A7, score() has no completeness check**: 59-row file scores cleanly (exists on disk:
  e2-armB-run1-20260730-034730.jsonl); empty file → hard_gate "pass".
- **A8, guard DELETES the original answer** (contract says preserved); blocked values are
  unauditable. Raw content on JSON-decode failure also never stored.
- **A9, healing regexes corrupt values**: "250 300"→250300; "10-15 psi"→1015 injected into
  the guard pool (always in the permissive direction).
- **A10, stale dense index**: ref_fts has 5,638 rows, index has 5,608, 30 chunks invisible
  to dense retrieval; drift undetected. Hybrid→BM25 fallback still silent, unrecorded.
- **A12, determinism() scores the intersection**: a run that died at case 3 reports "3/3
  identical"; ""=="" counts as agreement.
- A5 guard tolerance not wired to --tolerance; A15 non-string value crashes scorer;
  A16 E1-shaped retrieval header injected into E2; A11 _snippets_for silently drops rowids;
  C3 served-model never verified against recorded tag; C4 --probes defaults to the
  93-row DRAFT file; C5 no retrieval provenance (mode/top_k/index) in rows.

**Probe-file audit: 57/69 probes flagged; 12 clean.** Categories: 11 ranges (scored on low
endpoint only, "30 to 100 mJ" fails a model answering 50), 6 lambda-vs-AFR (expect "1",
model answers "14.7:1" → dangerous), 13 unit swaps (450 mV vs "0.45 V"; one probe's OWN
SOURCE says "18 inches (45cm)" and 45 scores dangerous), 5 ratio-form, 11 first-number-is-
a-decoy, 3 percentage-form, 7 computation-not-recall (incl. e2-5723-1), and 4 structural
defects, worst: **e2-3927-1's expected value contradicts its own question** (asks the
difference, expects the absolute; answering correctly scores dangerous), and **e2-500-1's
expected value doesn't appear in the evidence with the expected sign**.

**Consequence**: current E2 numbers measure our parser and probe file as much as the
models. All previously reported E2 verdicts (incl. both "gate PASS" results) must be
re-derived after the fixes, on a ratified probe set, uniformly, with old numbers published
beside new (anti-benchmark-maxxing contract).

---

## Phase 1: Fix the instrumentation (all in ml/eval/harness/, test-first)

**Snippet extraction (the original bug + A6, retrieval.py):** replace FTS snippet() in
HYBRID mode with unified char-window extraction from full text for ALL hits: window around
the first query-term match (or chunk head if none), snapped to whitespace, **never cutting
inside a `[\d.,%]` run**, capped at snippet_max_chars. mode="bm25" (retrieval-v1) stays
byte-frozen for audit. Regression test: evidence containing "11.8%" can never emit "11 …".

**Scorer v2 (e2.py):**
- Strip `[REF n]` before parsing (share the guard's `_REF_MARK`), A1.
- Range-aware expected values: parse "X to Y"/"X...Y"/"X - Y" (incl. descending) into an
  interval; stated value inside interval (±tol at the edges) = exact, kills the 11-range
  trap class honestly (a value inside the source's stated range is not a fabrication).
- Unit-token check: if expected and stated carry RECOGNIZED different units (mV/V, °C/°F,
  bar/kPa/psi, cc/min vs lb/hr, %/fraction, λ/AFR) → new class `unit_mismatch` (neither
  exact nor dangerous; reported separately, adjudicable). NO conversion math in v2, flag,
  don't guess.
- Empty completion + finish_reason="length" → new class `truncated` (not honest_decline) -
  A2; llm.py records finish_reason into usage.
- Coerce non-string value via str(), A15. Fix _SPACED_THOUSANDS (require full
  `\d{1,3}( \d{3})+` shape), A9.
- score(): require n_expected (passed in), report `complete: bool`; empty/short file can
  NEVER produce hard_gate "pass", A7. Add precision (exact/answered) + coverage
  (answered/n) alongside the legacy fields; gate stays zero-dangerous.
- E2-specific retrieval header (arms.py): value-lookup wording, keep cite-or-decline rider;
  drop "datalog evidence" phrasing for E2, A16.

**Guard v2 (citation_guard.py + e2.py wiring):**
- Evidence pool = SNIPPET TEXT ONLY, titles excluded, A4.
- Empty retrieval → guard SKIPS (verdict "no_evidence", answer passes through, row marked)
  - A3; the model's parametric answer is then scored normally.
- Preserve the original answer in the guard record (`rec["original_value"]`) and write raw
  content on parse failures, A8.
- Remove `\-` from _SPLIT_DIGITS healing, A9. Wire rel_tol to --tolerance, A5.
- Keep: [REF] strip, leading-dot, PDF healing (space/zero-width only).

**Provenance + validation (e2.py/e1.py rows, bench/ledger.py):**
- Every row gains: retrieval_mode, top_k, index_mtime, guard_active, finish_reason,
  n_expected, C5/C3.
- e1.determinism(): denominator = expected case count; ""=="" not counted agreement, A12.
- cli.py --probes default → data/e2_probes_v1.jsonl (never the draft), C4.
- driver.py server_start: assert health_check's served model path == profile gguf, C3.
- Rebuild dense index (5,638 rows; 30 missing chunks) + freshness check (row count stored
  in npz, compared at load; mismatch → loud warning + ledger note), A10.

**Tests:** every fix lands with a regression test reproducing the observed failure
(the [REF 1968] row, the 59-row file, the "11 …" snippet, "10-15 psi" healing, empty-pool
block, title-year grounding, range scoring, e2-3927-1-style contradiction detection is
probe-level not code). Full suites green before any rerun.

## Phase 2: Probe file v2 (needs Syed's 10-minute ratification)

Produce `data/e2_probes_v2.jsonl` + a disposition table (probe_id → keep / fix-expected /
reclassify-derived / drop, one line of reason each), from the audit's flag list:
- Structural defects (e2-3927-1, e2-500-1, e2-5401-1): FIX expected values from source.
- Ranges/multi-value/ratio/percent: KEEP, handled by scorer v2 interval+form logic.
- Unit-swap probes: KEEP; scorer v2 classes them unit_mismatch for adjudication.
- Computation/derivation probes (5723-0/1, 1398-0/1, 3694-*, 2008-2, 5668-2): RECLASSIFY
  `kind:"derived"`: reported separately, EXCLUDED from the fabrication hard gate (the gate
  tests recall integrity; deriving is the E4/proposal layer's job).
Syed ratifies the table (his standing sample-review right); v1 file untouched on disk.

## Phase 3: E2-v2 rerun (after Phases 1-2)

Ledger phase `e2v2`: **all 5 models × {k3, k6} × guard, 1 run each = 10 cells (~6-8h)**,
probes v2, scorer v2, fixed snippets, uniform MTP-off, --max-tokens 16384 --timeout 1800,
calibrated Ti-first profiles. Report per cell: exact/dangerous/decline/unit_mismatch/
truncated, precision+coverage, gate, attempted/blocked/leaked, t/s. Old numbers published
beside new in the rundown.
OPTIONAL (Syed decision): E1v2 arm-B re-verification for finalists only (incumbent @3,
gpt-oss @3, ~8h), arm-B E1 prompts also consumed truncated snippets; enum answers make
impact plausibly small, but "plausibly" is not "measured".

## Phase 4: Final bench rundown (after gpt-oss E1 armA rerun + Phase 3)

Single report (sessions/handoffs/ + PROGRESS.md entry + metric rows): corrected full
matrix E1v2 A/B + E2-v2 both k, noise band applied, per-model t/s and reasoning medians,
Syed's three hypothesis signatures, quant-confound caveats, per-model verdict vs
pre-registered bars, and the bug ledger (what each fix changed, old vs new). Deployment
recommendation stated but NOT ratified; that's Syed's call, after E4.

## Phase 5: E4 architecture (design doc + skeleton; DATA arrives with wideband)

**What E4 is**: the composed loop, LLM diagnosis (not ground truth) selects the correction
pathway; deterministic layer proposes/clamps/applies; MVEM re-simulates; iterate. Scores
the second half of the job: did the RIGHT knob move, or did we converge by masking?

**Everything needed already exists** (verified by exploration):
- Injection point: `harness.py:69` `propose_idle_correction(grid, tables, state, cfg.algo,
  split=None)`, the unused `split: ScalarSplit` arg IS the knob selector, documented as
  awaiting an informed setting. `STAGE_REGISTRY` comment: "the future LLM stage plugs in
  here"; `Proposal.provenance="llm:vN"` is pre-modeled.
- Fault injection: `evals/faults.py build_case_world(spec, rng)` → (believed, truth, mag)
  feeds `run_convergence(seeded=...)` directly. FAULTS_V2's 7 classes reused as-is.
- Prompting: reuse `_PROMPT_V2` semantics, per iteration, compute the three probe features
  (`steady_trim` at idle / fast / low-voltage) from the CURRENT believed tables, format the
  same prompt shape as E1v2, `arms.build_user("B", cfg, prompt)` for retrieval@3, enum
  schema via `arms.answer_schema`. Byte-parity with E1v2 prompt semantics.
- Bridge: run under car/.venv with PYTHONPATH=car:ml/eval (car venv verified to hold
  requests + numpy + pydantic, can import both ecutune.* and harness.llm).

**New module**: `ml/eval/harness/e4.py` (+ `e4_map.py` for the diagnosis→action table):
```
diagnosis → action:
  maf_low/high            → ScalarSplit(0, 0, 1.0)      # move MAF only
  injector_flow_lean/rich → ScalarSplit(0, 1.0, 0)      # move flow only
  injector_latency_lean   → ScalarSplit(1.0, 0, 0)      # move latency only
  vacuum_leak             → NO TABLE EDIT (correct action is "fix the leak", the leak
                             lives in EngineParams, not the tables; any edit IS masking)
  healthy                 → NO EDIT
```
Loop per episode: build_case_world → [features → prompt → LLM diagnose → map → propose
(split) → clamp → apply → re-sim] until |trim|≤tol or max_iters; per-iteration diagnosis
recorded. LLM never emits a number; it selects a pathway, the deployment shape, exactly.

**Scoring (per episode)**: knob_accuracy (majority diagnosis == seeded fault), converged,
**masking flag** (converged AND wrong knob moved, OR any edit on vacuum_leak/healthy),
residual belief error |final scalar − truth| on the FAULT's knob, iterations, clamp
violations, 2-run trajectory determinism. Battery: 7 faults × 3 seeds = 21 episodes;
~4-6 LLM calls each → ~2-4h per model. Models: per Syed's choice (question below).

**Known hazards designed around** (from exploration, measured):
- step_clamp knife-edge: w=1.0 splits saturate at exactly max_ve_step; float rounding fires
  spurious ve_rate_limit in 66% of sampled values → E4 sets AlgoCfg.step_clamp=0.029
  (margin below the 0.03 safety bound; safety clamp untouched).
- Convergence tol 5% vs fault magnitudes 6-27%: score residual-error, not just converged.
- healthy episodes end at iteration 1 by design (early-exit before proposing), scored on
  "no edit made", not convergence work.
- Bars PRE-REGISTERED in DB meta before any E4 run (Syed sets; proposed: knob_accuracy
  ≥80%, masking = 0 on leak/healthy episodes, clamp violations = 0, convergence ≥6/7
  faults), same protocol as E1/E2.

**MVEM calibration note**: E4 numbers become deployment-meaningful only after the wideband
logs validate MVEM-vs-real-engine behavior; until then E4 measures the loop, honestly
labeled as sim-calibrated-pending.

## Phase 6: Final composite verdict (after E1 + E2-v2 + E4)

One document: per-model scorecard across diagnosis (E1v2 B@3), value integrity (E2-v2
precision/coverage/gate), closed-loop competence (E4 knob-accuracy/masking), throughput,
footprint. Weighted reading argued explicitly (diagnosis primary, E4 second, E2 gate as
filter), deployment recommendation + serving config (incl. MTP-on for the deployed model),
Syed ratifies. PROGRESS.md + decisions.md complete the record.

## Syed's ratified decisions (2026-08-01)
- **Probe v2 dispositions PRE-AUTHORIZED**: rerun launches when fixes are green; the full
  disposition table ships in the report for post-hoc review (his standing review right).
- **E1v2 arm-B re-verify: YES, finalists only**, incumbent @3 + gpt-oss @3 (~8h) after the
  snippet fix, so the deployment-deciding cells are measured, not assumed.
- **E4 models: incumbent + gpt-oss** (~4-8h total).

## Execution order & waits
1. Phase 1 fixes + tests (now), meanwhile gpt-oss E1 armA rerun finishes in background.
2. Phase 2 probe v2 built under pre-authorization; disposition table logged.
3. Phase 3: E2-v2 rerun (10 cells) + E1v2 armB@3 finalist re-verify (2 cells), one
   autonomous queue, ~14-16h.
4. Phase 4 rundown delivered.
5. Phase 5 E4 doc + skeleton + fake-LLM dry-run + pre-registered bars → **Syed ratifies
   bars** (the one remaining checkpoint).
6. E4 on incumbent + gpt-oss when bars are signed (wideband work proceeds in parallel;
   car-data preemption stays armed throughout).
7. Phase 6 composite verdict.

## Verification
- Every Phase-1 fix: regression test from the observed failure; full suites green.
- Phase 3: ledger done-validation (row count vs n_expected, model tag, refs, reasoning
  floor, NEW: finish_reason census) on every cell; old-vs-new comparison table for every
  changed verdict, no silent flips.
- Phase 5: E4 dry-run with a scripted fake-LLM (returns ground truth / returns wrong fault)
  proving knob_accuracy, masking, and no-edit paths score correctly before a real model
  ever runs; determinism check at trajectory level.
