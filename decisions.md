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
