# MLECU — Progress Log

Reverse-chronological (newest first). This is a portfolio/resume artifact — entries are written to be
legible to a technical reader who wasn't in the room. Performance numbers are also recorded in the
table at the bottom (date / metric / value / conditions) for a comparable history over time.

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
| 2026-06-22 | RTX 3090 mem-junction (under load) | *pending* | gpu-burn + memtest_vulkan soak — settles the repad decision |

*Add rows as benchmarks/evals/training runs produce numbers — GPU thermals, inference
throughput/latency, fine-tune eval scores, corpus size/quality, tuning-loop convergence.*
