# MLECU — Progress Log

Reverse-chronological (newest first). This is a portfolio/resume artifact — entries are written to be
legible to a technical reader who wasn't in the room. Performance numbers are also recorded in the
table at the bottom (date / metric / value / conditions) for a comparable history over time.

---

## 2026-07-03 — Universal-first corpus expansion (4 new sources live)

**Context:** Syed's directive — the framework foundation is universal (every ECU speaks the same
channel vocabulary: MAF, trims, ECT, RPM, timing, VE = SAE J1979 + tuning extensions); Subaru
specificity layers on top. Full project review delivered (judge upgrades, semantic table layer,
sim-generated eval marked as follow-ups); "add every source not yet ingested" executed.

**Built** (`ml/data-pipeline/`):
- **Generic phpBB engine** (`forum_phpbb.py`, per-site binding) → three boards live: **speeduino**
  (universal open-EFI), **msextra** (MegaSquirt theory — first pass caught a 75-post "Free VE Table
  Corrections — drop your MSQ and a datalog" thread), **romraider.com** (Subaru tuning/logging/defs;
  seeded with the **2005 Forester XT 4EAT stock ROM map** thread — Syed's exact platform).
- **`tunerstudio_ini`** — speeduino.ini → **55 cross-platform table/curve definitions** (reference):
  the universal table vocabulary for the future semantic layer.
- **OBD-II PIDs** (J1979) reference page; **AEM wideband manuals** (30-0300/30-0310/FAE) → 36 pages.
- **NASIOC**: built + tested, **gated** — hard Cloudflare doesn't clear headless (challenge-retry
  loop added to BrowserFetcher anyway; benefits legacygt). Revisit: non-headless cookie seed.

**Corpus: 1,026 docs (976 reference / 50 community), 22 tests green.** Daily timer now accumulates
from three new boards passively.

**Follow-on same day — XenForo boards + NASIOC gating:**
- **`forum_xenforo`** engine → **subaruforester.org** (Syed's chassis: engine-tuning-datalogging +
  EJ25-turbo-2004-2013 + EJ20-turbo nodes) and **iwsti.com** (STI tuning). VerticalScope 202 stub →
  BrowserFetcher; verified end-to-end (20-post thread parsed). Slow (~25 s/page) so caps kept tight;
  nightly timer accumulates.
- **NASIOC**: built + enabled but **cf_clearance-cookie-gated** — its Cloudflare managed challenge is
  unbeatable headless (confirmed); a home-browser cookie (same public IP as the T630) auto-activates it.
- **BrowserFetcher** hardened (wait_until param, non-fatal goto, CF re-read, cookie injection).
- **6 forum boards** now (legacygt, speeduino, msextra, romraider, subaruforester, iwsti) + NASIOC gated.
- **RAM spec for the parser:** 32GB DDR4-2400 ECC RDIMM 2Rx4 PC4-19200 288-pin 1.2V. **27 tests green.**

