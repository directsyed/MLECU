# MLECU — Progress Log

Reverse-chronological (newest first). This is a portfolio/resume artifact — entries are written to be
legible to a technical reader who wasn't in the room. Performance numbers are also recorded in the
table at the bottom (date / metric / value / conditions) for a comparable history over time.

---

## 2026-07-05 — Slot-3 PCIe Bus Fatal root-caused (transient brownout) → boot-time clock locks

Four hard system hangs during the judge's first real inference runs — box alive, NIC dead,
kernel silent (Dell firmware-first AER); only the iDRAC SEL recorded each `Bus Fatal Error
(Slot 3)`. Systematic single-variable elimination across five instrumented benches: dual-PSU
load sharing, ASPM off, physical reseat, and cross-socket P2P all ruled out (crash #5 was solo
on the 3090). A purpose-built **1 Hz fsync'd PCIe flight recorder** (survives hard hangs; now in
`infrastructure/monitoring/`) proved the link pristine to the final second every time — which
pointed away from signal integrity and at **power transients: boost/limiter oscillation
(recorded 1065↔1500 MHz at 299 W/300 W cap) sagging slot 3's 12 V → instant poisoned
transaction**. Discriminating experiment: core clock pinned at 1395 MHz, same everything else →
**15/15 requests, ~13 min sustained, zero events** (unlocked died ≤7 min, 4/4). Fix made
permanent in `gpu-powerlimit.service` (boot-time `-lgc` both cards). Cost ≈ nil — inference is
memory-bound (mem clock untouched). Bonus: 15 bit-identical verdicts at temp 0 — judge
determinism demonstrated on real hardware.

---

## 2026-07-04 (later) — Cookie gates opened; the REAL FXT stock ROM read; sim grounded in it

**Corpus/harvest:** Syed exported the two blocking cookies. **NASIOC is live** — cf_clearance +
matching home-browser UA passes Cloudflare (the UA must stay pinned to the cookie in config.yaml);
seed thread ingested and 5 tuning subforums (Engine Mgmt & Tuning, Open Source Reflashes, Factory
2.0L/2.5L Turbo, Subaru Conversions) enabled for nightly keyword discovery — first pass pulled a
200-post AVCS-tuning thread. **RomRaider ROM harvest: 10/10 attachments** downloaded (SHA1
manifest), headlined by **the 2005 FXT 4EAT stock ROM, CID 3B12504206** — the exact calibration
family of the test car's ECU.

**car/ecutune — ROM-value reader (`romread/`, READ-ONLY by construction):** parses ECUFlash defs
(include-chain merge: base metadata + revision addresses) and decodes tables from the raw image
(big-endian uint8/16/float, toexpr scaling). The harvested image's internal ID is **A2WC411D — a
revision no community def covers**, so the reader reads through BOTH sibling defs (A2WC410D/412D)
and reconciles deterministically: bit-identical reads corroborate; disagreements survive only as
the UNIQUE candidate whose axes are strictly monotonic and whose values respect the def's own
min/max (zero or multiple survivors = hard error). Finding: 412D's late-ROM addresses sit +0x20
from ours; every 410D read is physically sane → 411D shares the 410D layout. Extraction also
covered the EcuFlash `.srf` container (INFO/DRMI/MEML/MEMD; MEMD = the 1MB image).

**Real calibration facts recovered** (`--rom-report`): injector flow scaling **503.93 cc/min**
(the "~500cc matched injectors" prior is now measured), injector latency **0.48–4.90 ms** over
5 voltage points (**0.661 ms @ 14.1V**), 48-point MAF transfer (1.3–296.5 g/s), primary AFR map
10.94–14.70, base timing 2.15–45.04° BTDC, **hot idle target 700 rpm** (replaces the 850 guess).

