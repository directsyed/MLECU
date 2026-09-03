# ml/: The Connective ML Layer

Loaded when working on the data pipeline, curation, fine-tuning, inference, or eval.
This layer bridges the domains: compute (infra) serves fine-tuning serves the car.

## Subdirs
- `data-pipeline/`: the **LLM-corpus data scraper** + ingestion (gathers tuning knowledge for the model).
- `curation/`: the **LLM-judge** scorer (1–5 substance/consistency) + structured-pair extraction.
- `finetuning/`: QLoRA configs, dataset prep, training runs.
- `inference/`: serving (llama.cpp / vLLM), quantization.
- `eval/`: held-out eval set + the **RAG-vs-fine-tune comparison** (the gate that authorizes EPYC spend).

## IMPORTANT: two different scrapers, never conflate
- **`data-pipeline/` (IN SCOPE, build here):** scrapes *tuning knowledge* (forums, FSMs, RomRaider wiki, books) to build the fine-tuning corpus.
- `~/Shared/Computing Projects/Hardware Parser/` (EXTERNAL, out of scope): the hardware-**deal** scraper. Do not import or modify it.

## The plan (soft foundation, refine freely, log divergences in ../decisions.md)
- **LLM-judge curation:** a quantized ~30B-class model scores scraped content for substance/consistency, extracts `(symptoms → diagnosis → change → outcome)` pairs; keep ≥4/5; ~5% human spot-check. Embeddings for dedupe/clustering (re-quoted posts bias toward popularity, not correctness). Runs as a batch/overnight workload. Model policy (decisions.md 2026-07-03): re-verify the latest open model at execution time, never assert from training memory. As of 2026-07: Qwen3.6-35B-A3B @ Q8 (MoE expert-offload fits the single 3090 + 32 GB RAM today). Quantization floor: Q6 min / Q8 preferred (Syed).
- **Source whitelist (priority):** tuning books (Banish ×2; Bell *Maximum Boost*; Cramer/Hoffmann; Heywood, full list given to Syed 2026-07-03, drop into `data/raw/pdfs/books/`); FSMs (2005 Forester + JDM Legacy GT for the EJ20X); the RomRaider wiki/definitions; forums, LIVE: legacygt, speeduino, msextra, romraider.com (phpBB engine), subaruforester.org, iwsti.com (XenForo engine); BUILT-BUT-GATED: NASIOC (hard Cloudflare, needs a home-browser cf_clearance cookie); cross-platform defs (**tunerstudio_ini**, 55 docs) + OBD-II PIDs (J1979); wideband manuals (AEM 30-0300 ingested); data artifacts (posted RomRaider logs, before/after ROM diffs, *binary attachments need Syed's forum accounts → `data/raw/roms/`*).
- **Curation rules:** whitelist-only ingestion; per-chunk gates (numbers/tables/logs? author tenure? thread resolved? pure opinion → discard).
- **Target corpus:** 10k–50k curated pairs / ~100–500 MB clean text. *Pollution costs more than scale pays.*
- **Fine-tune:** pilot **QLoRA 7B–14B** once ~2–5k pairs exist; build a held-out eval; **a pilot fine-tune must beat a RAG baseline** on it before any big hardware spend. Endgame compute (EPYC) is gated on (a) that eval passing AND (b) ambitions exceeding 24GB VRAM.

## Sequence (per the June 22 interview)
1. (infra) close out GPU/server bring-up.
2. **Build the data scraper**: the next doable thing (wideband not acquired → car logging blocked).
3. **LLM-judge curation engine.**

## HARD RULE: local-LLM output review (Syed, 2026-07-09; hardened 2026-07-15)
Everything a local LLM generates (judge verdicts aside; those have their own calibration
protocol) gets a Claude review pass before it is promoted, trained on, or used as eval
truth. The review judges BOTH axes, multiplied (Syed's formulation): structural quality
(grounding, causal depth, dedup/diversity) WEIGHTED BY fit to the project's CURRENT need
(ROADMAP phase + car working theory define "current"). A batch review without a
needs-alignment census + supply math against the actual target is incomplete; that
omission shipped a 725-pair "supply solved" verdict that was ~30% usable (2026-07-15).
Systematic problems → fix the prompt and regenerate, never hand-patch. Claude review
supplements Syed's sign-off sampling; it never replaces it.

## Learning mode (root CLAUDE.md)
The **LLM/ML work is learning-priority, TEACH it** (explain the why, let Syed drive, don't auto-complete). The scraper/parsers are build-priority; you build, then explain the design + mechanics.