**Decided** (decisions.md): model choices re-verified at execution time (Qwen2.5-32B judge plan was
2 generations stale — Syed's catch); judge as of 2026-07 = **Qwen3.6-35B-A3B @ Q8** via MoE expert
offload on the single 3090 + 32 GB RAM; **Q6 min / Q8 preferred** inference floor.

---

## 2026-06-27 — car/ecutune: deterministic algorithm + safety layer (offline, built)

**Built** — `car/ecutune/`, a new self-contained package (own `.venv`; numpy + hypothesis; mirrors `corpus_pipeline` conventions, copied not coupled). The car domain's first real code:
- **`safety/` — the write-path guard (the project's HARD safety constraint, now testable code, not prose).** Seven ordered clamps as pure functions — knock auto-abort, fuel-before-timing, steady-before-transient, boost gate, timing-row ceiling, **±3% VE rate-limit**, **AFR floor**. `apply_proposal()` is the *only* function that writes a Table, enforced by a source-scan meta-test. "The LLM never writes ECU values" is now true **by construction** — every proposer (the algorithm today, the LLM tomorrow) goes through the same clamped door.
- **`logparse/`** — tolerant RomRaider/SSM2 CSV parser (header→canonical-role using the 219 ingested SSM2 params) + (airflow×rpm) binning with a steady-state gate and the trim-error signal (`af_correction + af_learning`).
- **`algorithms/`** — bounded-integral / damped-PI controller (the ±3% clamp *is* the anti-windup) + the idle global-scalar corrector (injector latency→flow-scaling→low-MAF, emits one Proposal, never self-applies).
- **`simulation/`** — a mean-value engine model (MVEM) seeded with the known EJ20X-vs-EJ255 mismatch + the convergence harness running the full loop offline.

**Result — the offline proof (no car, no GPU):** from a seeded **+14.8% lean idle trim**, the loop converges to **<5% in 4 iterations with ZERO clamp violations**, deterministically (same seed → identical tables), across all tested seeds. **31 tests green** (unit + hypothesis property tests over the safety bounds + the keystone convergence test). One command: `cd car && PYTHONPATH=. .venv/bin/python -m ecutune.cli --run-convergence`.

**Why it matters:** the safety-critical core is validated end-to-end before any hardware exists. Real RomRaider logs drop into the same `bin→propose→clamp` path when the wideband arrives (`synth_log` already emits the real `LogTable` shape).

**Next:** Track B — the LLM-judge design (Syed's learning thread).

---

## 2026-06-26 — EFI-reference corpus (tier) + judge architecture

**Built**
- **Document `tier`** field (`reference` vs `community`) wired through model/schema/state/status — the split that keeps the judge non-circular.
- **`ecu_docs`** HTML source (reference tier): MegaSquirt **MegaManual** fundamentals (fuel equation, VE, tuning, injectors; private-corpus use). rusEFI already covered (its wiki = the `rusefi_documentation` repo we ingest); Speeduino redundant; AEM/Haltech skipped (gated + shallow).

**Corpus:** ~910 docs — **883 reference** (RomRaider defs+logger, rusEFI, MegaManual) + **27 community** (forums). Tests green.

**Decided (`decisions.md`):** the judge is a strong *general* model that **grounds** noisy community docs against the reference tier — never trained on the data it filters; deferred to the 48 GB (2×3090) setup. PID: idle Stage-2 = feedforward + a bounded-integral convergence loop; **boost (Stage 3) = a real PID**, informed by the corpus.

---

## 2026-06-23 — Data pipeline: vertical slice live (RomRaider defs)

**Built** (`ml/data-pipeline/`, mirroring Hardware Parser conventions — copied, not coupled):
- Config-driven corpus pipeline: `core/` (pydantic config, `Document` + SQLite schema, WAL state
  with `(source,source_id)` dedup + `poll_run` health, shared HTTP client, text-quality gates),
  `sources/` (`Source` protocol + `REGISTRY`), orchestrator with per-source isolation, and a CLI
  (`--once / --sources / --dry-run / --status`).
- First ingester `romraider_defs`: clones RomRaider SubaruDefs (GPL-2.0), parses ECUFlash per-ROM
  XML → structured `Document`s (ROM identity + tunable-table list + provenance).

**Result — 890 documents in `corpus.sqlite`, all gated `kept`, pending judge:**
- `romraider_defs` (333 ECU defs) · `romraider_logger` (219 SSM2 telemetry params) · `rusefi_docs` (327 theory).
- `forum_legacygt` — **11 EJ20X/tuning threads** via a **patchright headless-browser** fallback (legacygt's WAF
  202-challenges plain HTTP). Now with **bounded discovery**: crawls the Tuning subforum, keyword-filters titles,
  skips threads already stored, caps new/run. One pass auto-found 6 goldmine threads — *"COMPLETE beginner's
  guide to e-tuning"* (300 posts), *"Knock, do you have any?"* (299), *"Official Turbo Upgrade & Dyno Tuned"* (270), etc.
- `local_pdf` — owner-supplied PDF ingester (drop into `data/raw/pdfs/{fsm,books}/`; per-page; gitignored).
- **Daily systemd timer** (`systemd/`) runs the pass automatically → passive accumulation while the 2nd GPU is set up. 11 tests green.

**Next:** install the timer; drop the FSM/book PDFs; (later) NASIOC source; then Stage B (the LLM judge — Syed's learning thread).

---

## 2026-06-22 — Closed-loop fan control + GPU thermal soak

**Built**
- **Closed-loop chassis-fan controller** (`infrastructure/server/gpu-fan-control.sh` + systemd unit): iDRAC
  manual mode, GPU-core curve (30% floor → 100% at 80 °C core) with a `max(core, cpu)` term and a
  revert-to-auto dead-man's switch. Deployed as an enabled service. PWM→RPM calibrated (~46 RPM/%).
- **Unified soak logger** (`infrastructure/monitoring/soak-logger.py`): junction/VRAM (gputemps
  direct-register reader) + core/power/clock/util (nvidia-smi) + fan RPM (ipmitool) → CSV, with a
  thermal **auto-abort** (vram/junction ≥108 °C or core ≥90 °C → fans 100% + kill load + exit).
- Tooling: built `gputemps` (staged `nvml.h` to skip the CUDA toolkit), installed `memtest_vulkan`.

**Measured — 5-min memtest_vulkan soak, in-chassis (T630, 2 shroud fans, 22 °C inlet, ~335 W / 99% util)**
- Plateaued after ~2.5 min. **VRAM (GDDR6X) peaked 100 °C** — vs **106 °C** in the Omen, so in-chassis
  airflow is ~6 °C better. Under the 110 °C ceiling; no thermal throttle (clock sag was power-limit), no errors.
- GPU hotspot 94 °C, core (edge) 79 °C.
- **Fan curve validated:** ramped 30% → ~94% (1740 → 4560 RPM) as core hit 79 °C, held core below the 83 °C throttle.

**Decision:** repad **deferred** (100 °C memory is warm-but-safe). Prefer adding chassis fans (already ~94%,
near the 2-fan airflow ceiling) and re-soaking; repad is the fallback. See `decisions.md`.

**Next:** add additional chassis fans + re-soak; then the LLM-corpus data scraper.

---

## 2026-06-22 — Project bootstrapped; GPU bring-up verified

**Built**
- Initialized the `MLECU` repository: a layered `CLAUDE.md` hierarchy (lean root + `infrastructure/`,
  `ml/`, `car/` domain files), refined `context/` (project-purpose, hardware-state, principles),
  `decisions.md`, this `PROGRESS.md`, `README.md`, and `sessions/handoffs/`. The verbatim bootstrap
  package is preserved in `context/bootstrap-source/` for provenance.
- Git repository initialized (two-commit history: verbatim package, then generated structure) and
  pushed to a private GitHub remote.

**Verified (live machine)**
- T630 `syedlab` up — Ubuntu 24.04, BIOS 2.5.4 (legacy boot), 1× Xeon E5-2630 v3.
- **RTX 3090 enumerates and the driver is up:** driver 580.159.03 / CUDA 13.0, 24576 MiB, PCIe
  04:00.0, idle 37 °C, 75 W / 350 W cap. (The bootstrap context had recorded this as "in progress.")

**Next (sequenced)**
1. Close out GPU/server bring-up — fan-curve calibration (ipmitool) + a **mem-junction-under-load**
   soak (gpu-burn + memtest_vulkan) to settle the OEM-3090 repad question. *(Learning-priority — run
   as a teaching thread.)*
2. Build the **LLM-corpus data scraper** (`ml/data-pipeline/`).
3. Stand up the **LLM-judge curation engine** (`ml/curation/`).
- ZFS deferred. Car domain dormant (wideband not acquired).

---

## Performance history

| Date | Metric | Value | Conditions |
|------|--------|-------|------------|
| 2026-06-22 | RTX 3090 idle temp | 37 °C | idle, 75 W / 350 W cap, driver 580.159.03, in-chassis (T630 slot 3) |
| 2026-06-22 | RTX 3090 VRAM (GDDR6X) peak | 100 °C | 5-min memtest_vulkan, in-chassis, 2 fans @ ~94%, 22 °C inlet, ~335 W — vs 106 °C in the Omen |
| 2026-06-22 | RTX 3090 GPU hotspot peak | 94 °C | same soak |
| 2026-06-22 | RTX 3090 core (edge) peak | 79 °C | same soak; below 83 °C throttle |
| 2026-06-22 | Fan curve under load | 30% → ~94% (4560 RPM) | core-driven ramp held core at 79 °C, no thermal throttle |
| 2026-06-23 | Corpus: ECU definitions | 333 docs | romraider_defs (RomRaider SubaruDefs, ECUFlash), gated kept, pending judge |
| 2026-06-24 | Corpus: SSM2 telemetry params | 219 docs | romraider_logger (loggable-channel schema) |
| 2026-06-24 | Corpus: theory docs | 327 docs | rusefi_docs (general engine-management) |
| 2026-06-24 | Corpus: forum threads | 11 (~1440 posts) | forum_legacygt — 5 seeds + 6 auto-discovered (Tuning subforum) |
| 2026-06-27 | Idle convergence: start trim | +14.76% | seeded EJ20X-vs-EJ255 mismatch, MVEM, seed 0 |
| 2026-06-27 | Idle convergence: final trim | +3.86% (≤5% tol) | 4 iterations, deterministic, offline |
| 2026-06-27 | Idle convergence: clamp violations | 0 | controller self-limits below ±3%; clamp is the backstop |
| 2026-06-27 | car/ecutune test suite | 31 passed (1.8 s) | unit + hypothesis property (safety bounds) + keystone convergence |
| 2026-07-03 | Corpus: total | 1,026 docs (976 ref / 50 comm) | after universal-first expansion: +3 phpBB boards, +55 TunerStudio defs, +OBD-II PIDs, +AEM manuals |
| 2026-07-03 | Corpus: cross-platform ECU defs | 55 docs | tunerstudio_ini (speeduino.ini tables/curves, reference tier) |
| 2026-07-03 | Pipeline test suite | 22 passed (0.5 s) | incl. new phpBB/vBulletin/INI fixture tests |

*Add rows as benchmarks/evals/training runs produce numbers — GPU thermals, inference
throughput/latency, fine-tune eval scores, corpus size/quality, tuning-loop convergence.*
