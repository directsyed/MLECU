# ml/curation/

The **LLM-judge** curation engine.

**Status:** not started (built after the data scraper).

**Will contain:** the judge runner (plan: **Qwen2.5-32B-Instruct Q4** via llama.cpp/vLLM) scoring chunks 1–5 for substance/consistency, structured `(symptoms → diagnosis → change → outcome)` pair extraction (keep ≥4/5), ~5% human spot-check tooling, and embedding-based dedupe/clustering.

**Learning-priority — TEACH** (root CLAUDE.md): the LLM-judge is part of the ML stack Syed wants to learn. Explain the why, let him drive.
