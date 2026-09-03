# MLECU: Decision Log

Append-only. Records material choices and especially **divergences from the bootstrap soft-foundation**
(per the brief: the *facts* and the *safety architecture* are fixed; the *approach* is mine to refine,
with reasoning logged here).

---

## 2026-06-22: Bootstrap & initial structure

### Invariants carried forward (not decisions to revisit, recorded for clarity)
- **Safety architecture is fixed:** the LLM reasons/proposes; deterministic, hard-clamped,
  human-reviewed algorithms execute all ECU writes; the LLM never writes ECU values directly.
- **Answer-mode scope:** technology-domain questions only; decline/redirect non-tech.
- **Facts** in `context/` (hardware, vehicle config, verified state) are authoritative.

### Divergences from the package `ARCHITECTURE.md` / brief (with reasoning)
1. **Repo root `~/Shared/Computing Projects/MLECU/`, not `~/MLECU/`.** Syed keeps active projects under
   the Samba-shared Computing Projects dir (laptop-editable via the `S:` mount) alongside UMDPlanner +
   Hardware Parser. (Interview, 2026-06-22.)
2. **Directories scaffolded with stub `README.md`s, not left empty.** git doesn't track empty dirs;
   stubs make each area self-documenting and committable now.
3. **`principles.md` kept unified, optional `market-intelligence.md` split deferred.** The file isn't
   large; avoid premature fragmentation. Revisit if the market/pricing material grows.
4. **No `archive/` directory.** The June 11 files (`master-context.md`, `bootstrap-architecture.md`)
   are not present anywhere under `/home/syed`: nothing to archive.
5. **`context/hardware-state.md` refreshed to verified reality.** The OEM 3090 enumerates and the
   driver is up (580.159.03 / CUDA 13.0); §5 updated from "in progress" to verified. The
   mem-junction-**under-load** temp is still unmeasured → **the OEM-3090 repad decision remains
   deferred** (unchanged).
6. **ZFS deferred** (per Syed, not near-term). Storage/HBA work parked.
7. **Learning/collaboration mode added** to the root `CLAUDE.md` + `principles.md` §9. This is a
   learning project: the LLM/ML stack + fan-curve calibration are *learning-priority* (teach, don't
   auto-complete); parsers + deterministic algorithms are *build-priority* (build, then explain).
   Never "just do everything." (Interview, 2026-06-22.)
8. **The two scrapers explicitly disambiguated.** The in-scope LLM-corpus scraper (`ml/data-pipeline/`)
   vs the external, out-of-scope hardware-deal scraper (`~/Shared/Computing Projects/Hardware Parser/`).
   Documented so they're never conflated.
9. **Git: local + private GitHub remote** under `directsyed` (interview). The repo holds
   hardware/network specifics + a secrets concern → secrets are gitignored; a sanitization pass is
   required before any future public flip.

### Provenance
- Two-commit initial history: (1) the verbatim bootstrap package as received, (2) the generated structure.

### First work thread (sequenced, per interview)
1. Close out GPU/server bring-up (fan curve + mem-junction-under-load).
2. Build the LLM-corpus data scraper.
3. LLM-judge curation engine.
(Car domain dormant until a wideband is acquired.)

---

## 2026-06-22: Fan control + thermal-monitoring toolchain

- **Chassis fans run in iDRAC manual mode via a closed-loop daemon** (`infrastructure/server/gpu-fan-control.sh`), not iDRAC auto. Reason: the iDRAC is structurally blind to the third-party 3090 and maxes the fans in auto; the daemon ramps the 2 shroud fans off a GPU-core curve (`max(gpu,cpu)`), with revert-to-auto as the dead-man's switch. PWM→RPM calibrated (~46 RPM/%); curve to be revised after the soak.
- **Mem-junction temp read method = direct BAR0 register reader, not nvidia-smi.** NVML doesn't expose GDDR6X junction temp on GeForce. Chosen tool: `ThomasBaruzier/gddr6-core-junction-vram-temps` (`gputemps`; core+junction+VRAM, 3090-tested, `--json`). Requires `iomem=relaxed` (Secure Boot N/A, legacy boot). Resolves the previously-flagged "how do we read mem-junction on Linux" blocker.
- **Repad-decision soak: memtest_vulkan primary** (hardest junction heat + apples-to-apples with the prior 106 °C Omen reading), **gpu-burn secondary** (compute load / real-workload proxy). Run with the fan daemon active so one soak validates the curve *and* yields the junction number. The repad decision itself stays deferred until that number exists.

---

## 2026-06-22: Repad decision (data-backed) + soak-logger abort fix

