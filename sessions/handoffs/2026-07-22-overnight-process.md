# 2026-07-22 Overnight — the ENTIRE process, decision by decision

**Written for Syed's morning read, per directive: not "it's done" but HOW, WHY, and with
what commands.** Plan of record: `~/.claude/plans/snug-shimmying-spring.md` (approved
before sleep). Runtime events append to `ml/finetuning/logs/overnight-20260722.log`; this
doc explains everything that log refers to. Results land in `ml/eval/results/` as usual.

---

## 0. What was already true when the night began

v3 signed → 280 pairs → structural gate (your blank-field catch) → **242 train / 28 val**
chat transcripts in `ml/finetuning/data/`. BF16 checkpoint verified == judge GGUF source,
52G on disk. Training stack installed in `car/.venv`. Judge service stopped, both GPUs
idle. Your ratifications: top_k 6 primary + exhaust the sweep matrix; keep `-c 16384`
(inert allocation can't change scores); no KV-cache quantization anywhere; embeddings
before showdown.

## 1. The embedding pipeline (retrieval-v2) — what was actually done

**Why**: BM25 matches words; E2 proved its ceiling (34.8% match, 5 fabrications where the
RIGHT doc was found but the wrong number lifted). An embedding model maps whole passages to
1024-dim vectors where same-meaning ⇒ nearby, so retrieval becomes geometry (cosine
similarity = normalized dot product), immune to vocabulary mismatch.

**Model choice** (re-verified live, not from memory): **BAAI/bge-m3** — MIT license, 568M
params, the 2026 production default per current practitioner guides. Runs on **CPU** —
zero VRAM taken from anything, ~2.3GB one-time download (no sudo: plain user-level HF pull,
same mechanics as your 52GB one).

**Commands that ran** (all detached with `setsid nohup`, logs in `ml/finetuning/logs/`):
```
car/.venv/bin/hf download BAAI/bge-m3                       # to the HF cache
# then, automatically once that finished:
cd ml/eval && car/.venv/bin/python -m harness.embed_index    # ~15-25 min on CPU
```
`embed_index.py` (new file, fully commented): reads all 5,608 `ref_fts` rows — the SAME
text units BM25 ranks, so both rankers vote on identical candidates — encodes
`title\ntext`, L2-normalizes, stores `ml/eval/data/ref_dense_v1.npz` (~23MB: one float32
[5608×1024] matrix + rowids).

**Query-time wiring** (`ml/eval/harness/retrieval.py` — your `query_terms` untouched):
`retrieve()` now has two modes. `mode="bm25"` is retrieval-v1 byte-for-byte (kept forever
for audit). `mode="hybrid"` (the new default): BM25 top-20 + dense top-20, fused by
**Reciprocal Rank Fusion** — each doc scores Σ 1/(60+rank) across the two lists. RRF has
no tuned weights (nothing to overfit), rewards docs both rankers like, and lets either
ranker alone surface what the other missed. Top-k of the fused list emerges as the same
`RefSnippet` objects arm B always consumed — the seam you built held, which is the whole
point of seams. Dense-only hits get the chunk head as their snippet (FTS `snippet()`
requires a keyword MATCH; a semantic hit may have none). If the index file is missing,
hybrid silently degrades to pure BM25 and the chain logs a warning.

**Cite-or-decline** (P2's second half, data-mirror of the safety doctrine): the retrieval
block HEADER now ends: *"If asked for a specific calibration value, state it only if an
excerpt contains it (cite its [REF id]); otherwise decline rather than estimate."* It
rides inside the injected block — NOT in SYSTEM — so the arm protocol's "everything
identical except the injected block" stays exactly true. E2's answer grammar already has
the decline channel (`must_retrieve`/null): the rider tells the model to use it.

## 2. Arms C and D — 10 honest lines

`arms.build_user`: C behaves as A (case verbatim), D behaves as B (retrieval block). The
fine-tune is a SERVER-side variable — C/D talk to an adapter-loaded llama-server, A/B to
base — so the arm letter exists purely for honest labeling in results files/rows. CLI
gained `--top-k`, `--retrieval-mode`, `--model-name` (sweep provenance goes in the model
tag, e.g. `qwen3.6-27b-q8+qlora-v1|e1k3-e2k6`), and E2 got `--runs` parity with E1.
Tests: 25 eval + 11 finetuning, all green pre-launch; v1 retrieval pinned under
`mode="bm25"`; RRF fusion math unit-tested; "E" is still an unknown arm.

## 3. QLoRA training — every choice in `ml/finetuning/train.py`

- **NF4 4-bit frozen base** (~15-16GB of the Ti's 24): the only precision at which a 27B
  fits ONE card with training overhead. Not the product — scaffolding (serving re-quants).
- **`CUDA_VISIBLE_DEVICES=0`** + an assert that exactly 1 GPU is visible: the convicted
  3090 is physically invisible to the training process. Training load sits above its
  152-230W failure bracket; its crash kills the whole box; single-card was ratified.
- **LoRA r=16, α=32, dropout 0.05** on q/k/v/o/gate/up/down projections — every attention
  and MLP matrix gets the detect-16-patterns/apply-16-corrections bypass you were taught.
- **242 examples × 3 epochs ÷ (batch 1 × grad-accum 8) ≈ 90 optimizer steps**, lr 2e-4
  cosine with 10% warmup, paged 8-bit Adam (the optimizer's two per-weight running
  averages, quantized, pageable — the memory bill shrinks again).
- **Gradient checkpointing**: don't store forward activations; recompute them during the
  backward pass. ~30% slower, massively lighter — the trade that makes 27B-on-24GB real.
- **The 28-pair holdout drives early stopping**: eval each epoch, keep the checkpoint with
  best val loss (`load_best_model_at_end`). With 27B params vs 242 examples, memorization
  is expected — the question is when, and the val curve answers it. Full loss history
  saved to `runs/qlora-v1/train_summary.json` for your morning read.
- **assistant_only_loss**: loss masked to the assistant turns if this trl build supports it
  (the reply is the lesson, not the question); the log states which branch ran.
- **`--smoke` gate**: 2 optimizer steps + exit. The chain refuses to start the real run
  (or anything downstream) if the smoke fails — no 3am surprises on the first-ever 27B
  load through transformers on this box.

## 4. Serving the fine-tune (arms C/D)

```
pip install gguf                                             # converter dependency
convert_lora_to_gguf.py runs/qlora-v1/adapter --base <BF16> --outfile adapter.gguf --outtype f16
llama-server -m Qwen3.6-27B-Q8_0.gguf --lora adapter.gguf \
  -ngl 999 --split-mode layer --tensor-split 3.5,1 -c 16384 -np 1 --jinja  # port 8080
```
Same binary, same certified flags as the judge service (3.5:1 split keeps the 3090 in its
8-day-proven inference envelope), with two deltas, both logged: `--lora` applies the
adapter as separate matmuls over the Q8 base (measurement-grade; the production path —
merge into BF16, requant fresh Q8 — wants the 224GB RAM kit and is queued); and **no
`--spec-type draft-mtp`** for the adapter server ONLY (untested lora+MTP interaction;
MTP is speed-only and output-invariant, so dropping it cannot move a score). The base
server for B-v2 keeps MTP exactly as certified. No sudo: servers run as your user with the
service file's flags; systemd wasn't needed.

## 5. The chain (`ml/finetuning/overnight-chain.sh`) — order and reasoning

0. **Train** (smoke → full) on the Ti. Embedding index builds on CPU in parallel.
1. **Adapter → GGUF.**
2. **Arm C battery** (fine-tune, no retrieval) — E1v2 first (your ratified bar), then E2
   (hard gate), then E1v1. 2 runs each, per protocol.
3. **Arm D battery** @6 (fine-tune + hybrid) — 2 runs. Then **D sweeps** (E1@3/E2@6,
   then 3-all) at 1 run each — justified deviation: temp-0 determinism has been
   byte-identical in every measurement to date (588/588, twice); flagged for your review.
4. **Base server** → **arm B-v2 battery** @6 (2 runs) → B-v2 sweeps (1 run each).
5. **Judge batch**: 333 pending docs incl. re-queued 5781, on the same base server (it IS
   the certified judge config). Routine continuous ops, lowest priority, so it runs last.
6. Every stage appends to the log; a failure aborts dependents only (bad training can't
   stop B-v2; a bad server can't corrupt results — rows flush per-case, crash-safe).

**Priority logic**: C lands first because "did fine-tuning work" is the gate question;
D@6 second because fine-tune+RAG is the architecture bet; B-v2 third isolates the
embeddings effect; sweeps fill the matrix; judging is interruptible any time.

**Usage-limit resilience** (your question): the chain is one detached process tree owned
by the OS, not by me. If my usage window closes, everything above keeps running and
writing; I resume monitoring and write the final comparison the moment I'm back.

## 6. What the morning report will contain

Per-cell scores for A (recorded), B-v1 (recorded), B-v2@{6, 3/6, 3}, C, D@{6, 3/6, 3} on
E1v1 / E1v2 / E2 — against the pre-registered bars (E1v2: 90% top-1 + zero dangerous
misses; E2: any confident-wrong value = arm fails; E1v1: 85.7 rules reference). Plus
training curves, the gated-pairs list, judge batch outcome, and every deviation flagged.

## 7. Runtime appendix

See `ml/finetuning/logs/overnight-20260722.log` (chain events + eval summaries),
`server-20260722.log` (llama-server), `embed-index.log`, `runs/qlora-v1/train_summary.json`
(loss curves). All result JSONLs: `ml/eval/results/` with per-row model tags.

---

## 8. RUNTIME POSTMORTEM #1 (04:03-04:08) — two failures, both caught by the safety nets

**Smoke OOM (the gate worked).** First training step died in trl's loss computation: it
upcasts the hidden states and the 151K-vocab logits matmul to float32, asking for 2.37GiB
with 1.61 free. Root cause: my max_length=1024 was a guess. Fix: MEASURED the dataset with
the real tokenizer — longest transcript is 484 tokens — set max_length=512 (covers 100%,
halves the loss-step memory) + PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
(defragmentation). Lesson recorded: derive sequence length from data, never assume.

**The self-match bug, again (embarrassing, documented).** The embed-index watcher polled
`pgrep -f "hf download BAAI/bge-m3"` — a pattern its OWN command line contained. It waited
on itself forever; the download had long finished. This exact gotcha is in the 07-08
handoff with the bracket-trick fix; I reproduced it anyway, and then reproduced it AGAIN
one minute later when the cleanup pkill matched its own shell (exit 144). Both now fixed
with bracket patterns. Consequence: the first chain started the B-v2 battery with no dense
index — hybrid silently fell back to BM25, i.e. a MISLABELED cell. ~15 min of arm-B rows
quarantined in results/aborted-20260723/ (README inside; never score them).

**Chain hardening from the incident**: retrieval batteries now REFUSE to run
hybrid-labeled without the index file (hard abort, no silent fallback) — both stage 3 and
stage 4. Chain relaunched 04:08 as attempt 2; attempt-1 log kept as
overnight-20260722-attempt1.log.

## 9. RUNTIME POSTMORTEM #2 (04:10-04:12) — same OOM, real root cause, attempt 3

max_length=512 changed nothing: the failing allocation was the SAME 2.37GiB — which proved
it sequence-independent. Read trl's source: its default `chunked_nll` loss upcasts the
ENTIRE lm_head weight matrix to fp32 on every 256-token chunk (`w.float()`: 124k vocab x
5120 x 4B = 2.37GiB) — designed for GPUs with slack we don't have. Fix: `loss_type="nll"`
(trl's own documented alternative) — LM head stays bf16, only the logits (~250MB at our
lengths) upcast inside cross-entropy. Diagnosis method worth keeping: when an OOM number
doesn't move after you shrink the data, the allocation isn't data-shaped — go read the
library source. Chain attempt 3 launched 04:12; embed index build untouched and running.

## 10. RUNTIME POSTMORTEM #3 (04:51-04:53) — eval-pass OOM; attempt 4

Attempt 3's smoke PASSED (loss_type=nll was right) and training ran 35 min — then OOM'd at
the EPOCH-1 VALIDATION pass: eval batch size defaults to 8 (vs training's 1) and the eval
loop accumulates logits on-GPU. Fix: per_device_eval_batch_size=1 + prediction_loss_only
(we need only eval_loss for early stopping). Meta-lesson now visible across all three
failures: ONE memory budget, three different spenders (loss upcast, eval batching,
allocator fragmentation) — each hides until the previous one is fixed. Also: the self-match
kill bug bit a THIRD time (a pkill sharing a command line with the relaunch that names the
same script); rule hardened — kills get their own command, always. Embedder confirmed
healthy mid-crunch (2238% CPU, silent only because I disabled its progress bar —
observability mistake, noted). Attempt 4 launched 04:53.

## 11. TRAINING COMPLETE (06:32) — the holdout did its job

Attempt 4 ran clean: 91 min, 90 optimizer steps, train loss 2.06 -> 1.34. The 28-pair
holdout curve: eval_loss 1.772 (epoch 1) -> 1.824 (2) -> 1.927 (3) — **memorization began
immediately after epoch 1**, exactly the failure mode the holdout was built to catch, and
`load_best_model_at_end` silently saved the epoch-1 checkpoint as the adapter. What we
serve/measure is that best checkpoint (runs/qlora-v1/checkpoint-31 -> adapter, 153MB GGUF).
Embed index landed 06:19 (5608x1024, 2.2h on CPU — my 15-25min estimate was 5x optimistic;
noted). Hybrid sanity PASS: paraphrase query "additive fuel correction rising at closed
throttle" — BM25 returns only keyword-matched ECUFlash defs; hybrid surfaces
"Acceleration Compensation" (semantic hit, no shared keywords) at rank 2. Arm C battery
started 06:33 on the adapter server (healthy in 70s).

## 12. ARM C VERDICT (battery 06:33-15:53) — the pilot fine-tune fails the bars, informatively

**E1v2: 83.7% top-1 (123/147, both runs byte-identical) — equal to base arm A, and FAILS
the ratified bar twice over**: below 90%, and TWO dangerous misses (cross-family flips:
injector_flow_rich answered maf_low / injector_flow_lean — rich truth, lean answer). First
dangerous misses of any arm. **E1v1: 74.3% vs A's 84.3** (−10, incl. one vacuum_leak ->
healthy). **E2: hard-gate FAIL and the headline finding — honest declines collapsed 
(8/69) while dangerous fabrications hit 45/69 (65%)** vs base ~15%; exact matches rose only
14.5%->21.7%. Interpretation: 280 pairs taught the REGISTER (confident, numeric,
domain-voiced answers) without the underlying values — integrity regressed exactly where
the safety doctrine cares most. This is the pre-registration working: an unbarred demo
would have called C "more knowledgeable-sounding" and shipped it. Open question now at arm
D: does retrieval + the cite-or-decline rider discipline the fine-tune's new
overconfidence? D battery started 15:53.

## 13. ARM D VERDICT (15:53-~11:20 next day, incl. sweeps) — grounding disciplines the fine-tune

**E2 @6 (the headline): exact 29/69 = 42.0% — best any arm has scored — and dangerous
fabrications cut 45 -> 15 (65% -> 21.7%) vs arm C, declines restored (8 -> 24).** The
cite-or-decline rider + hybrid retrieval reclaimed most of the integrity the fine-tune
destroyed, while the fine-tune's domain fluency pushed exact-match past B-v1's 34.8%
ceiling. Still a hard-gate FAIL (15 confident wrong values > 0) — the gate remains
unpassed by every arm, and that is the honest state of the system.

**E1v2 @6: 78.2%, ZERO dangerous misses** (both runs identical). Retrieval remains a
DISTRACTION on self-contained diagnosis (78.2 < C's 83.7) — consistent with the E1v1
doctrine — but it eliminated C's two cross-family flips entirely. Sweeps: E1@3 74.1 /
k3-all 76.2 on v2; E2 k3-all traded 4 exact for 3 fewer dangerous + 8 more declines
(top_k 6 vs 3 is a real precision/recall dial on the integrity axis; full table for the
writeup). E1v1 @6: 70.0.

Emerging cross-arm picture: fine-tune alone = overconfidence without knowledge (C);
retrieval alone = knowledge access without integrity guarantees (B-v1); TOGETHER they are
complementary — D is simultaneously the most accurate on values AND the most disciplined
fine-tune configuration. The bet behind arm D held qualitatively; the hard gate says it
has not yet earned deployment. B-v2 battery running now — it isolates how much of D's E2
gain is retrieval-v2 alone.

## 14. CHAIN COMPLETE (07-25 00:14) — the full nine-cell table

E1v2 (bar: >=90% top-1 AND zero dangerous misses) / E2 (gate: zero confident-wrong values):

| cell                        | E1v2 top1 | E1v2 dang | E2 exact | E2 dang | E2 decline | E1v1 |
|-----------------------------|-----------|-----------|----------|---------|------------|------|
| A base (recorded 07-15)     | 83.7%     | 0         | 14.5%    | 14.5%   | 71%        | 84.3 |
| B-v1 bm25@3 (rec. 07-15)    | 89.8%     | 0         | 34.8%    | 15.9%   | 49%        | 74.3 |
| B-v2 hybrid@6               | 83.7%     | 0         | 36.2%    | 2.9%    | 60.9%      | 78.6 |
| **B-v2 hybrid, E1@3**       | **93.9%** | **0**     | (36.2%)  | (2.9%)  | (60.9%)    | 80.0 |
| B-v2 hybrid k3-all          | 93.2%     | 0         | 27.5%    | 2.9%    | 69.6%      | 80.0 |
| C fine-tune                 | 83.7%     | **2**     | 21.7%    | 65.2%   | 11.6%      | 74.3 |
| D ft+hybrid@6               | 78.2%     | 0         | 42.0%    | 21.7%   | 34.8%      | 70.0 |
| D ft+hybrid E1@3            | 74.1%     | 0         | (42.0%)  | (21.7%) | (34.8%)    | 72.9 |
| D ft+hybrid k3-all          | 76.2%     | 0         | 36.2%    | 17.4%   | 46.4%      | 72.9 |

(Parenthesized E2 cells share the @6 E2 config with the primary row. Primaries ran 2x,
byte-identical — determinism 8/8 batteries; sweeps 1x, deviation logged §Stage 7.)

**Verdicts vs pre-registration:** B-v2@E1-top3 = FIRST BAR PASS (93.9%, zero dangerous).
E2 hard gate: unpassed by all nine cells; closest B-v2 (2 confident-wrongs, down from
B-v1's 11 — the cite-or-decline rider works on the base model; the fine-tune fights it).
ROADMAP gate rule ("pilot fine-tune must beat the RAG baseline"): **NOT MET** — C lost to
B on every axis. No EPYC spend justified. Winning architecture today: base + hybrid@3 for
diagnosis, retrieval-mandatory for values. Fine-tune cure: better pairs (Stage-C real-car
arcs), not more epochs — the failure mode (register without knowledge) is a data-quality
statement, consistent with the mix's known 27% Subaru share and synthetic dominance.

**Loose ends for daytime:** (1) judge batch died instantly at 00:14 (exit non-zero in
seconds; not diagnosed overnight — do NOT blind-retry; 394 docs now pending incl. 5781);
(2) top_k interaction: E1 distraction is dose-dependent (hybrid@6 83.7 vs @3 93.9) —
worth a line in decisions.md when ratifying the serving default; (3) the lora-on-Q8
serving approximation stands until the RAM kit enables true merge+requant; (4) E1v1
regression on every retrieval/ft cell vs base (84.3) — v1's self-contained-distraction
doctrine held all night.
