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