- **Repad: DEFERRED, not urgent.** In-chassis 5-min memtest_vulkan put **VRAM (GDDR6X) at 100 °C** peak (hotspot 94, core 79; ~335 W, 22 °C inlet), under the 110 °C ceiling, no throttle, no errors, and ~6 °C cooler than the Omen's 106 °C. Decision: don't repad now. Preferred next lever = **add chassis fans (being sourced) + re-soak** (fans were already ~94%, near the 2-fan airflow ceiling); repad is the fallback if VRAM won't drop under ~95 °C or the card runs in a hot room / 24-7. Data in `infrastructure/monitoring/memtest-soak.csv`; numbers in `PROGRESS.md`.
- **Column semantics (from gputemps source):** `junction` = GPU hotspot (`HOTSPOT_REGISTER`), `vram` = GDDR6X memory (`VRAM_REGISTER`). The **VRAM** column is the repad-relevant memory temp.
- **soak-logger auto-abort corrected:** it originally watched `junction` (hotspot) + `core` but not `vram`: the temp nearest its ceiling and the whole point of the soak. Now aborts on **vram** ≥108 too (the GDDR6X 110 °C ceiling, less 2 °C margin). The run that surfaced this was safe (100 < 108).
- **gpu-burn dropped (was the "secondary" soak tool), unnecessary.** memtest_vulkan already pinned the 350 W power cap (so gpu-burn can't add total heat), gave the worst-case VRAM (gpu-burn heats memory less), and the card's compute/core stability was already validated in the Omen (OCCT 3D-Adaptive + FurMark). The real forward-looking validation is an actual inference/training run with the fan daemon + abort live, not another synthetic. gpu-burn stays cloned-unbuilt in `~/gpu-tools/`; build it for free if/when the CUDA toolkit lands for the ML work and a pure-compute datapoint is ever wanted.

---

## 2026-06-23: Data pipeline design (refines project-purpose §6-7)

- **Corpus built to serve BOTH consumption modes; RAG-vs-fine-tune deferred to the held-out eval** (`ml/eval/`). Working hypothesis: *retrieve* precision-critical exact values (ECU tables/specs/scalars, the same numbers `car/safety/` needs), *fine-tune* reasoning + conceptual theory. Rationale: LLMs recall exact numbers from weights unreliably (interpolation/interference) and a confident near-miss value is engine-grenading, the **data-layer mirror of "LLM never writes ECU values."** (Decided with Syed after he correctly noted the "RAG = fresh data" argument doesn't apply to a static 2005-Subaru domain; the real driver is precision/verifiability, not freshness.)
- **Fine-tune set sizing revised: 500–2,000 reasoning exemplars (pilot ~500–1,000), NOT the bootstrap's 10k–50k.** "Less is more" (LIMA/QLoRA); 500 clean > 5,000 noisy; quality is also a *safety* property here. The retrievable fact store can be large.
- **Quality over quantity, decisively.**
- **Pipeline mirrors the Hardware Parser infra conventions**: config-driven source registry, `fetch()`+`REGISTRY`, sqlite WAL dedup on `(source,source_id)`, tenacity HTTP client, systemd oneshot/timer, **copied, not coupled** (no runtime dependency; the external scraper is untouched). `matcher.py` (deal logic) → our `gates.py` + the LLM judge.
- **Model selection (Stage B/C, does not change the corpus):** for ~48 GB (2×3090), **~32B at Q5/Q6** (context/KV headroom + practical QLoRA) over a cramped **70B-Q4**; **pilot at 7–14B**. Dataset size + retrieval method are model-agnostic.
- **Forums:** hit at normal pace, adaptive backoff only if blocked (per Syed); `requests`+`bs4` first, `patchright` fallback for Cloudflare/JS.
- **First slice shipped:** `romraider_defs` → 333 Subaru ECU definitions in `corpus.sqlite`.

---

## 2026-06-26: EFI-reference corpus + judge architecture (no circularity) + PID note

- **Document `tier` field added:** `reference` (trusted/authoritative) vs `community` (noisy, needs judging). Tagged: RomRaider defs+logger, rusEFI docs, FSM/book PDFs, `ecu_docs` → **reference**; forums → **community**. Corpus now ~883 reference + 27 community.
- **`ecu_docs` source (HTML, reference tier):** the **MegaSquirt MegaManual** fundamentals (fuel equation `PW = REQ_FUEL × VE × MAP × E + …`, VE, tuning, injectors). PRIVATE-corpus use only (copyrighted, not redistributed). **rusEFI already covered** by `rusefi_docs` (its GitHub wiki = the same 387-file repo); **Speeduino redundant**; **AEM/Haltech skipped** (gated behind software + shallow public algorithm depth). Scope = "Open + MegaSquirt" (Syed).
- **Judge architecture, non-circular by construction (resolves Syed's concern):** the judge is a strong **general** model (Qwen2.5-32B), **NOT trained on the corpus it filters**. One-directional flow: raw → judge → curated → fine-tune the *main* model. The judge **grounds** noisy `community` claims against the `reference` tier (retrieved, not baked in), "is this consistent with the rusEFI / MegaManual / FSM spec?" If a domain judge is ever fine-tuned, train it **only** on the reference tier, never the community tier it filters ("train-on-trusted, filter-untrusted"). + 5% human spot-check.
- **Judging deferred to the 48 GB (2×3090) setup** (a ~32B Q5/Q6 judge); the corpus accumulates until then.
- **PID note (refines the pending algorithm-layer build):** idle Stage-2 = feedforward table correction (the ECU's own closed-loop fuel PI tracks AFR in real time); the iterative `log→correct→reflash→re-log` loop = a **bounded-integral controller** (±3% clamp = anti-windup/rate-limit, designed as a damped PI to avoid overshoot); **boost control (Stage 3) is a real PID we tune**, informed by the rusEFI/ECUMaster boost-PID docs now in the corpus.

---

## 2026-06-27 - car/ecutune: deterministic algorithm + safety layer (offline build)

Built the offline tuning-algorithm + safety-clamp layer (`car/ecutune/`). Design choices, with reasoning:

- **Packaging: a self-contained `car/ecutune/` package + its own `.venv`/`requirements.txt`** (numpy, hypothesis), zero runtime import from `corpus_pipeline`: the scraper venv stays stdlib-lean ("copied, not coupled", same rule as vs Hardware Parser). Log-parser submodule named **`logparse`** (not `logging`) to avoid shadowing the stdlib.
- **Single write path: `safety.apply_proposal()`** is the only function that mutates a Table, enforced by a source-scan meta-test (no `.values[...] =` or `.with_edits(` outside `safety/` + `core.models`). This makes "the LLM never writes ECU values directly" *structural*, not a convention, the LLM becomes just another `Proposal` producer through the same clamp pipeline.
- **Clamp order, AFR floor runs LAST, after the ±3% rate-limit.** Lean-at-boost is the engine-grenade case, so the AFR floor is the final hard word on a boost AFR cell and is the one clamp permitted to richen past the per-iteration rate-limit (rich = safe; the rate-limit still bounds every *leaning* move). Full order: knock→ordering gates→boost gate→timing ceiling→ve-rate-limit→afr-floor.
- **Idle scalars are degenerate at one operating point.** Injector latency / flow-scaling / low-MAF all shift idle fuel, so the algorithm corrects the NET fuel error via the bounded controller and splits it by fixed priority weights (latency 0.2 / flow 0.7 / MAF 0.1, "latency-first" lives in config, not physics). The loop converges *trim* to ±5%; the scalars settle at one of many trim-zeroing combinations (final flow ≈800 vs true 820, fine, trim is the objective). Flagged for Syed: separating the scalars individually needs a log spanning a voltage/load range, not just idle.
- **Controller = bounded-integral / damped PI; the ±3% clamp IS the anti-windup** (conditional integration freezes the integral while saturated). Gains kp0.5 / ki0.05 / damping0.7 (~0.8% overshoot). The controller self-limits below ±3%, so the clamp never fires in normal operation (zero violations); it is the backstop for a misbehaving proposer (incl. the future LLM).
- **MVEM fidelity: mean-value, steady-state, idle-fuel only.** No combustion/knock physics/transients; knock is a scripted test state for the abort clamp. Seeded mismatch (believed flow 850 vs true 820, latency 0.95 vs 1.0, MAF 0.98 vs 1.0 → +14.8% trim) is illustrative, flagged for Syed to set from the real swap. `synth_log` emits the exact `LogTable` shape `logparse` parses, so real logs replay through the same path when the wideband arrives.

---

## 2026-06-28: Forester build spec locked; idle mismatch reframed (injectors MATCHED)

Syed provided the real build (recorded in `car/build-sheet.md` + `car/CLAUDE.md`): the swap keeps the
**entire OEM 2005 FXT intake manifold + injectors + wiring harness** on the OEM FXT ECU. This
**reframes the bad-idle theory** and the sim:

- **Injectors are OEM FXT side-feed ~500 cc/min, MATCHED to the stock ROM.** So injector scaling &
  latency are already correct; the earlier "injector scaling/latency" idle theory is **wrong for this
  build**. With matched injectors + MAF metering, the MVEM's delivered fuel equals the ECU's target and
  the idle fuel trim reduces algebraically to **1/maf_ratio − 1**: a *pure MAF-calibration error*
  (from the modified intake tract). Re-seeded `simulation/mismatch.py`: injectors matched (500 cc /
  1.0 ms), MAF believed 0.88 vs true 1.0 (~12% low) → +13.6% start trim. Harness now uses
  `BUILD_SPLIT = ScalarSplit(0,0,1)` so the correction goes entirely into MAF scaling; injector scalars
  stay put. Converges to <5% in 4 iters, 0 clamp violations, 31 tests green.
- **The real idle problem is engine-side, not fuel scaling:** 2.0 L-on-2.5 L VE/load model; exhaust-AVCS
  delete + TGV delete (overlap + low-rpm stability); timing too advanced for the 9.5:1 CR on 93 oct
  (EJ255 ROM is 8.4:1). These are **not fuel-trim errors** and are out of scope for the mean-value FUEL
  model; they need real logs + a richer model. Documented so the sim isn't over-trusted.
- **Corpus/forum grounding:** searches for this build should use EJ20X-into-FXT, OEM-FXT-manifold/injectors,
  TGV-delete, fully-catless, intake-AVCS-only, feeds the judge/retrieval later.
- **Best ROM source = read his own ECU** with the Openport (read-only, safe, no wideband needed) → exact
  factory calibration + the ROM ID. Community 2005 FXT stock ROMs also exist on the RomRaider forums
  (4EAT vs MT differ). A stock ROM upgrades the sim SEED to real numbers; it does not replace logs for
  *validation* (the ROM is what the ECU assumes, not how the EJ20X actually breathes).

### 2026-06-28 (revised same day, with Syed): keep ALL fuel levers live; the data sets priorities

Correction to the note above. Syed's directive: do NOT exclude fueling or pre-prioritize any lever -
"everything most likely needs modifying, and reading the car is how we see what to prioritize." He is
right, and it's reinforced by the degeneracy I'd just identified: at one idle point a MAF error and an
injector error are indistinguishable in the trim, so locking the injectors (`BUILD_SPLIT = 0/0/1`) was
asserting a conclusion the data hasn't earned. **Reverted:** `ScalarSplit` default is now NEUTRAL
(0.34/0.33/0.33; no prioritization, still configurable once logs inform it); `mismatch.py` seeds error
across ALL fuel levers (latency 0.96, flow 510, MAF 0.93 vs truth 1.0 / 500 / 1.0); the harness uses the
neutral split. All three scalars now move; converges +14.2% → 4.6% in 4 iters, 0 violations, 31 tests
green. Real per-lever attribution, and the cross-axis priorities (fuel vs timing vs AVCS vs idle-air) -
come from logs across operating conditions, which is the whole point of reading the car. Transmission
confirmed **4EAT** (fixes the ROM variant).

---

## 2026-07-03: Universal-first corpus expansion + model-selection policy

**Context:** Syed's directive, the framework foundation is UNIVERSAL (every ECU exposes MAF/trims/
ECT/RPM/timing/VE, the SAE J1979 vocabulary); specificity layers on top. And: add every source not
yet ingested. Full review delivered in-chat (improvement map: semantic table layer, judge upgrades,
sim-generated eval, logged as follow-ups).

**Source expansion (built + live, 4 new sources + 1 gated):**
- **One generic phpBB engine** (`forum_phpbb.py`, bound per-site via `fetch_for()`) now serves THREE
  boards: `forum_speeduino` (universal open-EFI reasoning), `forum_msextra` (MegaSquirt theory),
  `forum_romraider` (Subaru tuning/logging/defs + stock-ROM threads; seeded with the 2005 FXT 4EAT
  stock-ROM thread). *Divergence from plan:* speeduino.com turned out to be phpBB, not Discourse
  (probed before building), which collapsed two planned engines into one.
- **`tunerstudio_ini`**: speeduino.ini → 55 cross-platform table/curve definitions (reference tier) -
  the universal table vocabulary that will anchor the future semantic table layer.
- **`ecu_docs` + obd_pids**: Wikipedia OBD-II PIDs page (SAE J1979), the universal channel anchor.
- **Wideband manuals**: AEM 30-0300 (+30-0310 inline, +FAE variant) PDFs → `local_pdf` (36 pages).
- **`forum_nasioc`: built but DISABLED**, NASIOC's Cloudflare managed challenge does not clear
  headless even with a new challenge-retry loop in BrowserFetcher (improvement kept; benefits
  legacygt). Revisit via one-time non-headless run or browser-cookie import.
- **ROM/log binary attachments need forum accounts** → Syed downloads manually into
  `data/raw/roms/` (gitignored); sources capture thread text/metadata only.
- Corpus after expansion: **1,026 docs (976 reference / 50 community)**; daily timer now accumulates
  from three new boards passively. 22 pipeline tests green.

**Model-selection policy (the durable lesson):** model choices are RE-VERIFIED against the current
landscape AT EXECUTION TIME, never asserted from training memory. (Syed caught the planned
Qwen2.5-32B judge being two generations stale. Qwen3.6 released 2026-04, after the agent's cutoff.)
- **Judge (as of 2026-07): Qwen3.6-35B-A3B at Q8_0**, MoE (3B active) lets Q8 run TODAY on the
  single 3090 + 32 GB RAM via llama.cpp expert offload; batch/overnight posture makes speed
  irrelevant. Dense alternative: Qwen3.6-27B (Q6 borderline on 24 GB; Q8 on 48 GB).
- **Quantization floor (Syed): Q6 minimum, Q8 preferred** for inference. (QLoRA's frozen NF4 base is
  a training-method standard, not subject to this floor.)
- **Fine-tune base (pilot): Qwen3.6-27B**, re-verify at pilot time.
- RAM pricing correction: the earlier $15–25/32GB DDR4 RDIMM figure was stale, prices rose with AI
  demand. RAM buy deferred to opportunistic (Syed watches for lots); NOT blocking: the judge fits
  the current 24 GB + 32 GB. **RAM spec for the parser: 32GB DDR4-2400 ECC RDIMM 2Rx4 PC4-19200
  288-pin 1.2V** (runs 1866 now on the v3, 2400 after the v4 swap; RDIMM not UDIMM/LRDIMM).

### 2026-07-03 (cont.): XenForo forums + BrowserFetcher hardening; NASIOC gated

- **XenForo engine** (`forum_xenforo.py`, per-site bindings) → **forum_subaruforester** (Syed's exact
  chassis, engine-management-tuning-and-datalogging + EJ25-turbo-2004-2013 + EJ20-turbo nodes) and
  **forum_iwsti** (STI tuning). Both are VerticalScope boards behind a 202 JS stub → BrowserFetcher.
  Verified end-to-end (40-thread listing, a 20-post thread parsed with authors/dates).
- **VerticalScope is SLOW** (~25 s/page, the JS challenge clears in <9 s but ad-trackers keep
  networkidle from ever settling, so each page waits out a non-fatal timeout). Kept per-page timeout
  at 25 s + tight caps (discover_max_new 3, discover_max_pages 1, **max_thread_pages 3**) so nightly
  runs stay bounded; a full foreground `--once` exceeds a few minutes, which is fine for the systemd
  timer. **Lesson: do NOT reload-loop per page in the fetcher**, it multiplies the per-page cost on
  slow-challenge boards; single-pass non-fatal goto + wait_selector is correct.
- **BrowserFetcher hardening (shared, benefits legacygt too):** `wait_until` param (networkidle vs
  domcontentloaded), non-fatal goto, CF-interstitial re-read loop, and cookie injection. A
  persistent-context experiment rendered an empty body here and was reverted, kept launch()+new_context().
- **NASIOC: built, enabled, but cookie-GATED.** Confirmed its Cloudflare managed challenge cannot be
  cleared headless (persistent stealth ctx + interaction + reload all return the identical block).
  Path: cf_clearance cookie exported from Syed's home browser (same public IP as the T630 → valid)
  into `data/raw/.cf-cookies/nasioc.json`; `require_cf_cookies` auto-activates it once present.
- Sources now: 12 registry keys (6 forums + defs/logger/theory/efi/ini/pdf). 27 pipeline tests green.

### 2026-07-03 (cont.): semantic table layer + sim-generated eval (autopilot queue)

- **Semantic table layer (car/ecutune):** algorithms + clamps now speak ONLY platform-neutral
  semantic IDs (`fuel.injector_flow`, `fuel.injector_latency`, `sensor.maf_transfer`,
  `fuel.target_afr_primary_a`, `ignition.*`, `boost.*`); platform names live in
  `ecutune/platforms/` adapters. `subaru_ecuflash` maps to the verified 2005 FXT (A2WC400x) names
  with VARIANTS absorbing per-def drift ("Injector Latency" vs "Injector Latency_"); a second
  `tunerstudio` adapter (injOpen/reqFuel/advTable1Tbl) proves the seam, with speed-density gaps as
  honest absences. Subaru is adapter #1 on a universal foundation, the structural encoding of
  Syed's universal-first directive. 35→40 tests green; convergence PASS unchanged.
- **Sim-generated diagnostic eval (ecutune/evals + ml/eval/data):** faults seeded in the MVEM
  (extended with `leak_air_g` unmetered air + `air_scale` operating points) → two-point datalog
  prompts in the universal channel vocabulary → scored against seeded truth. 7-fault taxonomy;
  leak-vs-dead-time degeneracy handled with acceptable-sets (separating them needs a voltage
  sweep, same doctrine as the real logging plan). **v1 artifact: 70 cases; rules baseline 85.7%
  top1 / 100% acceptable; random 18.6% / 25.7%**, the eval discriminates, and the future LLM
  evaluee must at least match rules. Eval DESIGN decisions (thresholds, taxonomy growth,
  RAG-vs-fine-tune protocol) stay Syed's learning thread.
- **Autopilot stop point:** queue complete up to the judge design session (learning-priority -
  not auto-built, per the root CLAUDE.md split).

### 2026-07-03 (cont.) - ROM-binary harvesting: attachments are gated, cookie is the key

Investigated login-free ROM sources per Syed ("shouldn't be trapped behind a login"). Findings:
archive.org has no Subaru ROM collection; GitHub has tuning *tools* but no ROM-binary repos;
SubaruDefs is defs-only. **RomRaider thread text is public but the attachment download 403s for
guests** (verified). So bulk ROMs realistically live as forum attachments behind a one-time login -
not an unbreakable wall, a cookie. Built **`rom_harvest.py`**: crawls the same phpBB threads we
already scrape, extracts `download/file.php?id=N` ROM attachments (strong exts always; archives only
if the filename hints a ROM), and downloads them **authenticated by a session cookie the user exports
once** into `data/raw/.cookies/<board>.txt` (same pattern as NASIOC cf_clearance). ROMs are car-side
files under `data/raw/roms/` + a manifest, NOT corpus Documents (binaries, and they feed the
ROM-value reader / reference library, not the LLM text corpus). CLI `--harvest-roms`; gated so it
skips cleanly (with guidance) until the cookie exists. Docs: `ml/data-pipeline/ROM_HARVEST.md`.
**The 2005 FXT 4EAT stock ROM (3B12504206) is attached to the seeded RomRaider thread**: Syed's
exact platform calibration, one cookie away. 31 pipeline tests green.

### 2026-07-04: ROM-value reader + the sim grounded in the REAL FXT calibration

Both cookie gates opened today (NASIOC cf_clearance + RomRaider phpBB session) → `rom_harvest`
pulled 10/10 attachments including **the 2005 FXT 4EAT stock ROM (CID 3B12504206)**. Extracted the
1MB image from the EcuFlash `.srf` (INFO/DRMI/MEML/MEMD block container; MEMD = the ROM), internal
ID at 0x2000 says **A2WC411D**, a revision with **no community def anywhere in SubaruDefs**.

**Decision: read via sibling revision defs with deterministic reconciliation, never guessing.**
New READ-ONLY `car/ecutune/romread/` (ECUFlash def parser incl. include-chain merge + value
reader). Empirical finding that shaped it: A2WC412D's late-ROM addresses are shifted +0x20 vs our
ROM (its latency read is non-monotonic garbage), while every A2WC410D read is physically sane →
411D shares the 410D layout. Rule codified in `read_semantic_tables()`: per table, defs that read
bit-identically corroborate; where they disagree, a candidate survives only if its axes are strictly
monotonic AND values sit inside the def's own min/max, and the survivor must be UNIQUE, else hard
error. Provenance is reported per table (`agree(...)` / `plausible-only(...)`).

**Decision: the sim's believed state now comes from the real ROM** (`simulation/rom_seed.py`,
CLI `--run-convergence --rom` / `--rom-report`). Believed = ROM facts: injector flow **503.93
cc/min** (the "~500cc matched injectors" prior is now a measured fact), latency curve interpolated
at 14.1V charging = **0.661 ms** (vs the 1.0 ms guess), hot idle target from the ROM's own table =
**700 rpm** (vs the 850 guess). Truth keeps the SAME neutral swap-uncertainty ratios as
`ej20x_into_ej255` (MAF ~7% low, flow ~2% high, latency ~4% low; no pre-decided culprit),
expressed relative to the real values. Result: **ROM-seeded convergence PASS** (+12.68% → +4.46%,
4 iters, 0 clamp violations) alongside the unchanged synthetic control (+14.18% → +4.56%). The
start-trim difference is physical: a 4% latency error on the real 0.66 ms dead time is a smaller
absolute fuel error than on the assumed 1.0 ms. 44 tests green (4 new romread).

No write path exists in romread by construction, ROM writes stay behind safety.apply_proposal.

### 2026-07-05 - Slot-3 Bus Fatal incident: locked GPU clocks are now mandatory on syedlab

Four hard system hangs during the first real judge inference runs (box alive, NIC dead, the
fatal PCIe error takes the root complex and the kernel's ability to log with it; only the iDRAC
SEL recorded each event: `Critical Interrupt. Bus Fatal Error (Slot 3)` x4).

**Eliminated one variable at a time:** cf. sessions/handoffs. Dual-PSU load sharing (crash #2
happened anyway), ASPM/link power management off via kernel params (crash #3), full physical
reseat of the 3090 (crash #4), cross-socket GPU P2P (crash #5 was SOLO on the 3090; no P2P
traffic existed). A 1 Hz fsync'd flight recorder (infrastructure/monitoring/pcie-flight-
recorder.sh) proved the link was PRISTINE to the final second every time: Gen3 x16, zero
replays, zero correctable errors, instant fatal, no prelude. Firmware-first AER (Dell) is why
the kernel never saw anything.

**Mechanism (confirmed by discriminating experiment):** boost clocking oscillates the card
against its power limiter (recorded: 1065<->1500 MHz at 299W/300W cap) -> current transients
through slot 3's 12V -> momentary brownout of the card's PCIe logic -> one poisoned transaction
-> Bus Fatal. Steady loads never trigger it (30-min memtest soaks pass); bursty LLM inference
does. **With GPU0 core pinned at 1395 MHz: 15/15 bench requests, ~13 min sustained, zero
events**, nearly 2x the longest unlocked survival. Cost ~nil (inference is memory-bound; mem
clock untouched at 9501 MHz).

**Standing config:** gpu-powerlimit.service now also locks clocks at boot (GPU0 1395, Ti 1560).
Do NOT unlock without re-testing slot 3 under bursty load with the flight recorder armed.
**Open attribution:** card's transient appetite vs slot 3 board-side power delivery, settled
someday by swapping the cards between slots; not blocking (locked clocks are a legitimate
permanent operating mode; datacenter GPUs ship clock-capped for the same reason).

Bonus finding from the incident benches: temp-0 judge determinism is real, 15 identical
verdicts (score + token count) on identical input.

### 2026-07-06 - CARD CONVICTED: slot-swap test ends the Bus Fatal investigation

Crash #9 settled it. Full card swap (3090 -> CPU2 slot 7; Ti -> slot 3, RAID pins cleared):
provoked run (locks reset, caps kept, the historical trigger recipe) killed the box in ~40s of
load, SEL reporting **Slot 7**: the fault followed the HP OEM 3090 across the chassis while
the Ti boosted to 1890MHz in slot 3 in perfect health. Black box: 3090 bouncing 1575-1800MHz
at 269-273W (limiter oscillation), link clean to the last sample. Slot 3 exonerated after
eight wrongful accusations. Verdict: the card's own power-delivery/PCIe interface electronics
glitch under its own load transients.

**Supporting color:** Syed found the card's backplate screws show tamper evidence (paint
chipping/slight stripping), someone was inside this card before purchase. Repad upgraded to
forensic teardown: document prior-rework evidence (flux residue, mismatched pads), inspect
12V input filtering + the six backside cap groups (the 2020 GA102 POSCAP/MLCC boost-crash
story matches our signature exactly), measure old pad thicknesses, clean/inspect edge fingers.

**Interim ops (Syed's option C):** dual-GPU batches at deepened margin, 3090 core lock
1200->1000 (measured load draw 215W vs 300W cap; limiter mathematically unreachable), Ti
unchanged. UUID-targeted service (slot-proof after the index-swap incident). Batches resume
via documented one-liner after each crash; DB snapshotted per stint; ~5-6h+ MTBF expected.
Endgame: repad/inspect the 3090, re-test with the 1-minute provoked-crash diagnostic, then
repair/retire/replace decision.

### 2026-07-22: pilot-mix-v3 SIGNED (training set of record) + QLoRA goes fully hands-on

**Syed signed pilot-mix-v3** (280 pairs = 70 organic + 210 synthetic, 100% Claude-full-read,
drop audit ml/curation/docs/pilot-mix-v3-drops.txt). It is THE arm-C training set. Reviewed
via the new readable exports (claude.ai artifact viewer + pilot-mix-v3-readable.txt).
Known shape, accepted: synthetic split 20 subaru / 190 modern_general. Subaru weight rides
on the 70 organic + those 20; more pairs come post-wideband (Stage C gold). Wideband status:
power/ground wired, serial connections remain; Syed finishes computer side first.

**QLoRA plan change (supersedes 07-16 handoff):** NO autonomous prep. Syed runs every command
end-to-end (dataset prep -> train -> merge -> eval C), Claude teaches. His words: the judge
and RAG tests were agent-built; this one he needs to own. Memory: qlora-syed-drives.

### 2026-07-22 - gone-sweep policy RATIFIED (Syed): NARROW

Gone-ness (`gone_at` stamped when the live thread 404s) affects **scraping only**: never
judging, retrieval, or pair-mining. Archived judged text remains first-class corpus material
forever. Evidence: community batch 4 deliberately included gone-marked threads and produced
the best pair density of the synthesis effort (forums prune old threads; old correlates with
resolved). No cleanup pass may purge or exclude gone-marked docs from training/eval use.

### 2026-07-22 - E1v2 bar re-ratified (Syed): 90% top-1 + zero dangerous misses

Original A1 wording ("90% top-1 AND 100% acceptable") is degenerate on v2 where
acceptable==exact. Syed asked the right question, could the allowed 10% hide catastrophic
misses? Empirical audit of all 588 scored v2 cases: every miss was lean-family answered as a
different lean-family fault; zero fault->healthy, zero lean<->rich flips, misses byte-stable
across runs (temp-0 blind spot, concentrated on injector_latency_lean). New bar: **90% top-1
AND zero dangerous misses** (dangerous = fault answered healthy, or cross-family lean/rich
flip), the E2-hard-gate analog for diagnosis. Doesn't change A/B verdicts; binds C/D.
DB meta eval.e1v2.preregistration amended with full definition + provenance.

### 2026-07-22: parked-doc queue cleared (Syed rulings)

Docs 1194 (Vizard p57, SU-carburetor prose) + 5748 (Kirkpatrick ch26, Matlab combustion-sim
appendix) -> **rejected_manual** (new explicit status; rubric_version=manual-syed-2026-07-22
- kept out of judge stats, fully auditable). Doc 5781 (LGT self-tune mod thread, 300 posts,
subaru/tuning_signal/gone-marked) -> **re-queued pending**: its 07-05 "runaway deliberation"
failure predates the 07-09 thinking-budget fix (8192); never actually judged bad. Rides the
next routine judge batch (333 pending) AFTER tonight's training frees the Ti.

### 2026-07-22 - arm C/D base model ratified (Syed): Qwen3.6-27B, 4-bit QLoRA on the Ti

Re-verified at execution time per policy: Qwen3.6 family is 27B dense + 35B-A3B MoE only
(no small siblings). Decisive argument = experimental design: arms A/B ran on Qwen3.6-27B,
so arm C must be the same base or A-vs-C confounds base-change with fine-tuning. Costs
accepted eyes-open: tight fit (~15-16GB 4-bit base on 24GB, batch 1 + grad checkpointing),
C4 circularity at full strength, ~54GB BF16 download (weights needed for training + merge;
4-bit is training scaffolding only, serving re-quantizes the merged model, Q8 available).
Training single-card on the Ti ONLY (3090 convicted; training load sits above its 152-230W
failure bracket; lockstep would throttle to 810MHz anyway).

Addendum (same evening, Syed's version-identity challenge): checkpoint provenance VERIFIED -
judge GGUF metadata says base=Qwen/Qwen3.6-27B (quantized_by=Unsloth, pulled Jul 4); official
HF repo frozen since Apr 24 (README-only last commit; weights untouched since Apr 21-22
release). BF16 download == judge's source checkpoint == arms A/B model. MTP: speculative
draft head, output-invariant (verify-every-token), part of same checkpoint; unaffected by
LoRA targets; survives merge+requant (worst case: lower draft acceptance = speed only).

### 2026-07-22: dataset-format knobs ratified (Syed) + v3 blank-field catch (Syed's)

Syed skim caught 10 organic pairs with blank symptoms/diagnosis (experiment-log genre from
the Fuel Economy/AVCS threads, change->outcome facts with no symptom beat; organic rows
were never field-completeness-screened). Rulings: (1) STRUCTURAL GATE, formatter excludes
any pair whose user turn would be empty (blank input trains confident-output-from-nothing);
gated pairs stay in the v3 archive as corpus facts. (2) User turn = datalog evidence +
unpinnable observations, no question framing. (3) Assistant turn = explicit structure
(Diagnosis/Change/Expected result), proposal must be extractable (safety mirror).
(4) Training SYSTEM = deployment assistant identity (drafted, pending Syed wording ratify);
eval arms keep their frozen fixture prompt per single-variable protocol. (5) Holdout 10%
stratified (organic | syn:topic), seeded. prepare.py is SYED'S BUILD (scaffold+tests laid).

### 2026-07-25: citation guard built (B-v3); SCORER v1.1 amendment; retro-test findings

**Guard**: harness/citation_guard.py; every number in a stated value must appear in the
retrieved snippets (±1%, [REF n] ids excluded, PDF-mangled digits healed) or the answer
mechanically becomes a decline. Pre-guard class always recorded (attempted/blocked/leaked
gauge). Applied via `--guard` to retrieval arms only. Anti-benchmark-maxxing contract in
docs/PLAN-post-showdown-2026-07-25.md §1 (Syed-ratified).

**Retro-test verdicts (measurement before deployment):** all 13 absent-number fabrications
across B-v1/B-v2 history BLOCKED; 0/26 false blocks on correct answers; exactly ONE
would-leak case (e2-5723-1: model retrieved the right Banish chapter, computed the right
sqrt(50/40) flow physics, rounded 11.8%->11%, outside the 1% tolerance; guard rightly
says "cited"). Per contract: if it recurs in B-v3 the gate stays RED and stands.

**SCORER v1.1 (logged amendment, applied uniformly, originals in git):** the retro-test
caught parse_number mis-scoring CORRECT answers as dangerous: '.84' (leading dot) parsed
as 84; '30 000' (spaced thousands) parsed as 30. Fixed; every historical E2 file re-scored
with both numbers published (PROGRESS.md). Effect: every arm improved where it stated the
true values (B-v2@6: 2->1 dangerous/25->26 exact; C: 45->44; D: 15->14; B-v1: 11->9).
**No hard-gate verdict flipped**: the amendment passes nothing by itself.

**Also fixed (found by the test suite + retro-test):** BM25 tie-order nondeterminism
(ORDER BY bm25, rowid); dense-index cache ignored index_path (now path-keyed).

### 2026-07-25 - B-v3 verdict: gate FAILS by one grounded-rounding case; red stands

E2 with guard (hybrid@6, rider, 2 identical runs): 26/69 exact (best base result),
42 declines, ONE dangerous leak = e2-5723-1 (model retrieved the right Banish chapter,
computed sqrt(50/40) correctly, stated 11% vs expected 11.8, guard rightly "cited").
Per the anti-benchmark-maxxing contract the gate stays RED and the result stands; no
tolerance change from inside this result. Deployment remains blocked per Syed's ruling.
Open options recorded in sessions/handoffs/2026-07-25-citation-guard-execution.md.
Judge batch fixed (venv root cause) and running.

### 2026-07-29 - E2 HARD GATE PASSED (first time): arm B + hybrid@3 + citation guard

**B@3+guard: 19 exact / 0 dangerous / 50 declines / 0 unparseable, hard_gate=PASS.** The one
fabrication the base model attempted was BLOCKED by the deterministic guard (gauge: attempted
1, blocked 1, leaked 0; false-blocks 0). This is the first configuration in the project's
history to clear the pre-committed gate. Honest cost, not hidden: exact-match falls 26 -> 19
(37.7% -> 27.5%) vs B@6+guard, because k3 supplies less evidence. The gate is passed by
DECLINING more, which is the doctrinally correct failure mode but is less useful.
NOT a deployment authorization by itself, E1v2 at k3 is the 93.9/93.2 cell, so the same
config is strong on diagnosis; deployment remains Syed's call.

**Arm D + guard (the question of whether a clamp rescues a fabrication-prone model):
partially, 11 of 14 attempted fabrications blocked, 3 leaked, gate FAILS.** Best exact of
any cell (30/69). The 3 leaks are EXACTLY the blind spot named in advance (plan §1):
 - e2-5723-1: "11 percent" vs 11.8, right doc, right physics, rounding outside tolerance
 - e2-2241-2: "500, 1500, 2500 rev/min" vs 2000; all three numbers present in evidence,
   wrong one selected (present-but-wrong-selection)
 - e2-3838-0: prose with no number at all ("excerpt cuts off"), scored dangerous by the
   scorer, guard verdict no_numbers; arguably a SCORER artifact, not a fabrication.
Verdict per the anti-benchmark-maxxing contract: the residue stands as documented open
problem (needs snippet-level attribution, not another patch). Also: e2-3838-0 suggests
scorer v1.2 should classify no-number prose as unparseable/decline rather than dangerous -
flagged for Syed, NOT changed unilaterally since it would alter a gate verdict.

MTP finding (same phase): back-to-back identical runs ARE 147/147 deterministic; MTP on-vs-off
shifts 9% of answers and 0.7pp of score, and costs 1.92x throughput (89 min vs 171 min per
147-case E1v2). MTP is therefore NOT output-invariant in practice. Showdown runs MTP-off
uniformly; incumbent's matched baseline is 93.2% (not the MTP-on 93.9% of record).

### 2026-07-30 - Ti-first offload policy (Syed): fill the healthy card, spill only the remainder

Syed: "load the 3090 Ti with everything it can handle, put the rest onto the 3090", and
"run all models to their max capability with the underpowered card."

**The flaw he caught:** `--tensor-split 3.5,1` allocates LAYERS proportionally, so on the 35B
MoE it left 16.9 GiB of 3090 VRAM idle while 8.4 GiB of experts streamed from RAM at ~8x
lower bandwidth. My first fix optimized the wrong objective (maximize the idle card's use
within a power budget) and produced a BACKWARDS allocation: 3090 21.7 GiB vs Ti 15.0, the
convicted card carrying the larger share. Syed's rule is the correct objective: MINIMIZE the
convicted card's share subject to fitting the model.

**Implementation:** `tensor_split` is now per-profile. Calibrated MoE profiles use "1,0"
(everything to the Ti) plus `--override-tensor` pinning only the overflow band of expert
tensors (`blk.N.ffn_*_exps.weight`, 0.80 GiB/layer on this model) to CUDA1. The sweep now
starts at the MINIMUM viable 3090 band and steps up only on OOM, instead of starting maximal.
Also fixed: -ncmoe and -ot are competing placement policies; keeping both left 8 GiB on CPU
while the -ot band moved to the 3090, leaving total VRAM residency unchanged. -ncmoe is now
stripped when -ot is used.

**Measured (35B-A3B, 41 expert layers):**
| config | 3090 share | 3090 power | 6-case probe |
|---|---|---|---|
| conservative 3.5,1 + ncmoe12 | 7.6 GiB (22%), 8.4 GiB in RAM | 117 W | 49.3 s/case |
| proportional -ot17 | 21.7 GiB (59%) | 143 W mean | 14.6 s/case |
| **Ti-first -ot18 (ADOPTED)** | **14.3 GiB (41%)** | **120 W mean / 123 peak** | **11.9 s/case** |
Ti-first is faster AND 23 W cooler than proportional, and 32 W below the 152 W proven-safe
operating point, with the entire 35.2 GiB model resident in VRAM (zero RAM streaming).

**Scope note:** full VRAM residency is specific to the 35B. The 80B (65 GB), gpt-oss (63 GB)
and Mistral (72 GB) exceed the 48 GiB combined VRAM, so for those the Ti fills, the 3090
takes what the power budget allows, and the genuine remainder spills to RAM. Each gets its
own calibration unit; measured power reported per model rather than assumed.

**Cell provenance (Syed's ruling, no restart):** the 35B's two E1v2 cells stand as measured
on the conservative config; both E2 cells re-run optimized. A 12-case numerical-equivalence
check between the two configs determines whether the E1 cells remain comparable to the rest
of the matrix; result recorded separately.

**Equivalence result (2026-07-30):** conservative-v1 vs optimized-ot18 on 12 identical E1v2
cases: **answers 12/12 identical**, completion_tokens 0/12 identical. Tensor placement changes
the reasoning PATH (float reduction order differs by device) but not the conclusions -
unlike MTP, which shifted ~9% of answers and would likely have shown a disagreement in a
12-case sample. The 35B's two conservative-config E1v2 cells therefore stand as comparable
to the optimized matrix. Caveat recorded: 12 cases is not proof of 147.

### 2026-07-30 - REASONING-MODE CONFOUND FOUND: the 80B cells were invalid

**What happened:** the Qwen3-Next-80B cells completed suspiciously fast (4 cells in 35 min;
calibration probe 2.4 s/case vs the 35B's 11.9). Inspection of completion_tokens exposed why:

| model | median completion tokens | E1v2 arm A |
|---|---|---|
| Qwen3.6-35B-A3B | **1,750-2,010** | 90.5% |
| gpt-oss-120b (harmony analysis channel) | 208 | running |
| Qwen3-Next-80B-A3B-**Instruct** | **8** | 55.8% |

The 80B was answering in 7-8 tokens, emitting the grammar-constrained JSON with NO reasoning
at all. Root cause: I downloaded the **Instruct** variant, which is the family's NON-thinking
member; a separate **-Thinking** variant exists. So those cells measured "a model that does
not reason" against "models that do", not capability. They are marked `skipped` with the
reason (files retained for the record), NOT deleted.

**This also destroyed the controlled experiment**: the 80B existed to hold active parameters
constant (3B, same as the 35B) while varying total capacity 2.3x. A thinking/non-thinking
mismatch confounds exactly that comparison. Re-queued on Qwen3-Next-80B-A3B-Thinking-Q6_K
(65.5 GB, downloading) at the END of the queue so the download has time.

**Protocol consequence, reasoning depth must be normalised, not assumed.** Each family ships
different reasoning defaults. Per Syed's max-capability directive, gpt-oss was requeued with
`--chat-template-kwargs '{"reasoning_effort":"high"}'` (it was reasoning at its default ~208
tokens; it supports low/medium/high). The 35B already runs at its own maximum (thinking on by
default). Mistral's reasoning toggle to be verified when its calibration runs.

**My validation predicate did NOT catch this**: it checks that >=80% of rows carry an answer,
and they did; the answers were just unreasoned. Lesson recorded: "answered" is not "engaged".
A future predicate should compare median completion_tokens against a per-model floor.

**Mistral Small 4, same confound, caught automatically (2026-07-30).** The new reasoning-floor
predicate FAILED its first E1v2 cell at median 16 tokens instead of banking it. Its chat
template: `reasoning_effort` accepts only 'none' or 'high' and **defaults to 'none'**.
Requeued with `--chat-template-kwargs '{"reasoning_effort":"high"}'` (same flag gpt-oss uses).
gpt-oss at high effort confirmed working: median 1,949 tok on E1v2 (vs 208 at its default).

Reasoning-mode status across the ladder, all now verified rather than assumed:
 - Qwen3.6-27B dense (incumbent): thinking by default
 - Qwen3.6-35B-A3B: thinking by default (median ~1,750-2,010)
 - gpt-oss-120b: reasoning_effort=high (median ~1,949; default medium was ~208)
 - Mistral Small 4: reasoning_effort=high (default 'none' = 16 tokens, invalid)
 - Qwen3-Next-80B: MUST use the -Thinking variant, not -Instruct

### 2026-07-31: SHOWDOWN COMPLETE + a measurement defect found in the results

**Raw matrix (E1v2 top-1 / dangerous; E2 exact of 69):**
| model | E1v2 A | d | E1v2 B@3 | d | E2 A | E2 B+guard | gate |
|---|---|---|---|---|---|---|---|
| Qwen3.6-27B dense (incumbent) | 83.7 | 0 | 93.2 | 0 | 10 | 19 | PASS |
| Qwen3.6-35B-A3B | **90.5** | 0 | 83.7 | 3 | 10 | 25 | FAIL(2) |
| Qwen3-Next-80B Thinking | 66.7 | 0 | 68.0 | 0 | 8 | 25 | FAIL(2) |
| gpt-oss-120b | 81.0 | 0 | 78.2 | 0 | 5 | **26** | **PASS** |
| Mistral Small 4 (MXFP4_MOE) | 29.3 | **30** | 44.9 | 22 | 7 | 14 | FAIL(2) |

**gpt-oss-120b PASSED the E2 hard gate** with the best exact-match ever recorded (26/69, zero
dangerous). Second gate pass in project history (after B@3+guard on the incumbent).

**DEFECT 1, token-ceiling truncation, same class as the 2026-07-09 starvation.** Every blank
answer in the run hit the 8192 max_completion_tokens ceiling mid-reasoning and scored as a
miss: 35B 0/147, gpt-oss 13/147, 80B-Thinking **26/147** (its median trace is 5,572 tokens).
Excluding truncated cases: gpt-oss 81.0 -> 88.8, 80B 66.7 -> 81.0. That exclusion is itself
selection-biased (it drops the hardest cases), so the honest fix is a re-run: four E1v2 cells
at `--max-tokens 16384` in a `-c 24576` window (largest measured prompt = 643 tok, so ~7.5k
headroom). NOTE: -c was previously inert; with the raised budget it is load-bearing. Queued
at seq 400-430; identical offload profiles so the delta isolates the defect.

**DEFECT 2. Mistral is uninterpretable, and MY quant deviation is the prime suspect.** Not
truncation (9 blanks). Its answer distribution never once returns `healthy` despite 21 healthy
cases, and skews rich on lean truths -> 30 dangerous misses, the worst of any arm ever. I chose
MXFP4_MOE over the Q6 floor because Q6_K (99 GB) would have been unmeasurably slow; I flagged
the risk then and it appears to have materialised. Cannot separate 4-bit damage from model
unsuitability with this data: recorded as INCONCLUSIVE, not as a loss.

**Also standing:** quant level is a confound across the ladder (Qwen models 6-8 bit, the two
100B-class models 4-bit). The core hypothesis pair, 35B (Q8) vs 80B (Q6), matched 3B active -
is unaffected, both above the 4-bit line. Infra: 3090 never exceeded ~120 W across 4 days and
5 models; zero box deaths, zero ECC errors, zero SEL events.

### 2026-08-02 - SESSION CLOSE: 27B dense ratified as WORKING MODEL; bench-integrity plan held

Syed: "We will be using the 27B", ratified on the corrected record: wins the deployed
config (E1v2 arm B@3: 93.2 vs 83.7 for both finalists), gate-clean, fastest, VRAM-resident.
gpt-oss corrected arm A = 86.4 (best closed-book of the finalists, zero dangerous anywhere)
- remains the E4 challenger. Claude raised no objection. Deployment RATIFICATION (as
opposed to working-model choice) still waits on the bench-integrity rerun + E4, per the
held plan docs/PLAN-bench-integrity-e4-2026-08-01.md. top_k mode-switching (when to serve
@6) explicitly deferred to next session at Syed's request. Serving config on ratification:
hybrid, k3-diagnosis/k6-values, guard, MTP ON.

### 2026-08-02 - BENCH-INTEGRITY EXECUTION: Phases 1, 2, 5 (autonomous, on Syed's go)

Syed gave the word to execute the held plan. Phases 1 (instrumentation), 2 (probe file) and 5
(E4 design) complete; Phase 3 (rerun) queued. Divergences and findings, with reasoning:

**D1. Multi-window snippets measured, NOT adopted (anti-benchmark-maxxing).** After the
snippet rewrite, a sweep showed 2 disjoint density windows at the SAME char budget recall the
expected value in 63/69 probes vs 59/69 for a single window (and 68/69 at 2400 chars). It was
rejected: I would have been choosing it *because it scored better on the benchmark's own
answers*, which is precisely the trap the anti-benchmark-maxxing contract exists to prevent.
The changes that WERE adopted (density anchor, span centring) are justified independently -
they fix "the window lands on the wrong passage", visible without knowing any answer. If Syed
wants the recall improvement, it should be adopted as a deliberate retrieval change with its
own before/after, not smuggled in under a bug fix. Sweep preserved in the session scratchpad.

**D2. Phase 3 expanded from 10 cells to 17 (~+4h on a ~17h run).** The plan reruns arm B only,
reasoning that the snippet fix cannot touch a closed-book arm. True, but `finish_reason` did
not exist when the arm-A cells ran, so their empty completions cannot be separated into
`truncated` vs `no_answer` retroactively, and arm A is where most empty completions happened.
The A2 fix is unmeasurable on arm A without a rerun. Added: 5 E2 arm-A cells. Also carried:
the 2 E1v2 arm-B@3 finalist re-verify cells Syed ratified on 08-01.

**D3, THREE AUDIT CLAIMS REFUTED against source; the gate was NOT softened.** The audit
proposed reclassifying 8-9 probes as `derived` and EXCLUDING them from the fabrication hard
gate. Checked against ref_fts: **0 of 69** probes have an expected value absent from their
source document; all nine candidates state their value verbatim. Excluding them would have
softened a pre-committed safety gate on an unsupported premise. They stay gated, flagged
`derivable_wording` for the report. Likewise `e2-500-1` (audit: "value absent with the expected
sign") was a PARSER bug, an infix minus read as a sign, so "(x-32768)" yielded -32768, fixed
in code, probe untouched; and `e2-5401-1` was never defective (quote verbatim, question
matches). Lesson recorded: the audit agents were right about the CLASS of defect and wrong
about specific instances; every disposition was re-derived from source rather than applied.

**D4; one genuine probe defect, and not the one the audit named.** `e2-3927-1`: Bosch source
gives pilot NOP ~180 bar and main NOP "at approximately 300 bar higher than pilot injection" -
an awkward translation reading two ways. The unit-pump design settles it (pilot 180, main 300
absolute), so v1's question ("by how many bar higher") has answer 120 while the probe expects
300: a model reading the source correctly and subtracting was scored dangerous_miss for being
right. The QUESTION is rewritten to the absolute form; expected value unchanged; `question_v1`
preserved in the row. v2 = 69 probes, 59 keep / 9 keep+flag / 1 fix-question / 0 drop.

**D5, a defect found by writing a regression test, absent from both audits.** An infix minus
was parsed as a sign in BOTH the guard and the scorer: "10-15 psi" yielded [10, -15] and
"(x-32768)" yielded [-32768]. A model correctly quoting 15 or 32768 was BLOCKED because the
source "never stated" it. This is the second time (after the snippet bug) that the harness was
convicting models for its own parsing. Fixed in both modules with tests.

**D6; two new gate-neutral scorer classes.** `unit_mismatch` (450 mV vs "0.45 V", lambda vs
AFR) and `range_mismatch` (stated "6 to 10 deg" against a source's "5 to 7 deg"). Both are
adjudicable rather than convicted, and both have a stated COST: v2 does not convert units, so
"30-40 psi" against "300 to 400 kPa" is genuinely wrong and lands in unit_mismatch rather than
dangerous_miss. Flagged for Syed's adjudication rather than guessed at, a conversion bug inside
the scorer that decides "does this model fabricate calibration values" is exactly the kind of
clever code that produced the defects being fixed. Conversion is a v3 decision, on evidence.

**D7, re-score of all 28 historical E2 files published both ways.** exact 558 -> 577,
dangerous 265 -> 201. Transitions: honest_decline->no_answer 65, dangerous->unit_mismatch 36,
dangerous->exact 21, dangerous->unparseable 5, dangerous->range_mismatch 2, and
**exact->range_mismatch 2 (the scorer got STRICTER)**. Both prior gate-PASS cells still show 0
dangerous. LIMIT STATED, not smoothed: historical rows carry no finish_reason, so their empty
completions cannot be retroactively separated from genuine truncation. Detail:
ml/eval/results/rescore-v1-vs-v2-detail.tsv.

**D8, dense index rebuilt as v2 with a freshness stamp; v1 kept.** v1 was built at 5,608 rows
while ref_fts had grown to 5,638, 30 chunks invisible to the dense ranker for the entire
showdown, undetected. v2 carries its source row count inside the artifact and retrieval.py
checks it against the live DB at load; the ledger now REFUSES a cell whose rows report a stale
index or a silent hybrid->BM25 fallback. v1 stays on disk so showdown cells remain reproducible.

**D9, E4 step_clamp 0.029 (algorithm request), safety clamp untouched at 0.03.** With one
weight at 1.0 the requested step equals the safety bound exactly and float rounding trips a
spurious ve_rate_limit on ~2/3 of sampled values. This narrows what the algorithm ASKS for,
never what the clamp ALLOWS. The separation is the whole safety architecture and is not
negotiable; this change is on the correct side of it.

**Standing checkpoint:** E4 pre-registered bars are proposed in docs/E4-DESIGN.md and NOT
ratified. No model runs against E4 until Syed signs them.

### 2026-08-03: TWO MORE HARNESS DEFECTS, found mid-run by scrutinising a PASSING cell

**D10, the defects.** Both are the same family as the snippet bug: the harness punishing a
model for text handling rather than measuring it. Both were found by looking hard at the ONE
cell that PASSED the gate, not by hunting for something that would flip a verdict.

  a) **U+202F narrow no-break space.** gpt-oss formats numbers with typographic thousands
     separators: `100 000 – 130 000 RPM`. The guard's healer knew U+00A0/U+00AD/U+200B but not
     U+202F, so it read [100, 0, 130, 0], found no support, and converted a CORRECT answer into
     a decline. Worse, healing had ONLY ever been applied to the EVIDENCE side, never to the
     stated value, so any model whose number formatting differed from the corpus was penalised
     for typography. The guard now heals both sides and blocks only when NO defensible reading
     of the answer is grounded.
  b) **Engine codes parsed as values.** `EJ20`, `FA20`, `EJ255`, `SH7058`, `A2WC411D` saturate
     this corpus. The harness read the 27B's explicit DECLINE, "Not specified for Subaru
     EJ20/FA20 in provided excerpts", as the stated value 20 and scored it dangerous_miss. A
     first attempt at the fix excluded only the first digit, so `EJ20` then parsed as 0; the
     lookbehind now excludes a digit run glued to any alphanumeric.

  Also fixed en route: `expected_candidates` ran its number scan on a comma-stripped string but
  sliced the un-stripped one, so every comma before a range separator shifted the offsets and
  `"100,000 to 130,000"` split into two point values instead of one interval.

**D11, the fixes are EVEN-HANDED, which is the check that matters.** (a) helps gpt-oss, (b)
helps the 27B, and the comma fix made the scorer STRICTER on the 27B (its `100,000 to 200,000`
over-claim correctly became range_mismatch instead of exact). Net on completed cells: 27B armA
10→9 exact, 27B k3 39→40, 27B k6 46→47, gpt-oss k6 47→48. **No gate verdict changed.**

**D12, NO RE-RUN NEEDED, and the reason is a design property worth keeping.** The citation
guard is POST-HOC: it inspects an already-generated answer and never touches the prompt,
retrieval, or generation. Combined with (1) `original_value` preserved in every guard record -
the A8 fix earning its keep, and (2) deterministic retrieval, verified by asserting the
re-retrieved doc ids match the ids the row recorded, a guard fix is **fully retroactive and
exact**, not an approximation. `rundown.reguarded()` re-derives it offline and refuses to guess
on any row whose retrieval does not reproduce. This saved ~3.5h of re-running four cells, and it
means cells run before and after the fix converge on identical final instrumentation.

**D13, STOPPING RULE adopted.** Each fix in this exercise has revealed another. To keep the
matrix from becoming a moving target, no further scorer or guard change lands during this run:
any defect found from here is documented and deferred to a v3. The cost of one more "small fix"
is a matrix whose cells were measured under different rules.

**Still pending Syed, unchanged:** E4 bars; the E1 dangerous-flip ruling; top_k mode-switching;
adjudication of `unit_mismatch` rows (incl. whether "equivalence ratio" joins the mixture family
- NOT added on discovery, because changing the scorer in response to a specific failing row is
the benchmark-maxxing pattern this whole exercise exists to avoid).

### 2026-08-04 - E4 RUN: neither finalist passes; the loop itself has a design gap

**Bars ratified by Syed and pre-registered in ledger meta before the first episode**:
diagnosis_accuracy >= 0.90 (set to match E1), masking on leak/healthy = 0, clamp violations = 0,
convergence >= 13/15, residual reported without a bar. `knob_accuracy` renamed
`diagnosis_accuracy`: Syed flagged the name and was right: it measures the LABEL, not the knob.

**Result, the two finalists scored IDENTICALLY in aggregate**, which is coincidence at an
18-episode sample (accuracy moves in 5.6% steps), verified as genuinely distinct runs by file,
timestamp, latency (2.1h vs 3.4h) and diagnosis sequences:

| bar | 27B | gpt-oss | verdict |
|---|---|---|---|
| diagnosis_accuracy >= 90% | 88.9% | 88.9% | **FAIL** (one episode) |
| masking on leak/healthy = 0 | 2 | 2 | **FAIL, hard** |
| clamp violations = 0 | 0 | 0 | pass |
| convergence >= 13/15 | 15/15 | 15/15 | pass |
| median residual belief error | 4.39% | 4.14% | reported |

**D14, THE FINDING: a single-iteration slip permanently corrupts a table, and that is a gap in
the DETERMINISTIC layer, not the model.** On both of the 27B's failing leak episodes it
diagnosed the leak correctly on 11 of 12 iterations and slipped ONCE. The deterministic layer
applied a bounded, clamped, entirely legal edit, and the injector-latency belief is now 2.9%
wrong permanently, with the leak partially masked (trim 13.1 -> 10.2). There is no undo. The
loop acts on the INSTANTANEOUS diagnosis, so one hallucination in twelve is enough.

**D15, proposed fix, deterministic-side (where the doctrine says fixes belong): require
diagnosis STABILITY before acting.** Counterfactual over all 8 masking events:
  N=2 consecutive identical diagnoses: prevents 4/4 for the 27B, 2/4 for gpt-oss
  N=3 consecutive identical diagnoses: prevents 4/4 for BOTH
gpt-oss needs the higher N because its failures are not isolated slips; it THRASHES
(`injector_flow_lean, injector_flow_lean, injector_latency_lean, vacuum_leak, ...`) and even
emits empty diagnoses mid-loop, which the unknown-token -> NO_EDIT default handled correctly.
The 27B's failures are rare slips on an otherwise stable correct answer. That difference is
invisible in the aggregate score and is the strongest qualitative separator between them.
CAVEAT: the counterfactual is exact only up to the first divergence, once an edit is
suppressed the trim trajectory changes and later diagnoses would differ. It justifies building
and TESTING the rule, not adopting a specific N on this evidence.
Cost to weigh: N=3 delays every first edit by 2 iterations against a 12-iteration budget where
the median episode uses 4.

**Composite state: NO model passes all three suites.** 27B passes E1 only (92.5%); nobody passes
E2 since unit conversion (every model fabricates >=1 value at its best setting); nobody passes
E4. Deployment remains unratified, and the two highest-value engineering items are now both in
the deterministic layer, not the model: (1) the diagnosis-stability rule above, (2) closing the
citation guard's cited-but-wrong-quantity blind spot.

### 2026-08-05 - D16: the citation guard's blind spot is NOT closable inside its own contract

**Attempted and REJECTED on its own acceptance test.** Plan Part 5 proposed closing the guard's
`cited-but-wrong-quantity` blind spot, the hole through which every surviving fabrication in the
E2 rerun escaped, with two deterministic, evidence-only checks: unit agreement, and question
anchoring (the number's surrounding window must contain a query term).

Built it, then ran the established 2026-07-25 retro-test protocol over the real corpus: 21
cited-and-WRONG rows (the leaks) and 410 cited-and-CORRECT rows (the false-block control).

    fabrications caught : 0/21
    false blocks        : 6/410

**Strictly worse than nothing, so it was reverted rather than tuned.** Tuning thresholds against
those 21 rows until the number looked better would be fitting the check to the test set, the
exact benchmark-maxxing pattern this project has refused twice already (the multi-window snippet
sweep, and adding "equivalence ratio" to the units table on discovery).

**Why it cannot work as specified.** Question anchoring fails because query terms are scattered
throughout a 1200-char snippet, so a +/-220 char window almost always contains one; the check is
satisfied by nearly every number in the pool. Unit agreement fails because the leaked answers
generally carry a unit that matches; their error is the QUANTITY, not the unit.

The underlying reason is structural: "right document, wrong quantity" requires knowing WHICH
quantity was asked for, and the guard is deliberately blind to the probe and the expected value -
that blindness is what makes it an honest clamp rather than an answer key. The blind spot is a
consequence of the contract, not an oversight in the implementation.

**What would actually be needed** (none of it a guard-internal change, all deferred):
  (a) require the model to return the SUPPORTING SENTENCE verbatim alongside the value; the
      guard can then verify that sentence exists in the evidence and contains the number. This
      makes the model commit to a claim LOCATION and is still fully deterministic. It is a
      prompt + answer-schema change, not a clamp change.
  (b) a semantic check of "does this sentence answer this question", which is an LLM judgement
      and would break the deterministic contract; it would need its own calibration and would
      make the clamp only as trustworthy as a model.

**Standing consequence:** the E2 fabrication gate remains failed by every model, and the leak
path is now understood rather than merely observed. `ml/eval/guard_retrotest.py` is kept; it is
the harness any future attempt must clear, and it is what stopped a bad safety change from
shipping on the strength of a plausible argument.

### 2026-08-05 - E4 VERIFICATION: the incumbent now passes; the two defences catch different faults

Re-ran E4 on both finalists against the SAME bars ratified 2026-08-04 (pre-registered in ledger
meta `e4_bars`; not renegotiated).

| bar | 27B before | 27B after | gpt-oss before | gpt-oss after |
|---|---|---|---|---|
| diagnosis_accuracy >= 90% | 88.9% FAIL | **100% PASS** | 88.9% FAIL | 77.8% FAIL |
| masking on leak/healthy = 0 | **2 FAIL** | **0 PASS** | **2 FAIL** | **0 PASS** |
| clamp violations = 0 | 0 pass | 0 pass | 0 pass | 0 pass |
| convergence >= 13/15 | 15/15 pass | 13/15 pass | 15/15 pass | 11/15 FAIL |
| collateral beliefs corrupted | 9 episodes | **0** | (in the 9) | **0** |

**The 27B passes all four. gpt-oss passes both SAFETY bars and fails both CAPABILITY bars.**

**D17, the two defences catch DIFFERENT failure modes, and that is the main finding.**
    27B     : refused_by_crosscheck = 0,  blocked_by_stability = 52
    gpt-oss : refused_by_crosscheck = 8,  blocked_by_stability = 54
The 27B's errors are isolated SLIPS, stability alone caught every one and the cross-check gate
never had to fire. gpt-oss THRASHES: it produces diagnoses stable enough to survive N=3 and still
wrong, so the estimator had to veto 8 edits stability had already let through. Neither mechanism
would have been sufficient alone for gpt-oss. This validates the layered design on evidence
rather than on argument, and it is invisible in the headline scores.

**The cost, stated plainly.** Convergence fell 15/15 -> 13/15 for the 27B, landing EXACTLY on the
ratified bar with no headroom, and 15/15 -> 11/15 for gpt-oss. Both misses on the 27B are
injector_flow_lean seeds 1-2, where stability withheld 5 and 9 edits because the model kept
changing its mind; those episodes ran out of budget instead of making wrong edits. Two
unconverged episodes bought zero masking and zero collateral damage. If Syed wants the headroom
back, STABILITY_N=2 would likely restore it for the 27B (its counterfactual was 4/4 at N=2) but
gpt-oss demonstrably needs N=3, so a per-model N is a serving decision, not a measurement one.

**CONFOUND, disclosed.** In these runs the estimator's probe pulls drew from the SAME rng as the
loop, so enabling the cross-check advanced the noise stream differently and trim histories
diverged for a reason unrelated to any fix. The large effects are robust to this (masking 2 -> 0
with an identified mechanism; collateral 9 episodes -> 0), but the diagnosis_accuracy movements
(27B 88.9 -> 100, gpt-oss 88.9 -> 77.8) partly reflect different noise realisations and should
NOT be read as pure capability deltas. Fixed afterwards, observations now draw from a separate
seed-derived stream, so future before/after comparisons are clean. Re-running both models under
the isolated stream would give a confound-free comparison; not done here because it costs ~6h GPU
and does not change any bar verdict.

**Escalation works:** all three vacuum-leak episodes on both models now stop at iteration 4 with
"no table edit can fix this; human action required (e.g. find the leak)" and ZERO edits, instead
of bending a table and burning the full budget.

### 2026-08-14 - D18: PERFORMANCE BEATS COMPARABILITY when the two conflict (Syed directive)

Ratified by Syed during the Qwen3.8-27B evaluation. I had justified keeping the certified July-4
llama.cpp build on the grounds that swapping the inference engine would break comparability with
existing benchmark numbers. **Syed rejected that framing:** the objective is a car that drives
correctly, and the model stack is a means to it. If a newer inference engine performs better, use
it, an equal comparison is not the goal.

**Consequences, standing:**
1. **Update the inference engine when it is likely to help, and re-baseline.** Do not preserve a
   stale engine to protect a historical number. The number is a means; performance is the end.
2. **Re-run the incumbent on the new engine too**: not for tidiness, but because the incumbent may
   also be faster/better on it, and *that* is the deployment-relevant figure. Comparability is then
   restored as a side effect rather than pursued as a goal.
3. Old builds are retained only as **rollback insurance** (zero cost on disk), never as the reason
   to avoid an upgrade.

**Evidence supporting the upgrade in this instance** (llama.cpp Jul 4 → Aug 14, 561 commits):
`chat : add qwen3 specialized parser` (#26252), directly relevant, Qwen3.8 emits `<think>` blocks
by default and the old build has no specialised parser for them; `model: MTP support for
Qwen3-Next` (#25589), our serving config uses `--spec-type draft-mtp`; recurrent-state and
gated-delta-net fusion work. DeltaNet is the architecture **both** 3.6 and 3.8 use; 45 CUDA
commits.

**This does NOT license sloppy attribution.** Where a confound exists it is still *disclosed* (as
with the 2026-08-05 rng confound), and a claim of "model X is better" still requires the like-for-
like run. The change is one of priority: ship the better-performing configuration first, measure
the attribution second, not the reverse.

### 2026-08-15 - D19: the deterministic layer MUST gain VE + timing axes (Syed directive)

Syed: *"the deterministic layer 100 percent needs the VE/timing access, because this is a very
large part of tuning that is omitted."* Correct, and the evidence is unambiguous.

**What we found.** MVEM's own docstring: *"a cycle-averaged idle FUEL model … we do NOT model
combustion, knock physics, or transients."* It carries four beliefs, injector latency, injector
flow, MAF transfer, unmetered air. There is **no VE table, no ignition timing, no compression
ratio, no boost, no exhaust backpressure** anywhere in it.

**So E1/E2/E4 prove something narrower than they look.** They demonstrate the loop can identify
idle *fuel* faults in simulation. They say nothing about tuning a VE table or a timing map, which
is the actual job on this car: 2.0 L EJ20X at 9.5:1 running an EJ255 calibration for 2.5 L at
8.4:1, plus VF48 and a fully catless exhaust. Every one of those is a VE/timing mismatch with no
axis in the model.

**Why the idle data looked deceptively good.** Closed loop drives trim to ~0 *regardless* of how
wrong the airflow model is; that is its function. Measured +0.31% total trim means the feedback
loop works, not that the calibration is right. Under load the ECU runs **open loop**, fuelling
straight from the VE/MAF model, and the mismatch appears undisguised. Direct evidence: `af_learning`
is **0.00 across every cell** because the car has only ever idled, the ECU has learned exactly one
operating point, and it is the one point feedback can rescue.

**The asymmetry that makes this tractable.** `safety/clamps.py` ALREADY implements
`knock_auto_abort`, `fuel_before_timing`, `timing_row_ceiling`, `ve_rate_limit` (±3%/iter),
`boost_gate` and `steady_before_transient`: six guardrails for VE and timing, tested. But
`algorithms/` proposes only `corrected_flow_scaling / corrected_latency / corrected_maf`. **The
guardrails exist; nothing generates proposals for them to guard.**

**Design ruling, do NOT answer this with a bigger simulator.**
1. **VE: data-driven, not simulated.** The one hand-set MVEM constant we validated
   (`NOMINAL_MAF_IDLE`) was **40% wrong** for this engine. Compounding that into a VE/timing sim
   multiplies unvalidated assumptions. Real practice is a direct measurement: per load/rpm cell,
   correct VE by (measured AFR / target AFR) from real logs. The three-hold capture supplies the
   idle cells; driving supplies the rest.
2. **Timing: never simulate knock.** Knock depends on CR, IAT, octane, boost and deposits, not
   modellable at useful fidelity, and MVEM already says its knock is "a scripted state for testing
   the abort clamp, not physics."
3. **⚠ TIMING IS A RETREAT MECHANISM, NOT AN OPTIMISER.** The deterministic layer may **remove**
   timing autonomously on knock feedback. **Adding** timing requires human review. Rationale: a
   lean miss costs a log; an over-advanced timing cell on 9.5:1 with 93 octane costs a piston.
   This extends the existing hard constraint rather than relaxing it.

**Sequencing.** Blocked on real data, VE correction needs logged AFR vs target across load/rpm,
which needs the car driven, which needs the ROM read for a write path. Do NOT build a speculative
VE model before the capture exists; that is how `NOMINAL_MAF_IDLE = 2.50` happened.

### 2026-08-16 - FINDING: the ratified E1v2 `base+RAG@3` headline retrieved THREE CONSTANT DOCS

Not a decision, a measurement that qualifies one. Full tables: `ml/eval/results/DOC-COLLAPSE-2026-08-16.md`;
tool: `ml/eval/doc_collapse.py` (committed so this is never ad hoc again).

**What was measured.** Over all 147 E1v2 cases, 3.6's ratified arm B (hybrid@3, 93.9% / 0 dangerous,
2026-07-24) retrieved exactly **3 distinct documents, 5714 (Banish ch.1 page), 621 (rusEFI
`Fuel-Overview.md`), 5502 (Hartman page); each on 100% of queries.** Only 2 distinct ordered
id-tuples exist in the file (dominant ×136). Every 3.6 re-baseline and the 08-02 reverify show the
identical set, and so does 3.8's E1v2 run. E1v1: the same 4 docs for both models. E2 (arm B@6):
**325 distinct docs**, max coverage 7%, E2 retrieval works; E1's does not, because E1 prompts are
simulated *log data* that nothing in a prose corpus is "about".

**What follows.**
1. Retrieval is a pure function of (prompt, index) → **3.6 and 3.8 saw byte-identical evidence on
   E1v2.** The 93.9/0 vs 95.2/7 gap is entirely model-side.
2. The "+RAG@3" was, in effect, a **constant three-page preamble**. It moved 3.6 from 83.7% (arm A,
   07-15) to 93.9%; six constant pages moved it back to 83.7%; it moved 3.8 by 0.0. A real effect,
   but a *prompt-prefix* effect, not retrieval supplying case-specific evidence. (Confound: the
   83.7 arm-A cell predates the 07-25 harness fixes; the arm-B cells were re-verified after them at
   92.5–93.9. Direction certain, exact delta not.)
3. So the ratification measured "base + fixed prefix", not "base + RAG". Running arm B remains a
   fine choice for 3.6 (it helped, cost nothing); the *claim* that retrieval passes the E1 bar is
   not supported. E2/E4 are unaffected.
4. Judging more forum docs (tonight's C2) does not by itself change E1 retrieval, `ref_fts` is
   reference-tier by construction and E1 queries are log-shaped. The levers are the separate
   community index (Track D, built inert tonight) and a *log-pattern → diagnosis* query
   representation. **Design question for Syed; not decided tonight.**

### 2026-08-16 - D20: the MAF baseline carries PROVENANCE, and the estimator refuses MAF verdicts against an unvalidated one

Executed overnight on Syed's ruling ("guard + make nominal rpm-dependent; do NOT guess the value").
Commit `58c8ec2`.

**Problem.** `NOMINAL_MAF_IDLE = 2.50 g/s` was a simulation seed. The first real warm-idle log read
3.493 g/s @709 rpm (+40%); `identify.maf_belief_ratio()` returned 1.397 and the estimator would have
issued a confident *"MAF +39.7%"* verdict on a car whose total fuel trim is +0.31%. The number was
wrong AND nothing recorded that it was unverified.

**Design.**
1. `mvem.MafBaseline(points=((rpm, g/s), …), validated: bool, provenance: str)`: `.at(rpm)`
   interpolates and clamps; `from_capture()` is the *only* validated constructor. `SIM_MAF_BASELINE`
   seeds 2.50@850 / 5.00@1500 with `validated=False`. `NOMINAL_MAF_IDLE` remains the scalar the
   sim/evals import (= baseline at 850). **Nothing hardcodes 3.49**: one log at one point on a
   poorly-idling car is a measurement, not a baseline; the three-hold capture populates it.
2. `identify.Observation.nominal_validated` (default **False**: untrusted unless stated). The sim
   harness and test fixture set True (inside the sim the seed *is* the truth by construction), so E4
   is unchanged. A real-log loader must take the flag from `MafBaseline.validated`.
3. When the baseline is unvalidated the MAF-reading term is dropped from **every** hypothesis'
   residual (it was poisoning `healthy` too), and if the verdict would still rest on it, ratio inside
   a `maf_low`/`maf_high` band, or trims-only best is a MAF fault, `identify()` returns
   `identifiable=False` with a reason naming the ratio, the band, the trims-only ranking and the
   capture protocol. Same shape as the two existing refusals; `clamp_diagnosis_agreement` blocks the
   write. **A refusal is visible; a down-weight is not**: that was the requirement.

**Consequence Syed may want to reverse:** the MAF bands are tight (0.70–0.999 / 1.001–1.40), so with
the seeded baseline *any* real log with a MAF ratio ≠ 1 ± 0.001 refuses. Until the capture exists the
layer effectively issues no MAF verdicts on this car, which is what the checklist already said in
prose. Widening a tolerance around 1.0 is a one-line change if he prefers.

Tests: `car/tests/test_maf_baseline.py` (10); car suite 91 → 101; `ml/eval` E4 tests 18/18.

### 2026-08-16: the ratified gone-sweep policy is now enforced in judge selection (was silently violated)

Commit `7e0c5d5`. `State.pending_for_judge()` and `judge.cli --status` filtered `gone_at IS NULL`.
The 2026-07-22 ratification ("NARROW: gone-ness affects scraping only, never judging, retrieval or
pair-mining") had never been propagated: 303 of the 314 pending community docs (gone-marked by the
2026-06-26 sweep) were invisible to every judge run for a month, `--status` reported 11 pending, and
doc 5781, which the ratification itself said should "ride the next routine judge batch", sat
unjudged. Filter removed in exactly those two places. **Same gap, not fixed tonight, listed for Syed:**
`calibrate.py:33,38` (sampling), `pairgen.py:80`, `e2gen.py:78` still filter `gone_at`. Also added:
`--no-reindex` (a judge run must not silently rebuild `ref_fts`; the operator reindexes deliberately)
and a dead-server STOP instead of burning the pending pool to `failed`.

### 2026-08-16 - FINDING: the E1 "dangerous" count depends on an unwritten reading; it decides the 3.8-vs-3.6 verdict

Not a decision. Syed's to make (handoff §7). Recomputed from the jsonl
(`ml/eval/results/RUNDOWN-2026-08-16-qwen38.md`): Qwen3.8's E1v2 "7 dangerous" per arm is **0**
under the *codified* `rundown.dangerous_flips()` (2026-08-02), the six `vacuum_leak →
injector_latency_lean` misses are lean→lean, which the codified metric explicitly calls a miss. The
handoff applied the "edit authorised on a no-table-edit fault" reading, which the codified rule
applies only to `healthy`. The definition is internally inconsistent about `vacuum_leak` (it is both
a lean signature and a no-edit fault) and no model had failed on exactly that pair before. What is
not in dispute: 3.8 errs toward "edit latency" on leak cars, 3.6 errs toward "no edit", the
safety-relevant asymmetry, and E4 neutralises it (all three 3.8 `vacuum_leak` episodes escalate
with no edit). **Recommendation: codify the reading explicitly, re-run `rundown.py` over every
historical E1 file so numbers are comparable, then compare models. Not done tonight; it changes a
ratified metric.**

### 2026-08-16 - JUDGE CALIBRATION VERDICT: Qwen3.8 does NOT replace Qwen3.6 (1 dangerous cell); incumbent re-baselined on the new engine at 90.0/98.0/0

Rule applied (Syed, ratified 06:2x UTC before the run): a candidate replaces the incumbent only if it
clears the DB pre-registration `meta['calibration-100:pass_bars']` = **90/90/0** AND matches-or-beats
the incumbent's LIKE-FOR-LIKE recalibration on the same engine/n/rubric AND has zero dangerous cells.
(The runbook's "93.1/97.7 pre-registered" was 3.6's *achieved* July numbers at n=87, corrected in
`recalibrate.py`, checklist, runbook text.)

| judge (Aug-14 llama.cpp build, ctx 32768, 24576 tok, rubric r2, n=100) | keep/drop | within±1 | exact | ρ | dangerous | verdict |
|---|---|---|---|---|---|---|
| Qwen3.8-27B Q8 (Unsloth) | 91.0 | 98.0 | 69.0 | 0.564 | **1** (doc 1081) | **FAIL**: hard bar |
| Qwen3.6-27B Q8 (incumbent, like-for-like) | **90.0** | 98.0 | 70.0 | 0.583 | 0 | PASS, zero margin |

**Consequences.**
1. `config.yaml llm.model` stays `qwen3.6-27b-q8_0`; the C2 community judge run used 3.6 on the
   Aug-14 build (engine change disclosed, D18 says use the better engine and re-baseline; the
   re-baseline is the row above).
2. **The incumbent's margin is gone.** 90.0 on a ≥90 bar. Not a failure; not comfortable. Part of the
   3-pp drop vs July is methodological (n 87 → 100; the 4 reference-tier docs in the set are fully
   judged by `recalibrate` where the runner auto-passes them, same treatment for both models, but
   different from July). It should be re-measured if the engine, budget or rubric changes again.
3. **Both judges recall 4/9 adjudicated 4s**: the same four, and push 960/1031/1088/5773 to 3 and
   1127 to 2. Keep/drop agreement is carried by the 54 truth-2 docs. So the ≥4 gate is reliably
   *rejecting* and unreliably *accepting*; that is the honest reading of "the forums hold content the
   judge will promote", and it is why the score-3 review (28 keep / 67 drop) found value below the bar.
4. Nothing decides whether 3.8 becomes the *diagnosis* model, E1/E2/E4 are that question and are
   Syed's (§7), with the E1 dangerous-definition finding above on the table.

### 2026-08-16: ROM READ SOLVED; and a standing directive to optimize past the pre-data (July) workflows

**The read.** The project's day-one blocker fell. The stock ROM was read (FastECU + the Subaru
**green test-mode connectors**, which enable read/write mode) and is **byte-identical to a harvested
known-stock reference**, so the ECU is genuinely un-tuned and was never locked. The failure had been
at `RequestDownload` (`7F 34 10`), not seed/key; a `dataFormatIdentifier` sweep falsified the
format hypothesis; the connectors were a **permission gate**. Our own `ROM-READ-BLOCKER.md` had
eliminated those connectors as "not applicable to a 2005 DBW car", an elimination by argument, never
by test. **Lesson (worth keeping): an elimination that was never run is not an elimination.** The fix
came from corpus doc 5793, surfaced by the overnight community-doc review, the pipeline found what
its own reasoning had ruled out. Provenance/validation: `car/ecu/rom read/PROVENANCE.md`, commit
`f27aad8`.

**Standing directive (Syed, 2026-08-16): optimize past the July guidelines where the data warrants.**
The roadmap and capture docs were written before any real car data. Syed's instruction: do what is
best for the project, not what an older workflow said before we had data. Concrete deviations now in
force:
1. **Extended-parameter RAM addresses may be grafted from siblings + validated**: the
   `IDLE-LOG-PROFILE.md` refusal ("do not before the ROM read is solved"; "'often' is not 'provably'")
   is lifted: the `3B125` family shares one RAM layout (Feedback Knock `0xFF5C18` agreed by 5 siblings
   incl. the rev-42 MT twin) and the ROM now cross-checks. We recover the rich channel set instead of
   logging an impoverished one, validating each channel live before trusting it.
2. **RAG is de-prioritized for diagnosis** (doc-collapse: ≈0 contribution to E1); it is kept for the
   exact-value job (E2). Diagnosis leans on the deterministic layer + fine-tune reasoning.
3. **Center of gravity is the car**: real logs + the deterministic layer + tuning iterations are
   primary; corpus/judge/eval is the parallel track. Re-scoring sim-bound evals is low-value.

**Reconciliations.** D19 sequencing: the "needs the ROM read for a write path" precondition is now
met; the remaining blockers are the write-path build + a driven load/rpm capture (no protocol yet).
D20: the unvalidated-baseline refusal band is superseded for real captures by
`MEASURED_MAF_BASELINE_20260816` once the log→layer bridge wires `nominal_validated` from it.

**Role guardrail (Syed, 2026-08-16, reaffirming the safety doctrine):** the *pipeline* tunes
(deterministic layer proposes → clamps bound → later a local fine-tuned model is a cross-checked
proposer); **Syed approves**; **Claude builds the pipeline and is a verification set of eyes, never
the runtime tuner.** Hand-analysis of logs is permitted only as build-phase verification of the
builder (the bridge's acceptance test), never as the product.

## 2026-08-26: Boost sequencing corrected (Syed); and WHY the car is unsafe under boost right now

### D21: The "no boost before the smoke test" rule was circular. Syed's sequencing stands.

**Corrected by Syed, 2026-08-26.** The recorded rule (`DRIVING-CAPTURE-PROTOCOL.md`: *"Boost/WOT
tuning waits for the smoke test. No exceptions."*, checklist A2) is **physically impossible as
written**: the smoke test happens at Syed's shop, reaching the shop requires highway driving, and
highway driving is boost driving. The rule required boost to be tuned before it could be tuned.

**Ratified ordering:** a **general base tune first, enough to drive safely, including boost** -
then the smoke test. This was Syed's intent on 2026-08-16 (`DRIVING-CAPTURE-PROTOCOL.md` line 24
already recorded *"tune enough to drive well, defer the smoke test"*); the absolute no-boost line
elsewhere in the same document contradicted it and is now withdrawn. Do not re-litigate.

Retained: a leak still poisons VE conclusions, so the smoke test remains a prerequisite for
**trusting** boost-region VE numbers as final; it is no longer a gate on **collecting** them or on
shipping a conservative safety tune.

### The finding that makes this urgent (drives 2–3, 2026-08-26)

The car **stays in CLOSED LOOP under boost, targeting ~14.55 AFR, while knocking.**

| | drive 2 | drive 3 |
|---|---|---|
| boost samples | 83 (max +1.31 psi) | 211 (max +2.18 psi) |
| CL/OL status under boost | `8` (closed loop), all | `8` (closed loop), all |
| commanded target | 14.53–14.57 AFR | 14.53–14.56 AFR |
| measured AFR | 15.45 mean | 14.51 mean |
| knocking while in boost | 57 of 83 samples | **211 of 211 samples** |
| worst retard | −8.22° | −12.00° |

A healthy Subaru leaves closed loop under boost and commands ~11.0–12.5 AFR. This one holds stoich
and pulls up to 12° of timing to survive it.

**Mechanism; one root cause explains everything observed:** open-loop transition is triggered by a
**load** threshold. Load is derived from airflow, and we measured the VE error directly, the ECU
needs **+34 % fuel correction at 0.7–0.8 g/rev** (`car/logging/drive/ANALYSIS-2026-08-26-vacuum-drives.md`).
It is therefore **under-reporting load**, never crosses the OL threshold, stays in closed loop, runs
stoich into boost, knocks, and has learned `IAM = 0.500`. The 2.0 L-on-a-2.5 L-calibration VE error
has **defeated the ECU's own boost-enrichment safety mechanism.**

**Consequence for the tune order:** correcting VE is not cosmetic; it re-arms stock protection. The
severity scales with boost, so sustained highway boost is materially worse than the +2 psi seen so
far. The cruise-region VE correction is therefore the first flash, and it is a safety fix.

## 2026-08-27: MAF root cause, a new clamp category, and the SH7058 checksum

### D22: The fault is the MAF TRANSFER CURVE, not the fuel maps

Six vacuum drives (35,744 rows, 30,795 steady closed-loop samples). Fuel trim tracks **measured
airflow** far better than load or rpm, `corr` +0.838 vs +0.708 / +0.737, and the decisive test
settles it: hold MAF fixed and swing load/rpm hard, trim moves 0.3–5.0 pp; hold load fixed and
swing MAF, trim moves 3.1–15.3 pp. The error is a function of airflow alone.

**This supersedes the "2.0 L on a 2.5 L VE map" framing.** Subaru's 32-bit ECU is MAF-based and
has **no VE table at all**: `core/tables.py` already annotated `sensor.maf_transfer` as
"(speed-density: absent)". A 1-D curve correction replaces a 2-D map rewrite.

**One fault, three symptoms.** Load is derived from airflow, so the under-read propagates:
fuel under-commanded (clawed back by trim); the ignition map indexed at the **wrong cell**,
applying light-cruise advance under real load, which is the only thing that explains knock at
stoichiometric AFR; and the load-triggered open-loop transition never firing, so the car has
**never once left closed loop under boost** in anything logged.

Contamination is **ruled out**: Syed cleaned the MAF element and re-drove (2026-08-27); the
curve's shape is unchanged and `corr` held at +0.840. Remaining candidates are a wrong
calibration for this intake tract, or unmetered air through the custom MAF→turbo tubing. Not
separable from logs; the smoke test is the arbiter. We proceed because the compensation is
correct for the car's present physical state and the failure direction if a leak is later
sealed is **rich**, which `clamp_afr_floor` already documents as the safe direction.

### D23: The ECU is nearly out of fuel-correction authority (why this is urgent)

A/F Learning hard-clamps at **+14.84%** and A/F Correction at **±25.00%**; combined ceiling
**+39.84%**. Above 20 g/s the car runs at **~75% of total authority**, learning is saturated in
79–81% of samples, and **6.2% have both channels maxed simultaneously**: roughly 9.8 pp left.

Independently corroborated by the ROM itself: `fuel.cl_learning_limits` reads **±15.00%**, and
we measured learning pegged at +14.84%. The wideband confirms the ECU is still holding command,
so it is winning, with nothing in reserve, in vacuum cruise. Highway airflow plus boost exceeds
what remains, and an ECU out of correction goes **lean**, on an engine already at IAM 0.500.

### D24: A new clamp CATEGORY: sensor calibration (methodology change to the safety layer)

`clamp_ve_rate_limit` bounds fuel edits to 3%/iteration because idle convergence chases a target
that moves as the loop corrects it. A MAF transfer curve is not a target being chased; it is a
**measurement wrong by a fixed amount**, established over ~20k samples. Creeping there needs ~11
flash cycles on a car with no authority margin. Adding `targets_kind="sensor"` +
`clamp_sensor_calibration`, which bounds **evidence** (samples per breakpoint), **displacement**
(`max_sensor_recal` 0.40; measured worst point 0.363) and **curve monotonicity**, instead of
velocity. The two paths are disjoint by `targets_kind` and that disjointness is property-tested:
`fuel.*` behaviour is byte-identical.

### D25: The SH7058 checksum, derived (ROADMAP E.4(c) closed)

The repo had **zero** checksum content and the ROADMAP left it open ("believed yes" that ECUFlash
fixes it on save). Derived and implemented rather than trusted: block at file offset **0xFFB80**
(1 MB ROMs), an array of 12-byte big-endian records `{start, end_inclusive, stored}` satisfying

    ( Σ BE-uint32 over data[start..end] + stored ) mod 2**32 == 0x5AA5A55A

Our ROM carries exactly one active record, `0x2000..0xFFAF7`, stored `0x5EA92EFD`. The block sits
**outside** every region it covers, so repair is a **one-pass fixed point**: asserted in code,
not assumed. The offset is claimed for **our family only**: foreign ROMs on disk do not parse
there, so `read_records` raises `UnknownChecksumLayout` rather than returning a confident wrong
answer.

### Two safety-config numbers that need Syed's ruling

1. **`boost_load_threshold: 1.5` g/rev is wrong for this car.** `clamp_afr_floor`: the clamp
   whose entire purpose is preventing lean-at-boost, only acts *above* that load, but this car
   crosses atmospheric MAP at **≈0.6 g/rev**. As configured it does not cover where boost happens.
2. **`belief_envelope` is absent from `config.yaml`**, so it runs on pydantic defaults whose own
   comment says "VALUES ARE SYED'S TO RATIFY", including `sensor.maf_transfer: 0.20`, which the
   measured correction exceeds. The new sensor clamp bypasses it by `targets_kind`, deliberately,
   but the number should still be ratified rather than inherited.

### Bugs found while building (all fixed)

- `clamps._sign()` computed `(x>0)-(x<0)`, which raises `TypeError` on a numpy scalar.
  `CellEdit.new_value` is *typed* float but nothing coerces it, so any array-derived proposal
  crashed `clamp_ve_rate_limit`. Never hit because only the sim had produced proposals.
- `Closed Loop Fueling Target (2-byte)* (lambda)` matched the wideband schema rule on the word
  "lambda" in its units, the ECU's *target* silently overwriting the *measured* AFR. It escaped
  notice only because the AEM sat in an earlier column and parsing is first-column-wins.
- `clamp_sensor_calibration` guaranteed a strictly ascending curve using `zero_base_eps` (1e-9).
  float32 has ~1.2e-7 relative precision, so at a value of 30 that separation **collapses to
  equality on write**: the guarantee died at the storage boundary and the flashed curve would
  have had flat spots. Caught by the write path's own read-back. Separation is now relative, and
  `patch()` independently re-checks ordering *after* encoding. **An in-memory guarantee that does
  not survive encoding is not a guarantee.**
- The first generated CHANGE REPORT showed the stage proposing −1% to −3% across the idle band -
  chasing bin noise in the one region independently validated as healthy (three-hold capture,
  −0.86%). Added `AlgoCfg.sensor_deadband` (0.02), applied before interpolation so a sub-noise
  anchor cannot drag its neighbours. 20 cells → 14.

### D26: `boost_load_threshold` 1.5 -> 0.60 g/rev (Syed ratified, 2026-08-27)

The number is a CLASSIFIER, not a limit: `clamps.py:160` uses it for exactly one decision -
which fuel-target cells `clamp_afr_floor` bothers to check. It does not restrict boost, does not
cap it, and never touches the wastegate.

But `clamp_afr_floor` is the last and strongest clamp in the pipeline (it will richen past the
rate limit, because commanding lean under boost is the engine-grenade case), and its guarantee is
only as good as the region it is aimed at. At 1.5 g/rev it aimed at nothing: this car crosses
atmospheric MAP at **~0.6 g/rev**, and all **31 knock events sat at 0.58-0.79 g/rev**: entirely
outside the protected region.

Nothing had been harmed: `clamp_afr_floor` only acts on AFR/lambda target tables and no edit to
one has ever been proposed. It goes live the moment boost tuning starts.

The error is one-sided, which is why the low value is right: too high leaves real boost cells
unprotected; too low protects vacuum cells whose 14.7 target is nowhere near the 11.5 floor, so
the clamp never fires there. `tests/test_boost_threshold.py` recomputes the crossing point from
the committed drive logs and fails if the threshold ever drifts back above it, a regression test
against a physical fact rather than a remembered number.

### D27: FIRST ECU WRITE, verified byte-exact (2026-08-29)

The project's first write to the car. Loop closed: **intended → written → confirmed.**

```
candidate  sha256 9d33d08b7d4e604b064c018c3fc9a02123b68074f5c11fe36641ade15a04bc25
read-back  sha256 9d33d08b7d4e604b064c018c3fc9a02123b68074f5c11fe36641ade15a04bc25   IDENTICAL
stock      sha256 11fe1536690e6b8f789d8719185a003c2d8ee73253ecd59a97a63f183a3f3118
```

53 bytes differ from stock, exactly as designed. Cal ID `A2WC411D` unchanged, SH7058 checksum
valid on the read-back, `sensor.maf_transfer` the only semantic table changed, curve strictly
ascending in the ECU. 16 of 48 breakpoints moved, −3.2% to +22.1%.

**Tool: FastECU, stock upstream build, block-by-block write.** EcuFlash was eliminated by test
(D26 / ROM-READ-BLOCKER): its SecurityAccess key is rejected on this ECU even with the green
connectors joined.

### ⚠ D28: FastECU's "test write" is NOT a dry run. It erases and does not program.

Read from the source before use (`modules/ecu/flash_ecu_subaru_denso_sh705x_kline.cpp`). The
erase command is sent **unconditionally**: there is no `test_write` guard around it:

```cpp
emit LOG_I("Erasing flash page...", true, false);
output.append((uint8_t)(SUB_KERNEL_BLANK_PAGE & 0xFF));
received = serial->write_serial_data_echo_check(output);
```

The flag changes only the final step: `SUB_KERNEL_VALIDATE_FLASH_BUFFER` (CRC, does not persist)
instead of `SUB_KERNEL_COMMIT_FLASH_BUFFER`. So a "test write" **erases the page and then does not
program it**, leaving the original contents destroyed and the replacement unwritten. Recoverable
only by immediately performing a real write. It converts one risky operation into two with a
dangerous window between them.

**Never use it.** The name, and the community description of the green arrow as a safe test, are
both actively misleading. Verified against the source, not assumed.

Corollary, from the same source: writes are block-by-block and unmodified blocks are skipped
(`get_changed_blocks()` / `if (block_modified[blockno])`). A stock→stock "rehearsal" flash would
therefore write nothing at all and prove nothing; that plan was dropped for this reason.

### D29: Three safety-config rulings (Syed, 2026-08-30)

**1. Timing ceiling is now LOAD-aware.** The rpm-only ceiling could not tell "40 deg at light
cruise, entirely normal" from "40 deg at 0.9 g/rev in boost, dangerous", on this car both
happen at the same engine speed. The placeholders (25/18/14 deg) were also *below* normal cruise
timing and would have gutted the map. Ratified:

    load < 0.55   45 deg   cruise; the map's 40-45 here is normal and not knocking
    load 0.55+    30 deg   the ECU DELIVERS 33.6 here and still pulls ~5 deg of knock
    load 0.85+    22 deg   boost; EJ20X 9.5:1 against a map written for 8.4:1, on 93 octane

Effective ceiling is `min(rpm limit, load limit)`, so load-awareness can only tighten. RPM limits
raised to 46/40/32 so they no longer clip legitimate cruise advance.

**2. Cumulative sensor displacement is now bounded (`sensor_envelope`, 0.40).** A real gap:
`max_sensor_recal` bounds each iteration against the table's CURRENT value, and `belief_envelope`
is fuel-only, so nothing bounded how far a sensor table could WALK across iterations. Exactly
the hole that motivated `belief_envelope` for fuel. The MAF curve was already +31.6% from stock
when this was found, and iteration 3 took it to **+35.2%** against the new 40% cap. The bound was
not theoretical.

Wiring note: the envelope must be measured against the ARCHIVED STOCK ROM, not the image being
patched, `--tune-maf` previously passed the current tables as baseline, which would have made
the bound vacuous (every iteration reads as 0% from baseline). New `--baseline-rom` flag.

**3. `belief_envelope` moved into `config.yaml`.** It had been running on pydantic defaults whose
own comment said "VALUES ARE SYED'S TO RATIFY". Same numbers, now visible and reviewable.

### D30: Fuel before timing, for a physical reason rather than a procedural one

Syed proposed timing first, so the car could safely reach boost and generate the high-airflow data
the MAF curve still lacks. Sound in isolation, but timing is indexed by LOAD and load is derived
from AIRFLOW, so the two are coupled:

  * At 45-70 g/s the MAF still under-read 17-24%, so the ECU looked up timing in a LIGHTER cell
    than the engine was actually in, which carries MORE advance. Correcting the MAF alone
    retards boost timing by **4 to 11 degrees** with no change to the timing map. For scale, the
    corpus EJ20X swapper (doc 944) ran "timing down 5%", which is about 1.9 deg.
  * The reverse order is actively worse: tuning timing against a load axis that is 20% wrong
    assigns corrections to the wrong cells (the map's load steps are 0.85/0.90/1.00/1.15, so a
    20% error is more than a full cell), and fixing the MAF afterwards moves them.

So MAF-first is the shorter route, not the cautious one. Recorded because the intuition that
"fix the dangerous thing first" points the other way, and will again.

## 2026-08-30 (later) - the timing stage: five blockers cleared, and four rulings

The plan (`docs/PLAN-timing-stage-2026-08-30.md`) listed five defects to fix before any timing
code ran. All five are closed and each has a named regression test that was **verified to fail
when the original bug is reintroduced**, a pin, not a claim:

| blocker | what it was | pin |
|---|---|---|
| 1 | load ceilings never fired (float32 axis vs decimal literal) | `test_load_ceilings_fire_at_the_ROMs_real_float32_breakpoints` |
| 2 | `knock_active` / `fuel_trims_converged` / `steady_state_ok` never set outside tests | `logparse/signals.py` + 8 tests |
| 3 | `report.py` indexed a 2-D map with `row * a.shape[0]` on a RAVELED array | `test_change_report_indexes_a_2d_cell_correctly` |
| 4 | timing had no rate limit, no cumulative bound, no floor | `clamp_timing_rate_limit` + 6 property tests |
| 5 | `_verify_flash` hardcoded to the MAF curve | `_FLASH_PROFILES`, `--expect` |

Fuel behaviour is provably unchanged: re-deriving MAF iteration 3 from its own log reproduces
`POSTFLASH3…bin` **byte-for-byte** (sha256 `3e64b627d0f532f8…`).

### D31: The timing rate limit runs AFTER the ceiling, not before. The plan had it backwards.

`PLAN-timing-stage-2026-08-30.md` §2 specified inserting `clamp_timing_rate_limit` *before*
`clamp_timing_row_ceiling`. That is wrong, and wrong in the same way blocker 1 was wrong, a
ratified limit that silently never binds.

The ceiling is a floor-to-a-value operation: on this ROM it drops the worst cell **18.12 deg in
one move** (40.12 deg at 2400 rpm / 0.85 g/rev, against the 22 deg boost ceiling). Running it
last would override Syed's ratified 6 deg/iteration and leave the rate cap decorative. The
plan's own acceptance criterion, *"rate limit holds for any input"*, is only satisfiable in
the other order.

**Ceiling decides WHERE a cell is going; the rate limit decides HOW FAST it gets there, so the
rate limit has the last word.** Consequence, stated plainly: the worst cell needs **4 passes**
to reach its ceiling, with a drive and a re-log between each. That is the cost of the ruling,
and it is the point of it.

### D32: Two gates get a VERIFIED retard-only exemption (and fuel gets a human override)

Wiring the live signals for the first time produced two deadlocks, both of the same shape: a
gate written to stop us ADDING risk was refusing the only change that REMOVES it.

* `clamp_knock_auto_abort`: this car knocks; that is the entire reason the timing stage
  exists. Every log that could justify a retard also trips the abort.
* `clamp_fuel_before_timing`: after three MAF flashes, 26 of 27 confident airflow bands sit
  within ±3.7%, but one (**59.31 g/s, 29 samples**, the very top of the measured range) reads
  **+7.44%**, past the 5% tolerance. Closing it needs high-airflow data; that needs sustained
  boost; and sustained boost is what the timing work exists to make safe. **That is D21's
  circularity arriving on a different axis.**

Both now pass a proposal in which no cell ends up more advanced than it currently is. The
exemption is **verified against `ctx.tables`, never declared**: it deliberately ignores
`prop.metadata`, because metadata travels with the proposal and the future LLM is a proposal
producer, a metadata flag would be a safety gate an untrusted party could open for itself.
One advancing cell disqualifies the whole proposal. Both exemptions are recorded in the audit
trail. Pinned by `test_knock_exemption_cannot_be_unlocked_by_metadata`.

The gate's own docstring already said the hazard: *"a lean miss + extra timing = detonation"*.
The hazard is **extra timing**. Retard is not the direction it protects against.

**Fuel and sensor proposals get no such structural argument**, so for those the abort stands and
the only way past is `--ack-knock`: a flag typed by a human at the command line, printed loudly,
and stamped into the change report. That is the "human-reviewed" leg of the architecture doing
its job, and it is categorically different from a proposal vouching for itself.

### D33: The IAM deficit is read from the ROM. Two guesses were replaced, and one earlier reading was wrong.

The stage's first cut applied a flat 2.0 deg of "lost dynamic advance" to every confident cell,
measured from an assumed healthy IAM of 1.0. Both halves were wrong, and the ROM says so:

**1. `Advance Multiplier (Initial)` = 0.5, not 1.0.** An observed IAM of 0.500 is this
calibration's **factory value**, not a halved one; the step is 0.25. The 2026-08-26 analysis
read "an engine whose `IAM` already sits at 0.500" as evidence of prior damage; on this ROM it
is simply the starting value. **The collapse to 0.000 on 2026-08-30 is still entirely real** -
that is a full deficit, not a half one, but the baseline it is measured from was wrong, and
measuring from 1.0 would invent a permanent 50% deficit on a healthy engine.

**2. IAM multiplies `Knock Correction Advance Max` (0xC8FB0), a real 18×16 map.** Commanded
advance on this family is `Base + IAM × KnockCorrAdvMax + feedback + fine learning + comps`. So
the advance a cell loses is that cell's own entry, and on this ROM that entry is **0.00 across
the entire idle and cruise region** (load ≤ 0.55) and **3.16–9.14 deg** where the car makes
boost.

The flat constant was thus wrong in both directions at once: it retarded the idle band, which
`car/CLAUDE.md` records as independently validated *knock-free*, by 2.11 deg, while
under-correcting the boost cells that needed up to 4.57. Reading the ROM removed 20 spurious
edits and raised the boost-region term. Two new read-only semantic tables carry it
(`ignition.knock_advance_max`, `ignition.advance_multiplier_initial`); the config numbers remain
only as fallbacks for a platform that lacks them.

**The lesson is the project's own, again: the ROM already knew.** The same shape as the MAF arc,
where `core/tables.py` had annotated the platform as MAF-based while the plan still assumed a VE
table.

### D34: `min_timing_advance`: an absolute floor, found by a property test rather than by reading

`max_timing_retard` (cumulative, vs the archived stock ROM) goes **inert when no baseline is
supplied**, the same "inert without a baseline" pattern as `belief_envelope` and
`sensor_envelope`. The ceiling is a *maximum*. So with no baseline there was **nothing at all**
bounding retard from below, and a convergence property test walked a cell to **−49 deg**: past
TDC, in twelve iterations.

Two fixes, because one was not enough:
* `min_timing_advance` (0.0 deg BTDC): an absolute clamp-level floor that needs no baseline. Not
  the tuning limit, the ceiling, cumulative floor and rate cap are; it is the bound that says
  *no ignition-retard stage ever fires after TDC*.
* `--tune-timing` now **refuses to run** without `--baseline-rom`, rather than warning. For
  `--tune-maf` an inert envelope still leaves the per-iteration cap doing real work; here it
  would leave the backstop as the only bound below.

**A rate limit that bounds a single step does not bound a sequence.** Worth stating on its own:
every per-iteration bound in this layer deserves the question "and what does N iterations do?",
which is exactly the question `belief_envelope` was created to answer for fuel in August.

### Two more silent schema collisions (five and six)

`IAM (1-byte)** (multiplier)` matched **no rule at all**: the channel recording the ECU
withdrawing all advance for 52 s was invisible to the layer. `Ignition Base Timing*` matched
`\btiming\b` and landed on `timing_total`, the role meaning FINAL commanded advance; it lost to
`Ignition Total Timing` only because that column came first. Both now have their own roles
(`iam`, `timing_base`). `tps` and `iam` gained explicit `schema.prefer()` entries, `tps` now
resolves to the **DBW plate angle** (max 49.8%, matching the handoff's figure) rather than the
pedal-derived channel.

Also worth recording: `Knock Sum* (count)`: a cumulative counter, non-zero on 6425 of 7402
samples, is one of **three** headers claiming `knock_retard` on the 2026-08-30 log. It loses
only because of the existing `prefer()` rule. Now pinned by a test, because a reordered export
would otherwise compute every timing-evidence figure from a rising integer.

### Numbers that still need Syed's ruling

| number | value | basis |
|---|---|---|
| `max_timing_retard` | 20.0 deg | derived: the ratified ceilings themselves demand at most 18.117 deg, so anything below ~18.2 would fight them; 20.0 clears it with ~1.9 deg of evidence headroom |
| `min_timing_advance` | 0.0 deg BTDC | a backstop, not a tuning limit; the stock map's own minimum is 2.148 deg |

### D35: Two IAM-gated behaviours we did not know about, found while answering "have we touched the knock tables?"

We have **never modified a knock-correction table**: only read two of them (`Knock Correction
Advance Max`, `Advance Multiplier (Initial)`) for the IAM deficit in D33. Reading the rest turned
up two thresholds that change how the car behaves *right now*, and neither was in any prior note:

| table | value | consequence |
|---|---|---|
| `Boost Control Disable (IAM)` @0xC0440 | **0.20 / 0.65** | boost control is DISABLED below IAM 0.20 and re-enabled only at 0.65 (a hysteresis pair; the axis is literally named "Boost Control") |
| `Primary Open Loop Fuel Map Switch (IAM)` @0xC5E7C | **0.35** | below IAM 0.35 the ECU runs `Primary Open Loop Fueling (Failsafe)`, not the primary map |

**The car has been driving with boost control disabled.** IAM sat at 0.000 for 52 s on the
2026-08-30 drive and recovered only to 0.125, under 0.20 the whole time. That is very likely why
maximum observed boost is +6.53 psi: the wastegate has been running on spring pressure, not on a
duty target. Every boost figure recorded in this project so far is a *boost-control-disabled*
figure, and D30's "boost rose across the set" reasoning was measuring a car with its boost
controller switched off.

**Recovery is a compound hazard, and it happens without the driver doing anything.** The
re-enable threshold (0.65) is ABOVE the initial IAM (0.50), so IAM must climb past its own
starting value to restore boost control. If the timing map works, the first drive can cross
**three** thresholds in sequence: 0.20 (boost control re-enables), 0.35 (open-loop fuelling
switches from the Failsafe map to the leaner Primary map, 14.36 vs 13.63 AFR at 1.15 g/rev,
2000 rpm), and 0.65 (full boost authority). More air and a leaner target, arriving together,
triggered by the ECU rather than the throttle.

This is also the strongest argument yet for having extrapolated the MAF curve first (D-prev):
the drive that could restore boost control is the same drive that would have exposed an
uncalibrated MAF in open loop.

**Why the knock tables stay untouched for now.** They are the ECU's protective RESPONSE; the
fault is the base map being over-advanced. Fixing the response before the cause is turning off a
fire alarm. Every one of them moved in the "give advance back" direction, raising
`Advance Multiplier (Initial)`, raising `Knock Correction Advance Max`, softening
`Feedback Correction Negative Advance Value` (1.0 deg/event), makes a knocking engine worse.
The legitimate future uses all run the other way: LOWERING `Knock Correction Advance Max` in the
boost region as belt-and-braces over the base map, pulling harder or sooner on knock
(`Feedback Correction Negative Advance Value` / `Delay` = 250 counts), lowering
`Fine Correction Advance Limit` (8.0 deg), or raising the boost-disable threshold so boost is cut
sooner when IAM sags. Recorded so the option set is known, not because any of it is scheduled.
