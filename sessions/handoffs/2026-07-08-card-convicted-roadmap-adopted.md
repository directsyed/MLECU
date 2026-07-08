# 2026-07-08 — Card convicted, corpus ~85% judged, master roadmap adopted (DELTA)

Read this FIRST on session start. Supersedes the 2026-07-05 handoff. Full forward plan now
lives in **`docs/ROADMAP.md`** (durable, committed) — read that for anything future-facing.

## Current live state (verify with the commands, don't trust these numbers blindly)
- **Judge / corpus:** reference tier ~85% judged (~4,800 judged, ~940 pending, 2 failed).
  Runner detached (`setsid`), log at `ml/curation/data/ref-tier-run.log`; `judge.cli --status`.
  Resume-safe: after any crash, reboot auto-restores locks, then re-launch the batch one-liner
  (in ROADMAP + below). 2 failed docs = 5781 (runaway-deliberation) + parked; manual queue.
- **GPU — THE 3090 IS CONVICTED (hardware fault, not software).** Nine PCIe Bus Fatal crashes.
  Slot-swap test (crash #9, SEL named Slot 7 = the 3090's new CPU2 slot, Ti now in slot 3
  healthy) proved the fault FOLLOWS THE CARD. Root cause: the card's own power-delivery/PCIe
  interface glitches on load transients. **Suppressed, not cured** by derating: `gpu-powerlimit
  .service` now UUID-targets each card (slot-swap reversed enumeration) and locks 3090 @1000MHz
  core (peak ~215W under the 300W cap → limiter unreachable → no forced excursions) + mem 9501,
  Ti @1500/10251. Has run ~2 days crash-free at this derate. DO NOT raise the 3090 clock.
  Endgame: repad/teardown (tamper-marked screws — someone was inside) → inspect the six backside
  cap groups first (2020 GA102 POSCAP story matches our signature) + multimeter protocol (rail
  shorts, phase symmetry, PCIe-lane diode fingerprint, flex-probe for cracked caps) → repair/
  retire/replace. Verification = the 1-minute provoked-crash test (unlock clocks, keep caps,
  real inference; sick card dies in ~40s). Flight recorder is systemd now (survives hangs).
- **Services (all systemd, boot-safe):** `llama-judge` (dense Qwen3.6-27B Q8, layer-split +MTP,
  ~54 t/s — TP tested WORSE at 44 t/s, cross-socket sync tax, reverted), `gpu-powerlimit`,
  `pcie-flight-recorder`. Watch cockpit: `bash infrastructure/monitoring/watch-judge.sh`.

## What shipped since 2026-07-05
- **Judge CERTIFIED** (calibration PASS: keep/drop 93.1%, ±1 97.7%, 0 dangerous cells; bars
  pre-registered; any-chunk≥4 keep metric). Community tier fully judged. 65 pairs harvested
  (`--harvest`). rubric-r2 is the gate of record.
- **MASTER ROADMAP** (`docs/ROADMAP.md`) adopted: 7 phases certified-judge → driving Forester,
  under the immutable safety doctrine. Includes the FULL RAG-vs-fine-tune eval protocol (4 arms
  × 3 eval sets, dangerous-near-miss HARD GATE, pre-registered decision rule) and the
  definition of done (v1.0 tuned car / v2.0 thesis-proven = the EPYC gate).
- **`ecutune.cli --rom-diff A B`** built (romread/diff.py + tests): table+byte comparison of a
  real ECU read vs the harvested stock 3B12504206 — the "is it really stock?" artifact for the
  first ECU read. Degrades to byte-only if semantic decode refuses. 48 car tests green.
- **`car/ecu/LAPTOP-SETUP.md`**: full RomRaider/ECUFlash/Openport guide. Warns of the "Unknown
  ROM Image" trap (do NOT flash A2WC412D to "fix" it — corpus doc 1036's mistake) + logger.xml
  missing-ECU-ID clone procedure + Openport clone validation (double-read + --rom-diff).
- **NASIOC**: canary probe added (dead cf_clearance now fails LOUDLY, not silent 0-fetch);
  **`nasioc-cookie.sh`** helper so Syed sets the cookie himself (`bash nasioc-cookie.sh '<val>'
  --pull`). Cookie lives HOURS, UA-bound — export fresh from same Chrome profile before pulling.
- **HARD RULE added (root CLAUDE.md + memory):** every CLI command given to Syed must be
  explained, every new flag individually. He is learning; no unexplained one-liners.

## NEXT (in priority order)
1. Finish reference tier (~940 left, ~few hours). Then FULL pair re-harvest over everything +
   corpus stats report → PROGRESS (answers "is the corpus enough" with a real number).
2. Sweep: 9 gone-marked community docs (one-off pattern proven on 1031), 5781 manual review,
   gone-sweep-vs-judge policy. Judge the 6 fresh NASIOC threads (incl. 200-post tuning guide).
3. r3 rubric backlog (single batched revision; r2 verdicts STAND — versioned, no retroactive
   re-judge): methodology-genre fix, LLM-content policy, qualitative-outcome rule, dedup cap.
4. **Eval harness head-start** (ROADMAP task, buildable NOW, car-independent): arms A (base) +
   B (RAG over ref_fts), E2 exact-value probe generator from reference keeps → first
   base-vs-RAG readout. Locks the baseline side of the gate.
5. Car domain UNBLOCKS when the wideband arrives (days out; Openport already acquired): laptop
   setup → validate clone → FIRST ROM READ (sacred archive ×3) → --rom-report + --rom-diff vs
   stock → Stage 0 leak test → idle logging. See ROADMAP Phase B.
6. Hardware side-quests: 3090 repad/diagnosis, chassis fans, CPU2+BIOS-first, RAM (bigger
   models). DB snapshot before any risky op (`data-backups/`, gitignored; use SQLite .backup API
   not cp — WAL).

## Standing facts / gotchas
- Command-explanation rule is HARD (above). · Model choices re-verified at runtime, never from
  memory. · DB writes go through corpus_pipeline.State (WAL, busy_timeout=10000 for concurrent
  labeler+runner). · One corrupt crash-era audit line exists — parsers skip. · The LLM proposes,
  clamped human-reviewed code executes — never designed away; extended in ROADMAP Phase E
  (our code writes FILES a human flashes, never drives the flash tool). · 93 octane only. ·
  memory/ holds: judge-design-directives, command-explanation-rule.