**Sim grounded in the real ROM** (`rom_seed.py`, `--run-convergence --rom`): believed state = the
ROM's actual values; truth keeps the neutral swap-uncertainty ratios (MAF ~7% low, flow ~2% high,
latency ~4% low — no pre-decided culprit). **ROM-seeded convergence PASS: +12.68% → +4.46% in 4
iterations, 0 clamp violations** (synthetic control unchanged: +14.18% → +4.56%). The lower start
trim is physical — a 4% latency error on the real 0.66 ms dead time is a smaller absolute fuel
error than on the assumed 1.0 ms. **44 tests green** (4 new: def merge/decode, reconciliation,
plausibility bounds, real-ROM integration that skips on fresh clones).

---

## 2026-07-04 — 2nd GPU installed + validated (RTX 3090 Ti); fan/monitor tooling made multi-GPU

**Hardware:** Zotac RTX 3090 Ti (450W) installed alongside the HP OEM 3090 — both enumerate
(GPU0 = 3090 @ 04:00.0, GPU1 = 3090 Ti @ 83:00.0). The slot/power/clearance block is resolved.

**Tooling — made multi-GPU-aware** (was single-GPU, a real safety gap): the closed-loop fan
controller (`gpu-fan-control.sh`) now drives off the **MAX core temp across both cards** (was
`head -n1` = GPU0 only, so a hot Ti wouldn't ramp the fans while the 3090 idled). The soak-logger
now parses **per-GPU** gputemps JSON (per-card core/junction/VRAM columns + a compact ≤80-col
console view) and its thermal auto-abort watches the **hottest** card. Deploy gotcha caught: the
service runs `/usr/local/sbin/gpu-fan-control.sh`, not the repo copy — fixes must be `cp`'d there.

**Validation — 30-min memtest_vulkan soak on the 3090 Ti** (full 446W, SM+mem 100%, cover on, fans
auto-ramping ~4300 RPM): steady state **VRAM 92–94 °C, junction 88–89 °C, core 76–77 °C, no
throttle** (held ~1950 MHz full boost — power-limited, not thermal). vs the OEM 3090's 100 °C VRAM
at 335 W → the Ti's aftermarket cooler is far superior; **no repad needed for the Ti.** The 3090 sat
idle/cold throughout; inlet barely moved (20 → 21 °C).

**Next:** the **dual-card soak** (both loaded, ~780 W) — the real 2-GPU-viability test, where the
3090's marginal pads meet a hotter chassis and the repad decision gets made. Then: revisit the fan
curve with this data; stand up the 48 GB judge (Qwen3.6-35B-A3B).

---

## 2026-07-03 — Semantic table layer + sim-generated diagnostic eval

**Semantic table layer** (`car/ecutune`): algorithms + safety clamps now operate ONLY on
platform-neutral semantic IDs (`fuel.injector_flow`, `sensor.maf_transfer`, ...); platform names
live in `ecutune/platforms/` adapters — `subaru_ecuflash` (verified 2005 FXT A2WC400x names +
VARIANTS absorbing per-def spelling drift) and `tunerstudio` (Speeduino: injOpen/reqFuel/advTable1Tbl;
speed-density gaps are honest absences). **Subaru is now adapter #1 on a universal foundation** —
the structural encoding of the universal-first directive. Convergence PASS unchanged.

**Sim-generated diagnostic eval** (`ecutune/evals/` + `ml/eval/data/sim_cases_v1.jsonl`): known
faults seeded in the MVEM (extended with unmetered-leak air + operating-point scaling) → two-point
datalog prompts in the universal channel vocabulary → scored against seeded ground truth.
Contamination-free (generated, not scraped), infinitely regenerable, universal. 7-fault taxonomy;
the genuine leak-vs-dead-time degeneracy is scored with acceptable-sets (separating them needs a
battery-voltage sweep — the same doctrine as the real logging plan).

**v1 numbers (70 cases):** rules baseline **85.7% top1 / 100% acceptable** vs random
**18.6% / 25.7%** — a 74-point spread; the eval discriminates. The future LLM evaluee must at
least match rules. **40 car tests green** (5 eval + 4 adapter tests added).

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
| 2026-07-03 | Pipeline test suite | 27 passed (0.5 s) | incl. phpBB/vBulletin/XenForo/INI fixture tests |
| 2026-07-03 | Sim-eval: rules baseline | 85.7% top1 / 100% acceptable | 70 cases (10×7 faults), two-point signatures, seed 0 |
| 2026-07-03 | Sim-eval: random baseline | 18.6% top1 / 25.7% acceptable | chance floor — 74-pt spread vs rules = eval discriminates |
| 2026-07-03 | car/ecutune test suite | 40 passed (1.8 s) | + semantic-adapter tests + sim-eval tests |
| 2026-07-04 | RTX 3090 Ti VRAM (GDDR6X) plateau | 92–94 °C | 30-min memtest_vulkan, 446 W, SM+mem 100%, cover on, fans ~4300 RPM, inlet 21 °C |
| 2026-07-04 | RTX 3090 Ti junction (hotspot) plateau | 88–89 °C | same soak; no throttle (held ~1950 MHz boost) |
| 2026-07-04 | RTX 3090 Ti core plateau | 76–77 °C | same soak; power-limited at the 446 W cap, not thermal |
| 2026-07-04 | RTX 3090 Ti vs OEM 3090 | 94 °C @ 446 W vs 100 °C @ 335 W | Ti's aftermarket cooler far better — no repad needed for the Ti |
| 2026-07-04 | Dual-card soak (both loaded, ~780 W) | 3090 VRAM 100–102 °C, Ti 92–94 °C | 20-min memtest_vulkan both cards; fans ~4680 RPM near max; inlet 21 °C — chassis adds only ~2 °C, the 3090's pads are the limiter |
| 2026-07-04 | 3090 undervolt (PL 300 W, from 350) | VRAM 102→98 °C | but memtest bandwidth ~800→~600 GB/s (~20%); core cap can't cool GDDR6X's fixed power → repad is the real VRAM fix |
| 2026-07-04 | 3090 Ti undervolt (PL 400 W, from 450) | ~862 GB/s (vs ~872 full) | near-zero perf loss — the Ti has the headroom; keep it capped for heat/noise |
| 2026-07-04 | ROM harvest (RomRaider, cookie-gated) | 10/10 attachments, 0 blocked | incl. 2005 FXT 4EAT stock ROM CID 3B12504206 (internal id A2WC411D) + SHA1 manifest |
| 2026-07-04 | NASIOC first ingest | 3 threads kept / 261 posts | cf_clearance + pinned home-browser UA; 5 tuning subforums enabled for nightly discovery |
| 2026-07-04 | ROM-seeded idle convergence | PASS: +12.68% → +4.46% in 4 iters, 0 clamp violations | believed = real A2WC411D values (503.93 cc/min, 0.661 ms @14.1V, 700 rpm idle target); truth = neutral swap-error priors; synthetic control +14.18% → +4.56% |
| 2026-07-05 | Judge inference (27B Q8, dual-GPU, MTP) | ~64 tok/s decode, 1282 tok/s prefill, draft acceptance 0.73 | Qwen3.6-27B-MTP Q8_0 split across 3090+Ti, before crash; ~40 s/doc end-to-end |
| 2026-07-05 | Slot-3 Bus Fatal MTBF, unlocked clocks | 4/4 crashes ≤7 min under bursty inference | steady memtest 30 min passes; reseat/ASPM/dual-PSU/P2P eliminated; link pristine to last second (flight recorder) |
| 2026-07-05 | Locked-clock stability (3090 @1395 MHz) | 15/15 requests, ~13 min, 0 PCIe events | solo Q6_K bench, 51.8 s/req; identical verdicts ×15 (temp-0 determinism); fix persisted via gpu-powerlimit.service |

*Add rows as benchmarks/evals/training runs produce numbers — GPU thermals, inference
throughput/latency, fine-tune eval scores, corpus size/quality, tuning-loop convergence.*
