# Post-showdown direction: 2026-07-25

## Context

The showdown produced: B-v2 (base + hybrid@3) = first bar PASS (93.9/0 dangerous); pilot
fine-tune C = register-without-knowledge failure; D = best exact (42%) but 13 fabrications
that probe-level analysis proves are DECLINE-INSTRUCTION DISOBEDIENCE (identical retrieved
docs as B's declines, the fine-tune overrides cite-or-decline when evidence is absent).
E2 hard gate unpassed by all arms (best: B-v2, 2 confident-wrongs). ROADMAP gate rule: pilot
did NOT beat RAG baseline; no EPYC spend. Syed asks: improve D with real data / run RAG
alone / wait for RAM + larger model? Objective reframe: the milestone is the CAR idling and
driving right, the assistant exists to serve that.

## The strategy (Syed-ratified 2026-07-25): pass the gate first, then deploy; fine-tune waits for real data

**Syed's rulings:** NO deployment until the E2 hard gate passes (the gate is a gate);
fine-tune v2 waits for Stage-C real-car pairs.

### 1. Close the E2 gate: the deterministic citation guard (B-v3) - the new near-term centerpiece

**What it is**: ~50 lines of deterministic post-processing on value queries: extract the
number(s) from the model's answer; require each to appear in the RETRIEVED SNIPPETS the
model was shown (alnum-canonicalized, E2's own ±tolerance); absent -> answer mechanically
replaced with a decline. No ML, no probe knowledge, no scorer changes.

**Anti-benchmark-maxxing contract (Syed's concern, addressed structurally):**
- Provenance: cite-or-decline-as-code was pre-committed in ROADMAP 2026-07-10 ("necessary,
  not optional") BEFORE arms C/D existed; the guard is the strong implementation of a
  pre-registered doctrine, not a post-hoc patch. The 13-disobedience finding proves the
  prompt-only version insufficient: instructions are requests, code is law (the ECU-clamp
  pattern applied at the data layer).
- Deployed == measured: the guard runs identically in garage serving and in eval; E2's
  scorer and gate stay byte-identical. The eval measures the real system.
- Gauge on the clamp: ALL E2 reporting becomes "fabrications attempted / blocked / leaked"
  (pre-guard AND post-guard, side by side, forever). The model's attempt-rate stays the
  quality metric fine-tune v2 is judged on, the guard never hides model quality.
- Known blind spot, named in advance: the guard catches absent-from-evidence numbers; it
  CANNOT catch present-but-wrong-selection (right doc, two numbers, model picks the wrong
  one). The retro-test on the 7 known fabrications MEASURES this split, if wrong-selection
  residue keeps the gate red after the guard, that result STANDS as red (no second patch
  to force green; residue = documented open problem, likely snippet-attribution work).
- False-positive check: the guard must not kill B-v2's 25 correct answers (formatting/
  units canonicalization measured on real rows).

**Build**: `citation_guard.py` in the harness (reuse e2.py `parse_number` + the PDF-lesson
alnum canonicalization); wire behind the retrieval seam, value-mode only. Then: retro-test
on the 7 fabrication rows + 25 exact rows -> full E2 re-run as **B-v3 = B-v2 + guard**
(logged new version, same pre-registered gate). Deployment ONLY on a legitimate gate pass,
per Syed's ruling.
- Alongside (routine ops, independent): diagnose the instant judge-batch failure from the
  chain log, restart llama-judge service, run the 394-doc batch incl. 5781.

### 2. Stage C: wideband + real-car data (Syed in garage - THE critical path)
Serial connections -> day-1 ritual (double ROM read, archive x3, --rom-diff vs stock,
Stage-0 leak test, idle logs). This single arc serves BOTH goals: the car milestone
directly, and gold Subaru pairs (real symptoms->diagnosis->change->outcome arcs), the
only cure the fine-tune data supports. E3 eval becomes buildable.

### 3. Fine-tune v2: gated on gold pairs, with doctrine-in-weights fixes
NOT more epochs, NOT a bigger base. When Stage-C pairs exist (~50-100 real arcs):
- Mix in DECLINE-TEACHING pairs (queries whose correct answer is "not in references,
  measure it"): teach cite-or-decline into the weights, targeting the exact 13-fabrication
  disobedience mode found today. Cheap to synthesize from corpus with the existing pairgen.
- Keep: holdout early-stopping (it worked), r=16 pilot scale, same pre-registered bars.
- Re-run C/D batteries only then; same bars, versioned.

### 4. RAM kit (when it arrives): four paths, each with numbers, two decided by TEST not belief
Physics: decode t/s = active bytes / bandwidth. VRAM ~950 GB/s/card; DDR4-2133 RAM
~60 GB/s effective. Whatever lives in RAM streams 15x slower.
- **(a) MoE expert-offload bake-off, the real serving opportunity (Syed's idea, viable).**
  Attention/router in VRAM, expert bank in RAM; per token only active experts stream.
  Estimates: 120B-class/5B-active ~10-15 t/s; 106B/12B-active ~6-8 t/s, 100B+ reasoning
  at usable speed. DECISION BY BAKE-OFF: 1-2 candidates (re-verified at execution), one
  night each as arms A/B vs the SAME pre-registered bars + measured t/s; adopt only if it
  beats 27B on E1v2/E2 AND clears the interactive floor (proposed >=10 t/s decode, Syed
  ratifies). No adoption by vibes.
- **(b) Dense 70B offload, measured-and-declined expectation.** Q6 ~4 t/s, Q8 ~2 t/s
  (11-27GB forced into RAM): 8-15 min per thinking answer; also last-gen dense class.
  Documented; one confirmation bench allowed if Syed wants the number on record.
- **(c) Judge upgrade, decided by the calibration set, not opinion.** Load bigger judge,
  re-run the 100-doc adjudicated set, compare agreement vs current judge. Jump -> re-judge
  marginal bands; flat -> keep current judge, zero re-judging. (Context: sheriff layer has
  been compensating; showdown says corpus CONTENT is the binding constraint, expectation
  is modest, the test settles it.)
- **(d) Unconditional wins:** TRUE adapter merge + fresh Q8 requant (kills the lora-on-Q8
  approximation); corpus jobs; NUMA-balanced 192GB@2133 population per the fit plan.

### 5. Parked/queued
- Learning-queue walkthroughs (QLoRA/embeddings/prepare.py), evening sessions.
- On-vehicle context design (rolling session file). Stage C design work.
- 3090 teardown. Syed's timing.

## Verification
- Citation guard: unit tests (number extraction, tolerance, canonicalization, decline
  conversion) + retro-test against the 7 known fabrication rows (must catch 7/7 without
  killing any of B-v2's 25 exacts) + full E2 re-run as B-v3 vs the pre-registered gate.
- Judge: diagnose from chain log stderr, fix, run one small batch, verify 5781 verdict.
- Fine-tune v2 (later, data-gated): same pre-registered bars; decline-pair efficacy
  visible as D-v2's B-decline->D-fabricate count (today 13; target 0).
