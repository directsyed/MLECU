# 2026-07-16: Pilot mix v1 assembled; everything waits on Syed's C3 word (DELTA)

Read FIRST on session start. Supersedes 2026-07-08 handoff. Forward plan: docs/ROADMAP.md.

## Current live state
- **Pilot training mix v1: ASSEMBLED, quarantined pending Syed's final C3 sign-off.**
  400 pairs = 82 organic + 318 synthetic (from 841 drafts via classify→filter→dedup→
  priority-cap). Deficit topics recovered (ve_load 64, injectors 46, idle 25, maf 18).
  **Subaru 21% vs 70% doctrine target, flagged honestly** (quality filter gutted shallow
  ROM-def Subaru clones; cure = Stage-C real arcs + community-thread synthesis batch).
  Syed's sample: `ml/curation/docs/pilot-mix-SAMPLE.md`; report: `pilot-mix-v1-report.md`.
- **Eval state:** E1v1 (A 84.3/B 74.3, RAG hurts closed reasoning), E2 (A 14.5/B 34.8,
  RAG 2.4× recall, both fail hard gate, retrieval-induced fabrication found), E1v2 (A 83.7/
  B 89.8, RAG +6.1 on knowledge-gated reasoning, B fails Syed's 90% bar BY ONE CASE).
  Retrieval doctrine fully characterized. **Pending Syed: v2 bar wording re-ratification**
  (registered "100% acceptable" was v1 semantics; on v2 acceptable≡exact).
- **GPU:** 3090 stable 7+ days at 810MHz/⅓-duty (~152W). Bracket 152<fail<230W. Teardown
  dossier complete (11 SEL convictions + dose-response + diagnosis route in chat 2026-07-08).
- **Wideband: 2 wires from live** (Syed, ~2026-07-15). Day-1 ritual staged: double ROM read
  → archive ×3 → --rom-diff vs stock 3B12504206 → Stage 0 leak test → idle logging.

## NEXT (order)
1. **Syed: C3 sign-off** on pilot-mix-SAMPLE.md → mix becomes arm-C/D training set.
2. **QLoRA pilot session, LEARNING-PRIORITY, Syed drives** (re-verify base model per policy;
   teach LoRA/quant/hyperparams; train on the Ti). Then arms C/D → the 4-arm showdown.
3. Wideband lands → car domain wakes (Phase B ritual above); Stage-C arcs fix the Subaru mix.
4. Backlog: E1v2 bar re-ratification · embeddings retrieval upgrade (motivated by E2
   fabrication finding) · r3 rubric · community-thread synthesis batch · 3090 teardown ·
   LEARNING-QUEUE walkthroughs (10 items, RAG retrieve() first).

## Gotchas added this session
- pgrep watcher patterns: quoted `\|` = LITERAL pipe in ERE (matches nothing), use
  unescaped `|` inside single quotes + bracket-trick self-match defense; TEST the pattern
  against the live process before trusting the watcher.
- Organic harvest rows carry a `provenance` DICT (doc/chunk metadata), synthetic rows use
  the string `synthetic:<id>`. Type-check, don't string-compare.
- All prior gotchas (2026-07-08 handoff §gotchas) still stand.
