# 2026-07-16 - SESSION CLOSE: pilot mix v3 final, priority ladder to the QLoRA gate (DELTA)

**READ THIS FIRST on session start. Supersedes all prior handoffs.** Forward plan: docs/ROADMAP.md.
This closes the marathon session of 2026-07-08 → 07-16 (context limit reached).

## START HERE (next agent, in order)
1. **Ask Syed for two one-liners:** (a) confirm **pilot-mix-v3 sign-off** ("moving on" was
   discussed and agreed in principle, never explicitly signed), v3 = 280 pairs
   (70 organic + 210 synthetic), EVERY pair personally full-read by Claude 2026-07-16, at
   `ml/curation/data/pairs/pilot-mix-v3.jsonl` (drop audit: docs/pilot-mix-v3-drops.txt);
   (b) **E1v2 bar re-wording**: registered "90% top-1 AND 100% acceptable" is vacuous on v2
   where acceptable≡exact; propose "90% top-1, acceptable clause struck" → record in DB meta
   key `eval.e1v2.preregistration` + decisions.md amendment.
2. Then execute the priority ladder below. QLoRA prep can start immediately after (a).

## PRIORITY LADDER (Syed-approved structure, 2026-07-16)
- **P0 (one-liners):** v3 sign-off · E1v2 bar re-ratification.
- **P1a, QLoRA pilot (arm C). LEARNING-PRIORITY: Syed drives, Claude teaches.** Prep first
  (agent does alone): format v3 → instruction dataset; re-verify base-model choice AT
  EXECUTION TIME (standing policy, never from memory; July pick was Qwen3.6-27B, RAM may
  have changed); training-config skeleton; train on the **Ti only** (3090 is convicted,
  see GPU section). Then the evening session: LoRA/quant/hyperparams taught, run launched.
- **P1b, wideband install (Syed, garage; 2 wires from live as of ~07-15).** Day-1 ritual
  staged: double ROM read → archive ×3 (ROM is sacred) → `ecutune.cli --rom-diff` vs stock
  3B12504206 → Stage-0 leak test BEFORE any tuning → first idle logs. Guide:
  car/ecu/LAPTOP-SETUP.md. Unlocks Stage C (gold Subaru pairs + E3 eval).
- **P2, embeddings retrieval upgrade, BEFORE the 4-arm showdown.** Motivation: E2 findings
  (BM25 ceiling 34.8% match; 5 retrieval-INDUCED fabrications). Build: local embedding model
  (re-verify choice), embed 3,791 kept chunks, hybrid dense+BM25 behind the `retrieve()`
  seam, higher top-k for value queries, **cite-or-decline system rule** (never state
  calibration numbers absent a verbatim retrieved value, data-layer mirror of the safety
  doctrine). Re-run arm B as logged new version. ~1 evening + 1 eval night. Learning-queue
  candidate (Syed may co-build).
- **P3, the 4-arm showdown:** A/B(upgraded)/C/D on E1v1+E1v2+E2 vs pre-registered bars
  (DB meta keys eval.e1.preregistration, eval.e1v2.preregistration; E2 hard gate
  pre-committed) → the ROADMAP decision rule → architecture + EPYC verdict.
- **P4 (trivial, fold into any session):** gone-sweep policy (gone-ness affects scraping,
  NEVER judging/mining, batch 4 proved gone threads are the best material; ~10 min) ·
  manual look at parked docs 5781 + sibling (~5 min).
- **P5 (post-gate):** r3 rubric batch, methodology-genre fix, LLM-content policy,
  qualitative-outcome rule, dedup cap. Syed-owned design session; r2 verdicts STAND
  (versioned); r3 requires RE-CERTIFICATION vs the 100-doc adjudicated set before becoming
  gate of record.
- **P6 (on demand post-gate):** extend e2gen/pairgen to multi-chunk docs (reuse judge
  chunker), unmined book/thread supply if the gate says more data helps.
- **P7 (Syed's timing):** 3090 forensic teardown (dossier complete: 11 SEL convictions,
  152<fail<230W bracket, cap-group route, see chats 2026-07-08/10) · learning-queue
  walkthroughs (docs/LEARNING-QUEUE.md, 10 items, RAG retrieve() first).
