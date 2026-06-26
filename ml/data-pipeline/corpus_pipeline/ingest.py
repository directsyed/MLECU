"""Ingestion orchestrator: enabled sources → gates → raw store.

Analogous to Hardware Parser's poller.py _one_pass(): for each enabled source, fetch raw
Documents, run the cheap gates, upsert into corpus.sqlite, then sweep stale docs. Each
source is isolated in try/except so one failure never kills the pass.
"""
from __future__ import annotations

import logging

from .core import gates, notify
from .core.config import Config, env, load_config
from .core.http import HttpClient
from .core.state import State
from .sources import REGISTRY

log = logging.getLogger(__name__)


def run_source(name: str, cfg: Config, state: State, http: HttpClient, dry_run: bool) -> dict:
    source_cfg = cfg.sources[name]
    fetch = REGISTRY[name]
    run_id = state.start_poll_run(name)
    fetched = kept = new = 0
    seen_ids: list[str] = []
    error = None
    try:
        for doc in fetch(cfg, source_cfg, http):
            fetched += 1
            seen_ids.append(doc.source_id)
            gates.apply(doc, cfg.gates)
            if doc.gate_status == "kept":
                kept += 1
            if not dry_run:
                _id, was_new = state.upsert_document(doc)
                if was_new:
                    new += 1
        if not dry_run:
            gone = state.sweep_gone(name, seen_ids, cfg.state.gone_after_misses)
            if gone:
                log.info("%s: %d docs marked gone", name, gone)
        state.finish_poll_run(run_id, ok=True, fetched=fetched, kept=kept, new_count=new)
    except Exception as e:
        error = repr(e)
        log.exception("source %s failed", name)
        state.finish_poll_run(run_id, ok=False, fetched=fetched, kept=kept, new_count=new, error=error)
    return {"source": name, "fetched": fetched, "kept": kept, "new": new, "ok": error is None, "error": error}


def one_pass(only: list[str] | None = None, dry_run: bool = False,
             config_path: str | None = None) -> list[dict]:
    cfg = load_config(config_path)
    enabled = [n for n, s in cfg.sources.items() if s.enabled and n in REGISTRY]
    if only:
        enabled = [n for n in enabled if n in set(only)]
    if not enabled:
        log.warning("no enabled+known sources to run (asked: %s)", only or "all")
    http = HttpClient(cfg.pipeline.user_agent_pool)
    state = State(cfg.resolve(cfg.state.db_path)) if not dry_run else _DryState(cfg)
    results = []
    for name in enabled:
        res = run_source(name, cfg, state, http, dry_run)
        log.info("source %s: fetched=%d kept=%d new=%d ok=%s",
                 name, res["fetched"], res["kept"], res["new"], res["ok"])
        results.append(res)
    if not dry_run:
        _maybe_notify(cfg, state, results)
        state.close()
    return results


def _maybe_notify(cfg: Config, state: State, results: list[dict]) -> None:
    """Post a Discord run summary if configured (DISCORD_WEBHOOK_URL in secrets.env)."""
    if not cfg.notify.enabled:
        return
    webhook = env(cfg.notify.discord_webhook_env)
    if not webhook:
        return
    total_new = sum(r["new"] for r in results)
    if total_new == 0 and cfg.notify.only_when_new:
        return
    try:
        recent = state.recent_titles(min(total_new, 8)) if total_new else []
        notify.post_summary(webhook, results, state.total_docs(), recent)
    except Exception as e:
        log.warning("notify step failed: %s", e)


class _DryState:
    """No-op state for --dry-run: counts but never writes."""

    def __init__(self, cfg: Config):
        self._rid = 0

    def start_poll_run(self, source: str) -> int:
        self._rid += 1
        return self._rid

    def finish_poll_run(self, *a, **k) -> None: ...
    def upsert_document(self, doc): return (0, True)
    def sweep_gone(self, *a, **k) -> int: return 0
    def close(self) -> None: ...
