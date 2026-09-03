# 2026-08-02 - SESSION CLOSE: showdown complete, bench-integrity plan HELD, 27B ratified as working model

**READ THIS FIRST on session start. Supersedes prior handoffs.** This closes the
2026-07-29 → 08-02 autonomous benchmark marathon (RAM install → burn-in → guard trials →
5-model showdown → audit).

## START HERE (next agent, in order)
1. **The plan of record is [docs/PLAN-bench-integrity-e4-2026-08-01.md](../../docs/PLAN-bench-integrity-e4-2026-08-01.md)**
   - Syed approved holding it, NOT executing yet. Execution begins on his word, at Phase 1
   (instrumentation fixes). Do NOT rerun any bench before those fixes: the audit found the
   scorer still parses `[REF n]` ids as answers (A1), 57/69 E2 probes carry parse traps,
   and the snippet extractor truncates numbers. All current E2 verdicts carry that asterisk.
2. **Syed's ratified decisions (2026-08-01/02):**
   - **Working model = Qwen3.6-27B dense Q8** (incumbent). Deployment serving config when
     ratified: hybrid retrieval, top_k 3 diagnosis / 6 value-lookup, citation guard, MTP ON
     (93.9% + ~2x speed; MTP-off was a bench-comparability constraint only).
   - Probe-v2 dispositions PRE-AUTHORIZED (table ships in the Phase-4 report for review).
   - E1v2 arm-B@3 re-verify after snippet fix: finalists only (27B + gpt-oss, ~8h).
   - E4 runs on 27B + gpt-oss (~4-8h) after Syed ratifies pre-registered bars.
   - **top_k mode-switching discussion (when to serve @6) DEFERRED to next session. Syed
     explicitly wants this conversation.**
3. Wideband/car data may land ANY TIME in `car/dataset/*.csv` or `car/ecu/rom-archive/*.bin`
   - Stage-C work then outranks everything (ROM ritual + AEM bring-up are documented in
   car/ecu/LAPTOP-SETUP.md; pin-5 ground + AFR-mode + AEM-UEGO-AFR-9600 plugin are the
   settled details). NOTE: the bench driver that auto-preempted on car data is now
   DISABLED, the next session must watch for the drop itself or re-arm a watcher.

## Final corrected matrix (pre-integrity-fix numbers; E2 carries the audit asterisk)

| model | E1v2 A | E1v2 B@3 | dang | E2@6 exact | gate | decode t/s |
|---|---|---|---|---|---|---|
| **Qwen3.6-27B dense (WORKING MODEL)** | 83.7 | **93.2** (93.9 MTP-on) | 0 | 26/68* | PASS@3 | 24 (46 MTP) |
| Qwen3.6-35B-A3B | **90.5** | 83.7 | 0/3 | 25/68* | FAIL(2)* | 44 |
| Qwen3-Next-80B Thinking (Q6_K) | 73.5 | 72.8 | 0 | 25/69* | FAIL(2)* | 31 |
| gpt-oss-120b (MXFP4, effort=high) | 86.4 | 83.7 | 0 | 26/68* | PASS | 23 |
| Mistral Small 4 (MXFP4_MOE) | 29.3 | 44.9 | 30/22 | - |, | 19, **INCONCLUSIVE** (my 4-bit quant deviation is prime suspect) |

*E2 numbers exclude probe e2-5723-1 by hand (OUR snippet bug truncated "11.8%" to "11" and
three models were convicted for quoting it); full re-derivation is plan Phase 3.

**Verdicts vs Syed's hypothesis (more params → better reasoning): NOT supported**, the
controlled pair (35B vs 80B, both 3B-active, Q8 vs Q6) went 90.5 vs 73.5; scaling helped
27B→35B closed-book then reversed. Retrieval value is MODEL-DEPENDENT: +9.5 for the 27B,
NEGATIVE for 35B and gpt-oss at k3. E2 arm A flat everywhere (stored-knowledge signature
absent). 27B chosen: wins the deployed config (arm B@3) by 9.5pp over both finalists,
gate-clean, fastest, VRAM-resident. gpt-oss = runner-up (best corrected arm A at 86.4,
zero dangerous anywhere), stays in E4 per Syed.

