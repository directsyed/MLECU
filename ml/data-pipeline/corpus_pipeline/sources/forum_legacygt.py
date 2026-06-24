"""legacygt.com forum ingester — Subaru EJ20X-swap reasoning threads (IPS Community).

legacygt's WAF defeats plain HTTP (202 JS-challenge stub), so this source uses the patchright
BrowserFetcher fallback (per the approved plan). robots.txt allows /topic/ (only /search/ is
disallowed), so we DON'T crawl search — instead we fetch a curated list of high-signal thread
URLs (`seed_threads` in config) + their pagination, and emit one Document per thread.

Each Document is a full thread (title + every post with author/date) — a reasoning conversation,
exactly the (symptom → diagnosis → change → outcome) material the Stage-B judge curates.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Iterator

from bs4 import BeautifulSoup

from ..core.browser import BrowserFetcher
from ..core.config import Config, SourceCfg
from ..core.http import HttpClient
from ..core.models import Document
from .base import safe_text

log = logging.getLogger(__name__)

name = "forum_legacygt"
_WAIT = '.ipsType_richText, [data-role="commentContent"]'


def _thread_id(url: str) -> str:
    m = re.search(r"/topic/(\d+)", url)
    return m.group(1) if m else url.rstrip("/").rsplit("/", 1)[-1]


def _max_page(soup: BeautifulSoup) -> int:
    pages = [1]
    for a in soup.select('a[href*="/page/"]'):
        m = re.search(r"/page/(\d+)", a.get("href", ""))
        if m:
            pages.append(int(m.group(1)))
    return max(pages)


def _posts_from(soup: BeautifulSoup) -> list[tuple[str, str | None, str]]:
    out: list[tuple[str, str | None, str]] = []
    for art in (soup.select('[id^="elComment_"]') or soup.select("article")):
        content = art.select_one('[data-role="commentContent"]') or art.select_one(".ipsType_richText")
        if content is None:
            continue
        author_el = art.select_one(".cAuthorPane_author a") or art.select_one(".ipsType_break")
        author = safe_text(author_el) or "?"
        t = art.select_one("time")
        date = t.get("datetime") if t else None
        text = content.get_text("\n", strip=True)
        if text:
            out.append((author, date, text))
    return out


def _fetch_thread(bf: BrowserFetcher, url: str, max_pages: int, delay: float) -> Document | None:
    base = url.rstrip("/")
    soup = BeautifulSoup(bf.get_html(url, wait_selector=_WAIT), "lxml")
    title = safe_text(soup.select_one("h1")) or f"legacygt thread {_thread_id(url)}"
    n_pages = min(_max_page(soup), max_pages)
    posts = _posts_from(soup)
    for pg in range(2, n_pages + 1):
        time.sleep(delay)
        try:
            psoup = BeautifulSoup(bf.get_html(f"{base}/page/{pg}/", wait_selector=_WAIT), "lxml")
            posts += _posts_from(psoup)
        except Exception as e:
            log.warning("page %d failed for %s: %s", pg, url, e)
    if not posts:
        return None
    lines = [f"Forum thread: {title}", f"Source: {url}", f"Posts: {len(posts)}", ""]
    for author, date, text in posts:
        lines.append(f"[{author}{' · ' + date if date else ''}]")
        lines += [text, ""]
    tid = _thread_id(url)
    return Document(
        source=name, source_id=tid, title=title, text="\n".join(lines),
        kind="forum_thread", domain="subaru", url=url,
        meta={"thread_id": tid, "post_count": len(posts), "pages": n_pages,
              "authors": sorted({a for a, _, _ in posts})},
    )


def fetch(cfg: Config, source_cfg: SourceCfg, http: HttpClient) -> Iterator[Document]:
    extra = source_cfg.model_extra or {}
    seeds: list[str] = extra.get("seed_threads", [])
    max_pages = int(extra.get("max_pages", 10))
    delay = max(0.5, 60.0 / max(1, source_cfg.rate_limit_per_min))
    if not seeds:
        log.warning("forum_legacygt: no seed_threads configured")
        return
    ua = (cfg.pipeline.user_agent_pool or [None])[0]
    bf = BrowserFetcher(ua)
    try:
        for url in seeds:
            try:
                doc = _fetch_thread(bf, url, max_pages, delay)
            except Exception as e:
                log.warning("thread failed %s: %s", url, e)
                continue
            if doc:
                log.info("legacygt: %s (%d posts)", doc.title[:60], doc.meta["post_count"])
                yield doc
            time.sleep(delay)
    finally:
        bf.close()
