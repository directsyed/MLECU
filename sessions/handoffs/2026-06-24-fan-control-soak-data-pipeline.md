# Handoff — 2026-06-24 — Fan control, GPU soak, data pipeline

**Type:** delta (since `2026-06-22-bootstrap.md`).

## Shipped since bootstrap
1. **GPU/server bring-up — closed out.**
   - Closed-loop **fan controller** (`infrastructure/server/gpu-fan-control.sh` + systemd unit, deployed & enabled), validated under real load (30% → ~94%, held core below throttle). PWM→RPM calibrated.
   - In-chassis **memtest_vulkan soak**: VRAM (GDDR6X) peaked **100 °C** (vs 106 °C in the Omen) → **repad DEFERRED** (warm-but-safe); revisit after adding chassis fans. gpu-burn dropped (redundant).
   - Unified **soak logger** (`infrastructure/monitoring/soak-logger.py`) with thermal **auto-abort** (vram/junction ≥108 °C or core ≥90 °C → fans 100% + kill load). Mem-junction read via `gputemps` (BAR0 register reader; `iomem=relaxed` is set). Tools live in `~/gpu-tools/`.

2. **Data pipeline — Stage A live** (`ml/data-pipeline/`, mirrors Hardware Parser conventions — copied, NOT coupled).
   - Config-driven corpus pipeline → `data/corpus.sqlite`. **884 docs / 4 sources, all gated `kept`, `judgment_status='pending'`:**
     - `romraider_defs` — 333 Subaru ECU definitions
     - `romraider_logger` — 219 SSM2 telemetry params (→ feeds `car/logging`)
     - `rusefi_docs` — 327 engine-management theory docs
     - `forum_legacygt` — 5 EJ20X threads / 158 posts (via **patchright headless-browser** fallback — legacygt's WAF blocks plain HTTP with a 202 JS-challenge)
   - 11 tests green. Run: `cd ml/data-pipeline && PYTHONPATH=. .venv/bin/python -m corpus_pipeline.cli --once` (then `--status`).

## Key decisions (see `decisions.md`)
- **RAG-vs-fine-tune deferred to the held-out eval**; corpus built to serve both. FT-set sizing **500–2k** (not 10k–50k). Quality > quantity (also a safety property).
- **Model selection (Stage B/C):** ~32B Q5/Q6 for the ~48 GB target; pilot 7–14B. Corpus is model-agnostic.
- **Forums:** normal pace + adaptive backoff; `requests`+`bs4` first, patchright fallback for JS/WAF.

## State
- Repo `~/Shared/Computing Projects/MLECU/`, private remote `directsyed/MLECU`, all pushed (HEAD `9f28e82`).
- Pipeline venv at `ml/data-pipeline/.venv` (incl. patchright + chromium). `data/`, `.venv/`, `corpus.sqlite` gitignored (regenerable).

## Next
1. **Corpus breadth** — more forum seeds + NASIOC; free-FSM PDFs; owner-supplied (books/FSM/ROM/logs) ingesters populate when Syed provides material.
2. **Stage B — the LLM judge** (Syed's learning thread): serve Qwen-32B on the 3090, score/extract pending docs → curated store. Note: the 333 ECU defs + 219 logger params are already clean structured facts; the judge mainly earns its keep on the forum/theory prose.
3. **Hardware:** add chassis fans (being sourced) → re-soak → settle the repad question.

## Watch-outs
- Forum scraping drives headless Chromium; one page timed out gracefully (per-page try/except). Keep seed lists curated (robots disallows `/search/`).
- Don't import/modify the external `Hardware Parser/` project — patterns were copied, not coupled.
