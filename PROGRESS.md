# MLECU — Progress Log

Reverse-chronological (newest first). This is a portfolio/resume artifact — entries are written to be
legible to a technical reader who wasn't in the room. Performance numbers are also recorded in the
table at the bottom (date / metric / value / conditions) for a comparable history over time.

---

## 2026-06-23 — Data pipeline: vertical slice live (RomRaider defs)

**Built** (`ml/data-pipeline/`, mirroring Hardware Parser conventions — copied, not coupled):
- Config-driven corpus pipeline: `core/` (pydantic config, `Document` + SQLite schema, WAL state
  with `(source,source_id)` dedup + `poll_run` health, shared HTTP client, text-quality gates),
  `sources/` (`Source` protocol + `REGISTRY`), orchestrator with per-source isolation, and a CLI
  (`--once / --sources / --dry-run / --status`).
- First ingester `romraider_defs`: clones RomRaider SubaruDefs (GPL-2.0), parses ECUFlash per-ROM
  XML → structured `Document`s (ROM identity + tunable-table list + provenance).

**Result — 879 documents in `corpus.sqlite`, all gated `kept`, pending judge:**
- `romraider_defs` — **333 Subaru ECU definitions** (666 files → 333 after standard/metric dedup).
- `romraider_logger` — **219 SSM2 telemetry params** (the loggable-channel schema → feeds `car/logging`).
- `rusefi_docs` — **327 engine-management theory docs** (general). Dedup verified (re-run `new=0`); tests green.

**Next:** forum ingester (legacygt EJ20X — needs the JS/`patchright` path); then free-FSM + owner-supplied; then Stage B (the LLM judge — Syed's learning thread).

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

*Add rows as benchmarks/evals/training runs produce numbers — GPU thermals, inference
throughput/latency, fine-tune eval scores, corpus size/quality, tuning-loop convergence.*
