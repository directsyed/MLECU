# ml/data-pipeline/

Config-driven ingestion of automotive tuning knowledge → a clean, **structured,
provenance-tagged** raw store (`data/corpus.sqlite`) for the Stage-B LLM judge. Mirrors the
Hardware Parser conventions (copied, **not** coupled, separate project).

**Status (2026-06-24):** 5 sources live → ~884+ docs. `romraider_defs` (333 ECU defs),
`romraider_logger` (219 SSM2 telemetry params), `rusefi_docs` (327 theory), `forum_legacygt`
(EJ20X threads via patchright + bounded **discovery**), `local_pdf` (owner-supplied PDFs).
A **daily systemd timer** runs the pass automatically (see `systemd/README.md`).

## Owner-supplied PDFs (FSMs, books)
Drop files under `data/raw/pdfs/` then run `--sources local_pdf`:
- `data/raw/pdfs/fsm/` → Subaru FSMs (kind=`fsm_spec`, domain=`subaru`)
- `data/raw/pdfs/books/` → tuning/theory books (kind=`theory`, domain=`general`)

One Document per page; scanned/image-only PDFs yield no text (the run logs "NO TEXT LAYER", needs
OCR). This folder is gitignored, copyrighted PDFs are never committed.

## Layout
- `config.yaml`: **source registry** + pipeline config (gates, state, per-source keys via pydantic `extra=allow`).
- `corpus_pipeline/core/`: `config.py` (pydantic + lru-cached load) · `models.py` (`Document` + `SCHEMA_SQL`) · `state.py` (sqlite WAL, dedup on `(source, source_id)`, `poll_run` health, idempotent `_migrate`) · `http.py` (shared client: per-host rate-limit, UA rotation, tenacity retries) · `gates.py` (cheap text-quality gates + flags).
- `corpus_pipeline/sources/`: `base.py` (`Source` protocol) · `__init__.py` (`REGISTRY`) · one module per source. `romraider_defs.py` is the slice.
- `corpus_pipeline/ingest.py`: orchestrator (per-source `try/except` isolation). `cli.py`: `--once` / `--sources` / `--dry-run` / `--status` / `--debug`.
- `data/` (gitignored), `raw/` source cache + `corpus.sqlite`. `tests/`: pytest (gates + parser).

## Run
```bash
cd ml/data-pipeline
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=. .venv/bin/python -m corpus_pipeline.cli --once --sources romraider_defs
PYTHONPATH=. .venv/bin/python -m corpus_pipeline.cli --status
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q
```

## Add a source
New `sources/<x>.py` with `name` + `fetch(cfg, source_cfg, http) -> Iterator[Document]`; import + add to `REGISTRY`; add a `sources.<x>` block in `config.yaml`. To add a `Document` field, wire it through `models` (+`SCHEMA_SQL`), `state._migrate()`, and `state.upsert_document()` (Hardware Parser discipline).

## Pipeline (per the plan)
1. **Ingest** (here) → gates → `corpus.sqlite` (provenance + `judgment_status='pending'`).
2. **Judge** (`../curation/`) → LLM scores/extracts → curated store.
3. **Split** → retrievable structured fact store + small fine-tune set.
4. **Eval** (`../eval/`) decides RAG vs fine-tune empirically.

**Next sources:** `rusefi_docs`, free-FSM PDFs, then the forums; owner-supplied (books/FSM/ROM/logs) populate as material lands. Forums: normal pace + adaptive backoff if blocked; `requests`+`bs4` first, `patchright` fallback for Cloudflare/JS.
