# MLECU — Decision Log

Append-only. Records material choices and especially **divergences from the bootstrap soft-foundation**
(per the brief: the *facts* and the *safety architecture* are fixed; the *approach* is mine to refine,
with reasoning logged here).

---

## 2026-06-22 — Bootstrap & initial structure

### Invariants carried forward (not decisions to revisit — recorded for clarity)
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
3. **`principles.md` kept unified — optional `market-intelligence.md` split deferred.** The file isn't
   large; avoid premature fragmentation. Revisit if the market/pricing material grows.
4. **No `archive/` directory.** The June 11 files (`master-context.md`, `bootstrap-architecture.md`)
   are not present anywhere under `/home/syed` — nothing to archive.
5. **`context/hardware-state.md` refreshed to verified reality.** The OEM 3090 enumerates and the
   driver is up (580.159.03 / CUDA 13.0); §5 updated from "in progress" to verified. The
   mem-junction-**under-load** temp is still unmeasured → **the OEM-3090 repad decision remains
   deferred** (unchanged).
6. **ZFS deferred** (per Syed — not near-term). Storage/HBA work parked.
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

## 2026-06-22 — Fan control + thermal-monitoring toolchain

- **Chassis fans run in iDRAC manual mode via a closed-loop daemon** (`infrastructure/server/gpu-fan-control.sh`), not iDRAC auto. Reason: the iDRAC is structurally blind to the third-party 3090 and maxes the fans in auto; the daemon ramps the 2 shroud fans off a GPU-core curve (`max(gpu,cpu)`), with revert-to-auto as the dead-man's switch. PWM→RPM calibrated (~46 RPM/%); curve to be revised after the soak.
- **Mem-junction temp read method = direct BAR0 register reader, not nvidia-smi.** NVML doesn't expose GDDR6X junction temp on GeForce. Chosen tool: `ThomasBaruzier/gddr6-core-junction-vram-temps` (`gputemps`; core+junction+VRAM, 3090-tested, `--json`). Requires `iomem=relaxed` (Secure Boot N/A — legacy boot). Resolves the previously-flagged "how do we read mem-junction on Linux" blocker.
- **Repad-decision soak: memtest_vulkan primary** (hardest junction heat + apples-to-apples with the prior 106 °C Omen reading), **gpu-burn secondary** (compute load / real-workload proxy). Run with the fan daemon active so one soak validates the curve *and* yields the junction number. The repad decision itself stays deferred until that number exists.

---

## 2026-06-22 — Repad decision (data-backed) + soak-logger abort fix

