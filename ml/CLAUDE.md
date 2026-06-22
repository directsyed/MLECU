# ml/ — The Connective ML Layer

Loaded when working on the data pipeline, curation, fine-tuning, inference, or eval.
This layer bridges the domains: **compute (infra) serves fine-tuning serves the car.**

## Subdirs
- `data-pipeline/` — the **LLM-corpus data scraper** + ingestion (gathers tuning knowledge for the model).
- `curation/` — the **LLM-judge** scorer (1–5 substance/consistency) + structured-pair extraction.
- `finetuning/` — QLoRA configs, dataset prep, training runs.
- `inference/` — serving (llama.cpp / vLLM), quantization.
- `eval/` — held-out eval set + the **RAG-vs-fine-tune comparison** (the gate that authorizes EPYC spend).

## IMPORTANT — two different scrapers, never conflate
- **`data-pipeline/` (IN SCOPE — build here):** scrapes *tuning knowledge* (forums, FSMs, RomRaider wiki, books) to build the fine-tuning corpus.
- **`~/Shared/Computing Projects/Hardware Parser/` (EXTERNAL — out of scope):** the hardware-**deal** scraper. Do not import or modify it.

## The plan (soft foundation — refine freely, log divergences in ../decisions.md)
- **LLM-judge curation:** a quantized ~30B model (plan floated **Qwen2.5-32B-Instruct Q4** via llama.cpp/vLLM) scores scraped content for substance/consistency, extracts `(symptoms → diagnosis → change → outcome)` pairs; keep ≥4/5; ~5% human spot-check. Embeddings for dedupe/clustering (re-quoted posts bias toward popularity, not correctness). Runs as a continuous background workload.
- **Source whitelist (priority):** tuning books (Banish *Engine Management: Advanced Tuning*; Bell *Maximum Boost*; Heywood *IC Engine Fundamentals*); FSMs (2005 Forester + JDM Legacy GT for the EJ20X); the RomRaider wiki/definitions; forums (RomRaider, NASIOC, **legacygt.com** — EJ20X-swap goldmine, IWSTI, MegaSquirt/rusEFI for theory); data artifacts (posted RomRaider logs, before/after ROM diffs, dyno threads with numbers).
- **Curation rules:** whitelist-only ingestion; per-chunk gates (numbers/tables/logs? author tenure? thread resolved? pure opinion → discard).
- **Target corpus:** 10k–50k curated pairs / ~100–500 MB clean text. *Pollution costs more than scale pays.*
- **Fine-tune:** pilot **QLoRA 7B–14B** once ~2–5k pairs exist; build a held-out eval; **a pilot fine-tune must beat a RAG baseline** on it before any big hardware spend. Endgame compute (EPYC) is gated on (a) that eval passing AND (b) ambitions exceeding 24GB VRAM.

## Sequence (per the June 22 interview)
1. (infra) close out GPU/server bring-up.
2. **Build the data scraper** — the next doable thing (wideband not acquired → car logging blocked).
3. **LLM-judge curation engine.**

## Learning mode (root CLAUDE.md)
The **LLM/ML work is learning-priority — TEACH it** (explain the why, let Syed drive, don't auto-complete). The **scraper/parsers are build-priority — you build, then explain the design + mechanics.**
