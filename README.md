# MLECU

**AI-assisted automotive ECU tuning system on a self-hosted ML compute stack.**

MLECU pairs a **fine-tuned LLM reasoning/diagnosis layer** with **deterministic, hard-clamped
execution.** OBD2/ECU log data feeds an LLM that interprets telemetry, diagnoses problems, and
proposes calibration changes — but **every actual ECU value change is made by deterministic,
human-reviewed algorithms with provable bounds. The LLM never writes ECU values directly.** Flexible
diagnosis, guaranteed-safe execution.

The test vehicle is a **2005 Subaru Forester XT with a JDM EJ20X swap**; the first milestone is making
it idle and drive correctly. The compute half — a Dell PowerEdge T630 with RTX 3090-class GPUs —
exists to serve the automotive half (data curation, fine-tuning, inference).

## Architecture (one repo, domain-partitioned)

| Path | What |
|------|------|
| `CLAUDE.md` | Lean, always-loaded agent context + behavior rules |
| `context/` | Vision/methodology, live hardware state, principles (+ `bootstrap-source/` provenance) |
| `infrastructure/` | The T630, GPUs, power, networking, monitoring |
| `ml/` | Data pipeline, LLM-judge curation, fine-tuning, inference, eval |
| `car/` | The ECU project — including `safety/`, the write-path guard |
| `sessions/handoffs/` | Self-written session handoffs (continuity) |
| `PROGRESS.md` | Reverse-chronological progress + performance numbers |
| `decisions.md` | Append-only decision log |

## Status (2026-06-22)

- **Compute:** T630 up; 1× RTX 3090 live (driver 580 / CUDA 13). Next: close out bring-up (fan curve + mem-junction-under-load soak), then build the data-curation pipeline.
- **Car:** dormant — blocked on acquiring a wideband (the ground-truth instrument).

## Safety note

The deterministic-execution / LLM-never-writes separation (`car/safety/`) is a hard architectural
requirement, not a convenience. See `car/CLAUDE.md`.
