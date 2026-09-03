# 2026-07-05: Judge LIVE + slot-3 crash root-caused + rubric-r2 approved (DELTA)

Marathon session (cookie paste → 4 AM). Read 2026-07-04 handoff for prior state.

## Delta: what changed
- **Corpus gates opened:** NASIOC live (cf_clearance + pinned home-browser UA in config -
  keep them paired), 5 tuning subforums on nightly discovery. RomRaider ROM harvest 10/10
  incl. **2005 FXT 4EAT stock ROM 3B12504206 / internal id A2WC411D**.
- **car/ecutune/romread/**: READ-ONLY ROM-value reader (ECUFlash def parser + cross-def
  reconciliation: bit-identical corroboration or unique-plausibility survivor, never guess).
  Real calibration facts recovered (injector flow 503.93 cc/min, latency 0.661ms @14.1V, hot
  idle target 700rpm). **ROM-seeded convergence PASS** (+12.68→+4.46%, 4 iters, 0 clamp
  violations). 44 car tests green.
- **Judge harness built end-to-end** (`ml/curation/`): schema migration (judgment +
  human_label tables, doc-atomic mark_judged), chunker, FTS5 grounding, grammar-enforced
  JSON verdicts, JSONL audit with thinking captured, calibration tooling, CLI. 62 tests green
  across both packages. Both judge models downloaded (Qwen3.6-27B-MTP + 35B-A3B-MTP, Q8_0);
  llama.cpp b9872 built with CUDA; MTP flag = `--spec-type draft-mtp`; `-np 1` (MTP limit).
- **SLOT-3 BUS FATAL INCIDENT (see decisions.md 2026-07-05):** 4 hard hangs under bursty
  inference; single-variable elimination (dual-PSU, ASPM off, reseat, solo-GPU) + 1Hz fsync'd
  flight recorder (infrastructure/monitoring/) → **transient brownout from boost/limiter
  oscillation**; fix = boot-time clock locks (3090 @1395, Ti @1560) in gpu-powerlimit.service
  - NOW DEPLOYED+ENABLED (verified). 15/15 locked-solo, then dual 10-doc bench clean.
  Diagnostic habit: iDRAC SEL is the only surviving witness (firmware-first AER hides
  errors from the kernel); flight recorder for anything PCIe-suspicious.
- **Model bench (smoke-10, both models, same docs):** dense deterministic (6/6 identical on
  repeat doc), 0 fabricated pairs; MoE 3x faster, broader extraction, but 1 FABRICATED
  outcome leg ("knock eliminated") + leniency on tooling docs. Split verdict per
  pre-registered rule: **dense 27B = community-tier judge of record; MoE = candidate for
  reference-tier light-judging** pending calibration spot-check.
- **Adjudication (docs/smoke10-adjudication-claude.md + Syed guard read):** Syed's standard
  now governs: **no reported data-backed outcome = max 3.** 961 adjudicated 3 (MoE was
  right, dense+Claude over-scored). 960 adjudicated 4 via Syed's chunk ruling ("7-run MPG
  section 4-5"), validates per-chunk harvesting as the yield mechanism. Labels in
  human_label(label_set='smoke-10', rater=claude|syed|adjudicated).
- **rubric-r2 APPROVED by Syed:** outcome-required anchor 4, real-doc worked examples,
  tooling/redundancy anchor-2 case, extraction policy explicit (≥3 extract-stated-only),
  relevance tag (subaru_ej|subaru|general, firewalled from score, in judgment columns),
  evidence_in_images flag (VLM backlog), FXT/EJ20X context block, synopsis pre-pass for
  multi-chunk docs (option 2). config points at prompts/rubric-r2.

## NEXT (in order)
1. **Calibration-100 under r2**: freeze sample (`--sample`; ~96 community + ref anchors);
   **Syed blind-rates ~20 FIRST** (give him a full-text reader, NOT a 6k-truncated dump -
   that bug bit once); Claude rates all; divergence check; guard review; adjudicate.
2. **Dense judge runs the calibration set** (server launch command in chat history; locked
   clocks are automatic now). Agreement report vs Syed's PRE-REGISTERED bars (he sets them
   BEFORE seeing numbers, not yet done, do first).
3. Re-run doc 960 dense @6144 budget (was truncation-failed at 4096). MoE determinism
   re-run test before giving it the reference tier.
4. Then: full community-tier run + overnight reference-tier light-judge (MoE if it passes
   spot-check); PDF-context question is SETTLED (synopsis pre-pass).
5. Backlog: VLM captioning for image-bound evidence (evidence_in_images flags the worklist);
   audit-writer fsync hardening; flight-recorder systemd unit; card-vs-slot attribution swap
   (only if clock locks ever need lifting); hardware-parser co-tenancy during benches.

## Standing facts
- Judge stack: llama.cpp b9872, models in ml/curation/data/models/, launch in tmux, judge
  CLI dry-runs don't write the DB. Audit JSONL = the forensic record (one corrupt crash-era
  line exists; parsers must skip).
- memory/judge-design-directives.md holds Syed's standing directives (detailed rubric,
  Subaru context, yield concern, bigger fine-tune base if RAM grows).

## ADDENDUM (07-05 ~08:00) - CALIBRATION COMPLETE, JUDGE CERTIFIED
The NEXT list above is superseded: calibration ran the same night. **PASS on all pre-registered
bars** (keep/drop 93.1%, ±1 97.7%, dangerous 0; any-chunk>=4 keep metric ruled blind by Syed).
Adjudicated labels: human_label(calibration-100, rater='adjudicated'), 9 keeps. Full community
tier judged (116 docs). Dense 27B = certified gate of record.

### NEW next steps
1. **Reference tier run** (auto_pass defs/logger/ini instantly; light_judge the 4.6k PDFs
   overnight). DECISION FIRST: MoE for this tier needs a spot-check pass (it fabricated once);
   or run dense over several nights. Also judge the 9 gone-marked community docs (one-off
   pattern proven on 1031) + decide gone-sweep-vs-judge policy.
2. **Pair harvest**: extract chunk>=4 pairs (non-empty outcome filter) -> first training-pair
   corpus stats. The 9 kept docs are pair-dense (960 alone ~20+).
3. **r3 backlog**: methodology-genre undervaluation (1127 miss), synthetic/LLM-content policy
   (2 sightings), qualitative-outcome rule (1088/1114 consistency), runaway-deliberation cap
   (5781 parked), evidence_in_images -> future VLM pass worklist.
4. Ops: 5781 in manual-review queue; audit-writer fsync hardening; flight-recorder systemd unit.

## ADDENDUM 2 (~08:20) - harvest live, reference tier running unattended
- **First training pairs harvested: 65 pairs / 12 docs** (48 subaru_ej, 6 subaru, 11 general)
  -> ml/curation/data/pairs/pairs-rubric-r2.jsonl, full per-pair provenance. `--harvest` CLI.
- **llama-judge.service** (systemd, After=gpu-powerlimit) replaces tmux serving, deployed+enabled.
- **Reference-tier run DETACHED** (setsid, log: ml/curation/data/ref-tier-run.log): 552 auto-passed,
  ~5,050 light-judge docs at ~40s/doc ≈ 2.5 days. Resume-safe; just check the log / --status.
- On resume: check `judge.cli --status`, then queue = gone-marked 9 docs, 5781 manual review,
  MoE spot-check decision, r3 backlog, pair-harvest rerun when tier completes.
