# ml/data-pipeline/

The **LLM-corpus data scraper** + ingestion — gathers *tuning knowledge* to build the fine-tuning corpus.

> ⚠ **Not the same** as the external `~/Shared/Computing Projects/Hardware Parser/` deal-scraper. That one hunts GPU/server deals and is out of scope. *This* one feeds the model.

**Status:** not started. **This is the first build after GPU/server bring-up** — the next doable thing while the car domain is hardware-blocked (no wideband yet).

**Will contain:** whitelist-driven scrapers/fetchers for the prioritized sources (RomRaider wiki + definitions, legacygt.com / NASIOC / IWSTI threads, the FSMs, the tuning books), raw→clean text normalization, per-chunk provenance, and the handoff into `../curation/`.

**Build-priority (Claude builds, then explains — see root CLAUDE.md):** whitelist-only ingestion; per-chunk gates (numbers/tables/logs? author tenure? thread resolved?); dedupe via embeddings downstream. Target corpus 10k–50k curated pairs.