- **Repad: DEFERRED, not urgent.** In-chassis 5-min memtest_vulkan put **VRAM (GDDR6X) at 100 °C** peak (hotspot 94, core 79; ~335 W, 22 °C inlet) — under the 110 °C ceiling, no throttle, no errors, and ~6 °C cooler than the Omen's 106 °C. Decision: don't repad now. Preferred next lever = **add chassis fans (being sourced) + re-soak** (fans were already ~94%, near the 2-fan airflow ceiling); repad is the fallback if VRAM won't drop under ~95 °C or the card runs in a hot room / 24-7. Data in `infrastructure/monitoring/memtest-soak.csv`; numbers in `PROGRESS.md`.
- **Column semantics (from gputemps source):** `junction` = GPU hotspot (`HOTSPOT_REGISTER`), `vram` = GDDR6X memory (`VRAM_REGISTER`). The **VRAM** column is the repad-relevant memory temp.
- **soak-logger auto-abort corrected:** it originally watched `junction` (hotspot) + `core` but not `vram` — the temp nearest its ceiling and the whole point of the soak. Now aborts on **vram** ≥108 too (the GDDR6X 110 °C ceiling, less 2 °C margin). The run that surfaced this was safe (100 < 108).
- **gpu-burn dropped (was the "secondary" soak tool) — unnecessary.** memtest_vulkan already pinned the 350 W power cap (so gpu-burn can't add total heat), gave the worst-case VRAM (gpu-burn heats memory less), and the card's compute/core stability was already validated in the Omen (OCCT 3D-Adaptive + FurMark). The real forward-looking validation is an actual inference/training run with the fan daemon + abort live, not another synthetic. gpu-burn stays cloned-unbuilt in `~/gpu-tools/`; build it for free if/when the CUDA toolkit lands for the ML work and a pure-compute datapoint is ever wanted.

---

## 2026-06-23 — Data pipeline design (refines project-purpose §6-7)

- **Corpus built to serve BOTH consumption modes; RAG-vs-fine-tune deferred to the held-out eval** (`ml/eval/`). Working hypothesis: *retrieve* precision-critical exact values (ECU tables/specs/scalars — the same numbers `car/safety/` needs), *fine-tune* reasoning + conceptual theory. Rationale: LLMs recall exact numbers from weights unreliably (interpolation/interference) and a confident near-miss value is engine-grenading — the **data-layer mirror of "LLM never writes ECU values."** (Decided with Syed after he correctly noted the "RAG = fresh data" argument doesn't apply to a static 2005-Subaru domain; the real driver is precision/verifiability, not freshness.)
- **Fine-tune set sizing revised: 500–2,000 reasoning exemplars (pilot ~500–1,000), NOT the bootstrap's 10k–50k.** "Less is more" (LIMA/QLoRA); 500 clean > 5,000 noisy; quality is also a *safety* property here. The retrievable fact store can be large.
- **Quality over quantity, decisively.**
- **Pipeline mirrors the Hardware Parser infra conventions** — config-driven source registry, `fetch()`+`REGISTRY`, sqlite WAL dedup on `(source,source_id)`, tenacity HTTP client, systemd oneshot/timer — **copied, not coupled** (no runtime dependency; the external scraper is untouched). `matcher.py` (deal logic) → our `gates.py` + the LLM judge.
- **Model selection (Stage B/C, does not change the corpus):** for ~48 GB (2×3090), **~32B at Q5/Q6** (context/KV headroom + practical QLoRA) over a cramped **70B-Q4**; **pilot at 7–14B**. Dataset size + retrieval method are model-agnostic.
- **Forums:** hit at normal pace, adaptive backoff only if blocked (per Syed); `requests`+`bs4` first, `patchright` fallback for Cloudflare/JS.
- **First slice shipped:** `romraider_defs` → 333 Subaru ECU definitions in `corpus.sqlite`.

---

## 2026-06-26 — EFI-reference corpus + judge architecture (no circularity) + PID note

- **Document `tier` field added:** `reference` (trusted/authoritative) vs `community` (noisy, needs judging). Tagged: RomRaider defs+logger, rusEFI docs, FSM/book PDFs, `ecu_docs` → **reference**; forums → **community**. Corpus now ~883 reference + 27 community.
- **`ecu_docs` source (HTML, reference tier):** the **MegaSquirt MegaManual** fundamentals (fuel equation `PW = REQ_FUEL × VE × MAP × E + …`, VE, tuning, injectors). PRIVATE-corpus use only (copyrighted, not redistributed). **rusEFI already covered** by `rusefi_docs` (its GitHub wiki = the same 387-file repo); **Speeduino redundant**; **AEM/Haltech skipped** (gated behind software + shallow public algorithm depth). Scope = "Open + MegaSquirt" (Syed).
- **Judge architecture — non-circular by construction (resolves Syed's concern):** the judge is a strong **general** model (Qwen2.5-32B), **NOT trained on the corpus it filters**. One-directional flow: raw → judge → curated → fine-tune the *main* model. The judge **grounds** noisy `community` claims against the `reference` tier (retrieved, not baked in) — "is this consistent with the rusEFI / MegaManual / FSM spec?" If a domain judge is ever fine-tuned, train it **only** on the reference tier, never the community tier it filters ("train-on-trusted, filter-untrusted"). + 5% human spot-check.
- **Judging deferred to the 48 GB (2×3090) setup** (a ~32B Q5/Q6 judge); the corpus accumulates until then.
- **PID note (refines the pending algorithm-layer build):** idle Stage-2 = feedforward table correction (the ECU's own closed-loop fuel PI tracks AFR in real time); the iterative `log→correct→reflash→re-log` loop = a **bounded-integral controller** (±3% clamp = anti-windup/rate-limit, designed as a damped PI to avoid overshoot); **boost control (Stage 3) is a real PID we tune**, informed by the rusEFI/ECUMaster boost-PID docs now in the corpus.

---

## 2026-06-27 — car/ecutune: deterministic algorithm + safety layer (offline build)

Built the offline tuning-algorithm + safety-clamp layer (`car/ecutune/`). Design choices, with reasoning:

- **Packaging: a self-contained `car/ecutune/` package + its own `.venv`/`requirements.txt`** (numpy, hypothesis), zero runtime import from `corpus_pipeline` — the scraper venv stays stdlib-lean ("copied, not coupled", same rule as vs Hardware Parser). Log-parser submodule named **`logparse`** (not `logging`) to avoid shadowing the stdlib.
- **Single write path: `safety.apply_proposal()`** is the only function that mutates a Table, enforced by a source-scan meta-test (no `.values[...] =` or `.with_edits(` outside `safety/` + `core.models`). This makes "the LLM never writes ECU values directly" *structural*, not a convention — the LLM becomes just another `Proposal` producer through the same clamp pipeline.
- **Clamp order — AFR floor runs LAST, after the ±3% rate-limit.** Lean-at-boost is the engine-grenade case, so the AFR floor is the final hard word on a boost AFR cell and is the one clamp permitted to richen past the per-iteration rate-limit (rich = safe; the rate-limit still bounds every *leaning* move). Full order: knock→ordering gates→boost gate→timing ceiling→ve-rate-limit→afr-floor.
- **Idle scalars are degenerate at one operating point.** Injector latency / flow-scaling / low-MAF all shift idle fuel, so the algorithm corrects the NET fuel error via the bounded controller and splits it by fixed priority weights (latency 0.2 / flow 0.7 / MAF 0.1 — "latency-first" lives in config, not physics). The loop converges *trim* to ±5%; the scalars settle at one of many trim-zeroing combinations (final flow ≈800 vs true 820 — fine, trim is the objective). Flagged for Syed: separating the scalars individually needs a log spanning a voltage/load range, not just idle.
- **Controller = bounded-integral / damped PI; the ±3% clamp IS the anti-windup** (conditional integration freezes the integral while saturated). Gains kp0.5 / ki0.05 / damping0.7 (~0.8% overshoot). The controller self-limits below ±3%, so the clamp never fires in normal operation (zero violations) — it is the backstop for a misbehaving proposer (incl. the future LLM).
- **MVEM fidelity: mean-value, steady-state, idle-fuel only.** No combustion/knock physics/transients; knock is a scripted test state for the abort clamp. Seeded mismatch (believed flow 850 vs true 820, latency 0.95 vs 1.0, MAF 0.98 vs 1.0 → +14.8% trim) is illustrative — flagged for Syed to set from the real swap. `synth_log` emits the exact `LogTable` shape `logparse` parses, so real logs replay through the same path when the wideband arrives.

---

## 2026-06-28 — Forester build spec locked; idle mismatch reframed (injectors MATCHED)

Syed provided the real build (recorded in `car/build-sheet.md` + `car/CLAUDE.md`): the swap keeps the
**entire OEM 2005 FXT intake manifold + injectors + wiring harness** on the OEM FXT ECU. This
**reframes the bad-idle theory** and the sim:

- **Injectors are OEM FXT side-feed ~500 cc/min — MATCHED to the stock ROM.** So injector scaling &
  latency are already correct; the earlier "injector scaling/latency" idle theory is **wrong for this
  build**. With matched injectors + MAF metering, the MVEM's delivered fuel equals the ECU's target and
  the idle fuel trim reduces algebraically to **1/maf_ratio − 1** — a *pure MAF-calibration error*
  (from the modified intake tract). Re-seeded `simulation/mismatch.py`: injectors matched (500 cc /
  1.0 ms), MAF believed 0.88 vs true 1.0 (~12% low) → +13.6% start trim. Harness now uses
  `BUILD_SPLIT = ScalarSplit(0,0,1)` so the correction goes entirely into MAF scaling; injector scalars
  stay put. Converges to <5% in 4 iters, 0 clamp violations, 31 tests green.
- **The real idle problem is engine-side, not fuel scaling:** 2.0 L-on-2.5 L VE/load model; exhaust-AVCS
  delete + TGV delete (overlap + low-rpm stability); timing too advanced for the 9.5:1 CR on 93 oct
  (EJ255 ROM is 8.4:1). These are **not fuel-trim errors** and are out of scope for the mean-value FUEL
  model — they need real logs + a richer model. Documented so the sim isn't over-trusted.
- **Corpus/forum grounding:** searches for this build should use EJ20X-into-FXT, OEM-FXT-manifold/injectors,
  TGV-delete, fully-catless, intake-AVCS-only — feeds the judge/retrieval later.
- **Best ROM source = read his own ECU** with the Openport (read-only, safe, no wideband needed) → exact
  factory calibration + the ROM ID. Community 2005 FXT stock ROMs also exist on the RomRaider forums
  (4EAT vs MT differ). A stock ROM upgrades the sim SEED to real numbers; it does not replace logs for
  *validation* (the ROM is what the ECU assumes, not how the EJ20X actually breathes).

### 2026-06-28 (revised same day, with Syed) — keep ALL fuel levers live; the data sets priorities

Correction to the note above. Syed's directive: do NOT exclude fueling or pre-prioritize any lever —
"everything most likely needs modifying, and reading the car is how we see what to prioritize." He is
right, and it's reinforced by the degeneracy I'd just identified: at one idle point a MAF error and an
injector error are indistinguishable in the trim, so locking the injectors (`BUILD_SPLIT = 0/0/1`) was
asserting a conclusion the data hasn't earned. **Reverted:** `ScalarSplit` default is now NEUTRAL
(0.34/0.33/0.33 — no prioritization, still configurable once logs inform it); `mismatch.py` seeds error
across ALL fuel levers (latency 0.96, flow 510, MAF 0.93 vs truth 1.0 / 500 / 1.0); the harness uses the
neutral split. All three scalars now move; converges +14.2% → 4.6% in 4 iters, 0 violations, 31 tests
green. Real per-lever attribution — and the cross-axis priorities (fuel vs timing vs AVCS vs idle-air) —
come from logs across operating conditions, which is the whole point of reading the car. Transmission
confirmed **4EAT** (fixes the ROM variant).

---

## 2026-07-03 — Universal-first corpus expansion + model-selection policy

**Context:** Syed's directive — the framework foundation is UNIVERSAL (every ECU exposes MAF/trims/
ECT/RPM/timing/VE — the SAE J1979 vocabulary); specificity layers on top. And: add every source not
yet ingested. Full review delivered in-chat (improvement map: semantic table layer, judge upgrades,
sim-generated eval — logged as follow-ups).

**Source expansion (built + live, 4 new sources + 1 gated):**
- **One generic phpBB engine** (`forum_phpbb.py`, bound per-site via `fetch_for()`) now serves THREE
  boards: `forum_speeduino` (universal open-EFI reasoning), `forum_msextra` (MegaSquirt theory),
  `forum_romraider` (Subaru tuning/logging/defs + stock-ROM threads; seeded with the 2005 FXT 4EAT
  stock-ROM thread). *Divergence from plan:* speeduino.com turned out to be phpBB, not Discourse
  (probed before building) — which collapsed two planned engines into one.
- **`tunerstudio_ini`**: speeduino.ini → 55 cross-platform table/curve definitions (reference tier) —
  the universal table vocabulary that will anchor the future semantic table layer.
- **`ecu_docs` + obd_pids**: Wikipedia OBD-II PIDs page (SAE J1979) — the universal channel anchor.
- **Wideband manuals**: AEM 30-0300 (+30-0310 inline, +FAE variant) PDFs → `local_pdf` (36 pages).
- **`forum_nasioc`: built but DISABLED** — NASIOC's Cloudflare managed challenge does not clear
  headless even with a new challenge-retry loop in BrowserFetcher (improvement kept; benefits
  legacygt). Revisit via one-time non-headless run or browser-cookie import.
- **ROM/log binary attachments need forum accounts** → Syed downloads manually into
  `data/raw/roms/` (gitignored); sources capture thread text/metadata only.
- Corpus after expansion: **1,026 docs (976 reference / 50 community)**; daily timer now accumulates
  from three new boards passively. 22 pipeline tests green.

**Model-selection policy (the durable lesson):** model choices are RE-VERIFIED against the current
landscape AT EXECUTION TIME, never asserted from training memory. (Syed caught the planned
Qwen2.5-32B judge being two generations stale — Qwen3.6 released 2026-04, after the agent's cutoff.)
- **Judge (as of 2026-07): Qwen3.6-35B-A3B at Q8_0** — MoE (3B active) lets Q8 run TODAY on the
  single 3090 + 32 GB RAM via llama.cpp expert offload; batch/overnight posture makes speed
  irrelevant. Dense alternative: Qwen3.6-27B (Q6 borderline on 24 GB; Q8 on 48 GB).
- **Quantization floor (Syed): Q6 minimum, Q8 preferred** for inference. (QLoRA's frozen NF4 base is
  a training-method standard, not subject to this floor.)
- **Fine-tune base (pilot): Qwen3.6-27B**, re-verify at pilot time.
- RAM pricing correction: the earlier $15–25/32GB DDR4 RDIMM figure was stale — prices rose with AI
  demand. RAM buy deferred to opportunistic (Syed watches for lots); NOT blocking: the judge fits
  the current 24 GB + 32 GB. **RAM spec for the parser: 32GB DDR4-2400 ECC RDIMM 2Rx4 PC4-19200
  288-pin 1.2V** (runs 1866 now on the v3, 2400 after the v4 swap; RDIMM not UDIMM/LRDIMM).

### 2026-07-03 (cont.) — XenForo forums + BrowserFetcher hardening; NASIOC gated

- **XenForo engine** (`forum_xenforo.py`, per-site bindings) → **forum_subaruforester** (Syed's exact
  chassis — engine-management-tuning-and-datalogging + EJ25-turbo-2004-2013 + EJ20-turbo nodes) and
  **forum_iwsti** (STI tuning). Both are VerticalScope boards behind a 202 JS stub → BrowserFetcher.
  Verified end-to-end (40-thread listing, a 20-post thread parsed with authors/dates).
- **VerticalScope is SLOW** (~25 s/page — the JS challenge clears in <9 s but ad-trackers keep
  networkidle from ever settling, so each page waits out a non-fatal timeout). Kept per-page timeout
  at 25 s + tight caps (discover_max_new 3, discover_max_pages 1, **max_thread_pages 3**) so nightly
  runs stay bounded; a full foreground `--once` exceeds a few minutes, which is fine for the systemd
  timer. **Lesson: do NOT reload-loop per page in the fetcher** — it multiplies the per-page cost on
  slow-challenge boards; single-pass non-fatal goto + wait_selector is correct.
- **BrowserFetcher hardening (shared, benefits legacygt too):** `wait_until` param (networkidle vs
  domcontentloaded), non-fatal goto, CF-interstitial re-read loop, and cookie injection. A
  persistent-context experiment rendered an empty body here and was reverted — kept launch()+new_context().
- **NASIOC: built, enabled, but cookie-GATED.** Confirmed its Cloudflare managed challenge cannot be
  cleared headless (persistent stealth ctx + interaction + reload all return the identical block).
  Path: cf_clearance cookie exported from Syed's home browser (same public IP as the T630 → valid)
  into `data/raw/.cf-cookies/nasioc.json`; `require_cf_cookies` auto-activates it once present.
- Sources now: 12 registry keys (6 forums + defs/logger/theory/efi/ini/pdf). 27 pipeline tests green.

### 2026-07-03 (cont.) — semantic table layer + sim-generated eval (autopilot queue)

- **Semantic table layer (car/ecutune):** algorithms + clamps now speak ONLY platform-neutral
  semantic IDs (`fuel.injector_flow`, `fuel.injector_latency`, `sensor.maf_transfer`,
  `fuel.target_afr_primary_a`, `ignition.*`, `boost.*`); platform names live in
  `ecutune/platforms/` adapters. `subaru_ecuflash` maps to the verified 2005 FXT (A2WC400x) names
  with VARIANTS absorbing per-def drift ("Injector Latency" vs "Injector Latency_"); a second
  `tunerstudio` adapter (injOpen/reqFuel/advTable1Tbl) proves the seam, with speed-density gaps as
  honest absences. Subaru is adapter #1 on a universal foundation — the structural encoding of
  Syed's universal-first directive. 35→40 tests green; convergence PASS unchanged.
- **Sim-generated diagnostic eval (ecutune/evals + ml/eval/data):** faults seeded in the MVEM
  (extended with `leak_air_g` unmetered air + `air_scale` operating points) → two-point datalog
  prompts in the universal channel vocabulary → scored against seeded truth. 7-fault taxonomy;
  leak-vs-dead-time degeneracy handled with acceptable-sets (separating them needs a voltage
  sweep — same doctrine as the real logging plan). **v1 artifact: 70 cases; rules baseline 85.7%
  top1 / 100% acceptable; random 18.6% / 25.7%** — the eval discriminates, and the future LLM
  evaluee must at least match rules. Eval DESIGN decisions (thresholds, taxonomy growth,
  RAG-vs-fine-tune protocol) stay Syed's learning thread.
- **Autopilot stop point:** queue complete up to the judge design session (learning-priority —
  not auto-built, per the root CLAUDE.md split).

### 2026-07-03 (cont.) — ROM-binary harvesting: attachments are gated, cookie is the key

Investigated login-free ROM sources per Syed ("shouldn't be trapped behind a login"). Findings:
archive.org has no Subaru ROM collection; GitHub has tuning *tools* but no ROM-binary repos;
SubaruDefs is defs-only. **RomRaider thread text is public but the attachment download 403s for
guests** (verified). So bulk ROMs realistically live as forum attachments behind a one-time login —
not an unbreakable wall, a cookie. Built **`rom_harvest.py`**: crawls the same phpBB threads we
already scrape, extracts `download/file.php?id=N` ROM attachments (strong exts always; archives only
if the filename hints a ROM), and downloads them **authenticated by a session cookie the user exports
once** into `data/raw/.cookies/<board>.txt` (same pattern as NASIOC cf_clearance). ROMs are car-side
files under `data/raw/roms/` + a manifest — NOT corpus Documents (binaries, and they feed the
ROM-value reader / reference library, not the LLM text corpus). CLI `--harvest-roms`; gated so it
skips cleanly (with guidance) until the cookie exists. Docs: `ml/data-pipeline/ROM_HARVEST.md`.
**The 2005 FXT 4EAT stock ROM (3B12504206) is attached to the seeded RomRaider thread** — Syed's
exact platform calibration, one cookie away. 31 pipeline tests green.

### 2026-07-04 — ROM-value reader + the sim grounded in the REAL FXT calibration

Both cookie gates opened today (NASIOC cf_clearance + RomRaider phpBB session) → `rom_harvest`
pulled 10/10 attachments including **the 2005 FXT 4EAT stock ROM (CID 3B12504206)**. Extracted the
1MB image from the EcuFlash `.srf` (INFO/DRMI/MEML/MEMD block container; MEMD = the ROM) — internal
ID at 0x2000 says **A2WC411D**, a revision with **no community def anywhere in SubaruDefs**.

**Decision: read via sibling revision defs with deterministic reconciliation, never guessing.**
New READ-ONLY `car/ecutune/romread/` (ECUFlash def parser incl. include-chain merge + value
reader). Empirical finding that shaped it: A2WC412D's late-ROM addresses are shifted +0x20 vs our
ROM (its latency read is non-monotonic garbage), while every A2WC410D read is physically sane →
411D shares the 410D layout. Rule codified in `read_semantic_tables()`: per table, defs that read
bit-identically corroborate; where they disagree, a candidate survives only if its axes are strictly
monotonic AND values sit inside the def's own min/max — and the survivor must be UNIQUE, else hard
error. Provenance is reported per table (`agree(...)` / `plausible-only(...)`).

**Decision: the sim's believed state now comes from the real ROM** (`simulation/rom_seed.py`,
CLI `--run-convergence --rom` / `--rom-report`). Believed = ROM facts: injector flow **503.93
cc/min** (the "~500cc matched injectors" prior is now a measured fact), latency curve interpolated
at 14.1V charging = **0.661 ms** (vs the 1.0 ms guess), hot idle target from the ROM's own table =
**700 rpm** (vs the 850 guess). Truth keeps the SAME neutral swap-uncertainty ratios as
`ej20x_into_ej255` (MAF ~7% low, flow ~2% high, latency ~4% low — no pre-decided culprit),
expressed relative to the real values. Result: **ROM-seeded convergence PASS** (+12.68% → +4.46%,
4 iters, 0 clamp violations) alongside the unchanged synthetic control (+14.18% → +4.56%). The
start-trim difference is physical: a 4% latency error on the real 0.66 ms dead time is a smaller
absolute fuel error than on the assumed 1.0 ms. 44 tests green (4 new romread).

No write path exists in romread by construction — ROM writes stay behind safety.apply_proposal.

### 2026-07-05 — Slot-3 Bus Fatal incident: locked GPU clocks are now mandatory on syedlab

Four hard system hangs during the first real judge inference runs (box alive, NIC dead — the
fatal PCIe error takes the root complex and the kernel's ability to log with it; only the iDRAC
SEL recorded each event: `Critical Interrupt — Bus Fatal Error (Slot 3)` x4).

**Eliminated one variable at a time:** cf. sessions/handoffs. Dual-PSU load sharing (crash #2
happened anyway), ASPM/link power management off via kernel params (crash #3), full physical
reseat of the 3090 (crash #4), cross-socket GPU P2P (crash #5 was SOLO on the 3090 — no P2P
traffic existed). A 1 Hz fsync'd flight recorder (infrastructure/monitoring/pcie-flight-
recorder.sh) proved the link was PRISTINE to the final second every time: Gen3 x16, zero
replays, zero correctable errors — instant fatal, no prelude. Firmware-first AER (Dell) is why
the kernel never saw anything.

**Mechanism (confirmed by discriminating experiment):** boost clocking oscillates the card
against its power limiter (recorded: 1065<->1500 MHz at 299W/300W cap) -> current transients
through slot 3's 12V -> momentary brownout of the card's PCIe logic -> one poisoned transaction
-> Bus Fatal. Steady loads never trigger it (30-min memtest soaks pass); bursty LLM inference
does. **With GPU0 core pinned at 1395 MHz: 15/15 bench requests, ~13 min sustained, zero
events** — nearly 2x the longest unlocked survival. Cost ~nil (inference is memory-bound; mem
clock untouched at 9501 MHz).

**Standing config:** gpu-powerlimit.service now also locks clocks at boot (GPU0 1395, Ti 1560).
Do NOT unlock without re-testing slot 3 under bursty load with the flight recorder armed.
**Open attribution:** card's transient appetite vs slot 3 board-side power delivery — settled
someday by swapping the cards between slots; not blocking (locked clocks are a legitimate
permanent operating mode; datacenter GPUs ship clock-capped for the same reason).

Bonus finding from the incident benches: temp-0 judge determinism is real — 15 identical
verdicts (score + token count) on identical input.

### 2026-07-06 — CARD CONVICTED: slot-swap test ends the Bus Fatal investigation

Crash #9 settled it. Full card swap (3090 -> CPU2 slot 7; Ti -> slot 3, RAID pins cleared):
provoked run (locks reset, caps kept — the historical trigger recipe) killed the box in ~40s of
load, SEL reporting **Slot 7** — the fault followed the HP OEM 3090 across the chassis while
the Ti boosted to 1890MHz in slot 3 in perfect health. Black box: 3090 bouncing 1575-1800MHz
at 269-273W (limiter oscillation), link clean to the last sample. Slot 3 exonerated after
eight wrongful accusations. Verdict: the card's own power-delivery/PCIe interface electronics
glitch under its own load transients.

**Supporting color:** Syed found the card's backplate screws show tamper evidence (paint
chipping/slight stripping) — someone was inside this card before purchase. Repad upgraded to
forensic teardown: document prior-rework evidence (flux residue, mismatched pads), inspect
12V input filtering + the six backside cap groups (the 2020 GA102 POSCAP/MLCC boost-crash
story matches our signature exactly), measure old pad thicknesses, clean/inspect edge fingers.

**Interim ops (Syed's option C):** dual-GPU batches at deepened margin — 3090 core lock
1200->1000 (measured load draw 215W vs 300W cap; limiter mathematically unreachable), Ti
unchanged. UUID-targeted service (slot-proof after the index-swap incident). Batches resume
via documented one-liner after each crash; DB snapshotted per stint; ~5-6h+ MTBF expected.
Endgame: repad/inspect the 3090, re-test with the 1-minute provoked-crash diagnostic, then
repair/retire/replace decision.

### 2026-07-22 — pilot-mix-v3 SIGNED (training set of record) + QLoRA goes fully hands-on

**Syed signed pilot-mix-v3** (280 pairs = 70 organic + 210 synthetic, 100% Claude-full-read,
drop audit ml/curation/docs/pilot-mix-v3-drops.txt). It is THE arm-C training set. Reviewed
via the new readable exports (claude.ai artifact viewer + pilot-mix-v3-readable.txt).
Known shape, accepted: synthetic split 20 subaru / 190 modern_general — Subaru weight rides
on the 70 organic + those 20; more pairs come post-wideband (Stage C gold). Wideband status:
power/ground wired, serial connections remain; Syed finishes computer side first.

**QLoRA plan change (supersedes 07-16 handoff):** NO autonomous prep. Syed runs every command
end-to-end (dataset prep -> train -> merge -> eval C), Claude teaches. His words: the judge
and RAG tests were agent-built; this one he needs to own. Memory: qlora-syed-drives.

### 2026-07-22 — gone-sweep policy RATIFIED (Syed): NARROW

Gone-ness (`gone_at` stamped when the live thread 404s) affects **scraping only** — never
judging, retrieval, or pair-mining. Archived judged text remains first-class corpus material
forever. Evidence: community batch 4 deliberately included gone-marked threads and produced
the best pair density of the synthesis effort (forums prune old threads; old correlates with
resolved). No cleanup pass may purge or exclude gone-marked docs from training/eval use.

### 2026-07-22 — E1v2 bar re-ratified (Syed): 90% top-1 + zero dangerous misses

Original A1 wording ("90% top-1 AND 100% acceptable") is degenerate on v2 where
acceptable==exact. Syed asked the right question — could the allowed 10% hide catastrophic
misses? Empirical audit of all 588 scored v2 cases: every miss was lean-family answered as a
different lean-family fault; zero fault->healthy, zero lean<->rich flips, misses byte-stable
across runs (temp-0 blind spot, concentrated on injector_latency_lean). New bar: **90% top-1
AND zero dangerous misses** (dangerous = fault answered healthy, or cross-family lean/rich
flip) — the E2-hard-gate analog for diagnosis. Doesn't change A/B verdicts; binds C/D.
DB meta eval.e1v2.preregistration amended with full definition + provenance.