- **Continuous:** nightly scrapers (timer Persistent fixed) · judge new-doc batches as they
  accumulate · NASIOC cookie ritual on demand (hours-lived; canary fails loudly).

## WHAT THIS SESSION DID (2026-07-08 → 07-16, all committed; PROGRESS.md has full entries)
- **Corpus:** judging completed (5,697 docs, 3,791 keeps) incl. community + NASIOC batches.
- **Eval harness built from zero** (ml/eval/harness/): arms A/B, E1 runner (scoring
  byte-identical to rules baseline via file-path import), E2 probe gen + hard-gate scorer,
  E1v2 (voltage-sweep MVEM extension breaks leak/dead-time degeneracy; v1 byte-identical
  test-locked), pair generator (4 batches), classifier, assembler. RAG's query_terms was
  built BY SYED (his first Python, resume teaching at retrieve(), memory: syed-rag-
  learning-progress).
- **Eval verdicts (all pre-registered, all recorded):** E1v1 A 84.3/B 74.3 (RAG −10 on
  closed reasoning); E2 A 14.5%/B 34.8% match, BOTH fail fabrication hard-gate, 5
  retrieval-induced fabrications found; E1v2 A 83.7/B 89.8, **B failed Syed's 90% bar by
  ONE case**; retrieval doctrine fully characterized (distraction on self-contained,
  key on knowledge-gated, insufficient for exact-value integrity).
- **Training set:** 841 synthetic drafts → classify/dedup/off-field purge (46% of survivors
  convicted after Syed's catches) → community batch 4 (best density: 20 subaru/25 deep of
  36) → **v3 = 280 pairs, 100% Claude-full-read**. Syed's three review rounds caught real
  classes each time (sampling skew, off-field, tool-trivia/mechanical), his 15% sample
  hit-rate exactly predicted the pool rate.
- **GPU:** crashes #10/#11 (fully-pinned decode ~230W) → threshold bracketed 152<fail<230W
  → 3.5:1 split @810MHz/~152W has run crash-free since 07-08 (8+ days). DO NOT raise 3090
  clocks/share. Teardown dossier + diagnosis route delivered to Syed.
- **Rules created (memory/ + ml/CLAUDE.md, all HARD):** narrate-all-actions ·
  local-llm-output-review (hardened twice: quality × current-goal-fit + batch needs-census;
  **SHERIFF-NOT-DEPUTY: local classifier is pre-filter only, anything training/eval-bound
  gets a personal Claude full read, every item; organic gets the same field screen**) ·
  command-explanation rule stands.

## GOTCHAS (new this session, full list also in 2026-07-08 handoff)
- pgrep watcher patterns: `\|` inside quotes = LITERAL pipe (matches nothing), use single
  quotes + bracket trick, and TEST against the live process. Self-match killed a watcher once.
- Organic harvest rows: `provenance` is a DICT; synthetic is `"synthetic:<id>"`: type-check.
- Runner marks docs FAILED if llama-server restarts mid-run, stop runner first.
- Backgrounded `cd X && cmd & tail rel/path` → tail runs in OLD cwd; absolute paths after `&`.
- Thinking-model budget: 8192 min (4096 starved case 43); empty completion = scored miss.
- PDF sources mangle whitespace/hyphens, quote-verification must canonicalize to alnum.

## KEY FILES
pilot mix: ml/curation/data/pairs/pilot-mix-v3.jsonl · drops: ml/curation/docs/pilot-mix-
v3-drops.txt · mix reports: ml/curation/docs/pilot-mix-v1-report.md (+batch reviews) ·
eval results: ml/eval/results/ · harness: ml/eval/harness/ · decisions: ml/eval/DECISIONS-
PENDING.md (all knobs signed except the two P0 one-liners) · learning: docs/LEARNING-
QUEUE.md · eval bars: corpus.sqlite meta keys eval.e1.preregistration / eval.e1v2.pre-
registration · organic pairs: ml/curation/data/pairs/pairs-rubric-r2.jsonl.