## What this session built/learned (delta)
- **RAM**: 168GB @2133 across 14 DIMMs, 7 channels (B4 slot DEAD, multi-bit ECC at MRC,
  survives reseat; channel D unusable, B8 pulled). Burn-in PASSED (memtester 100G, stress-ng
  2h, EDAC 0/0/0/0, SEL clean vs baseline). Old 2x16GB Hynix 2400 = spares. hardware-state
  facts: dual E5-2660 v4 verified, Ti-first offload doctrine.
- **Ti-first offload policy (Syed's)**: tensor_split=1,0 + -ot minimum overflow band on the
  3090; two regimes (FITS minimizes 3090 share / OVERSIZED maximizes it vs RAM). 3090 held
  ~110-125W all week, never tripped the 200W duty watchdog. Zero box deaths, 5 models.
- **bench/ pipeline** (ml/eval/bench/): sqlite ledger + autonomous systemd driver + duty
  watchdog + car-data preemption + done-validation (row count, model tag, refs, reasoning
  floor >=40 median tokens). 40 units executed. Driver now DISABLED (drained).
- **Guard-phase findings**: E2 hard gate PASSED first time (27B B@3+guard, 19 exact/0 dang);
  arm D+guard blocked 11/14 fine-tune fabrications (3 leaked = the named blind spot);
  **MTP is NOT output-invariant** (91.2% answer agreement on-vs-off, ±0.7pp, 1.92x speed);
  back-to-back same-config runs ARE deterministic (147/147 twice).
- **Four measurement defects found and fixed mid-run** (wrong 80B variant / Mistral
  reasoning_effort=none / 8192 token-ceiling truncation / 600s client timeout); each fix
  exposed the next. Validation gained the reasoning floor + finish-reason lessons.
- **The audit** (2 agents, findings in the held plan): A1-A18 code bugs + 57/69 probe flags
  + C1-C9 validation gaps. THE reason nothing reruns before Phase 1.
- **E4 designed** (held plan Phase 5): LLM diagnosis → ScalarSplit knob selection →
  clamp → MVEM re-sim loop; masking metric; fake-LLM dry-run spec; bars need Syed.
  All hooks verified present in car/ecutune (split arg, STAGE_REGISTRY, provenance).

## System state at close
- GPUs idle, locks verified (3090 810MHz/300W, Ti 1500/400, persistence ON, gpu_guard
  self-heals + halts if the 3090 can't be confirmed pinned).
- Services: mlecu-bench **disabled** (queue drained). llama-judge **still disabled from the
  pipeline**, first sudo action next session: `sudo systemctl enable --now llama-judge`
  (or run batches user-level); ~300+ docs pending incl. re-queued 5781.
- nvidia packages apt-mark HELD (the 2am unattended-upgrade lesson). vm.swappiness=1.
  Narrow NOPASSWD sudoers for nvidia-smi/ipmitool at /etc/sudoers.d/mlecu-bench.
- Models on disk: 27B Q8/Q6, 35B Q8, 80B Instruct+Thinking Q6_K, gpt-oss MXFP4, Mistral
  MXFP4_MOE (~330GB total, 465GB free). Dense index STALE (5,608 of 5,638 rows), rebuild
  is in plan Phase 1.
- Ledger: ml/eval/bench/bench.sqlite (40 units: 35 done, 5 skipped-invalid). Results in
  ml/eval/results/ (model identity is in the row `model` field, never the filename).

## Learning queue additions this session
MoE expert offload + -ot placement; MTP non-invariance finding; the four-defect
chain (variant/effort/ceiling/timeout); audit methodology (fresh-eyes agents + probe
audit). All queued in docs/LEARNING-QUEUE.md pattern, walkthroughs when Syed has time.
