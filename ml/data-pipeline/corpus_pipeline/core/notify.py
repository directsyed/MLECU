"""Discord webhook notifier, a per-run corpus summary so runs are observable.

No-ops silently if no webhook is configured. Posts a compact embed: per-source new/fetched
counts, the titles just added, and any source errors. Never raises into the pipeline.
"""
from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)


def post_summary(webhook_url: str | None, results: list[dict], total_docs: int,
                 recent_titles: list[str] | None = None) -> None:
    if not webhook_url:
        return
    total_new = sum(r.get("new", 0) for r in results)
    errs = [r for r in results if not r.get("ok", True)]
    color = 0xE74C3C if errs else (0x2ECC71 if total_new else 0x95A5A6)  # red / green / grey

    lines = [
        f"`{r['source']}` +{r.get('new', 0)} (fetched {r.get('fetched', 0)})"
        + ("  ⚠️" if not r.get("ok", True) else "")
        for r in results
    ]
    desc = "\n".join(lines) or "(no sources ran)"
    if recent_titles:
        desc += "\n\n**Added this run:**\n" + "\n".join(f"• {t[:80]}" for t in recent_titles[:8])
    if errs:
        e = "; ".join(f"{r['source']}: {str(r.get('error'))[:80]}" for r in errs)
        desc += f"\n\n**Errors:** {e[:400]}"

    embed = {
        "title": f"MLECU corpus pass, +{total_new} new ({total_docs} docs total)",
        "description": desc[:4000],
        "color": color,
    }
    try:
        r = requests.post(webhook_url, json={"embeds": [embed]}, timeout=15)
        if r.status_code >= 300:
            log.warning("discord webhook returned %s: %s", r.status_code, r.text[:200])
    except Exception as e:  # never break a run over a notification
        log.warning("discord notify failed: %s", e)
