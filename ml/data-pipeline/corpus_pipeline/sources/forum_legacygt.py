"""legacygt.com forum ingester. Subaru EJ20X-swap reasoning threads (IPS Community).

legacygt's WAF defeats plain HTTP (202 JS-challenge stub), so this source uses the patchright
BrowserFetcher fallback (per the approved plan). robots.txt allows /topic/ (only /search/ is
disallowed), so we DON'T crawl search, instead we fetch a curated list of high-signal thread
URLs (`seed_threads` in config) + their pagination, and emit one Document per thread.

Each Document is a full thread (title + every post with author/date), a reasoning conversation,
exactly the (symptom → diagnosis → change → outcome) material the Stage-B judge curates.
"""
from __future__ import annotations

import logging
import re
import sqlite3
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
_BASE = "https://www.legacygt.com"
_WAIT = '.ipsType_richText, [data-role="commentContent"]'
# Coarse in-domain TITLE filter for discovery. The subforum scope already constrains to Subaru
# EJ tuning; this just drops obvious off-topic. The Stage-B judge does the deep relevance/quality call.
_DEFAULT_KEYWORDS = [
    # platform / engine, the EJ25 <-> EJ20X realm
    "ej20x", "ej20y", "ej20", "ej255", "ej257", "ej25", "spec b",
    # tuning intent
    "swap", "tune", "tuning", "base map", "basemap", "ots map", "fuel map", "romraider",
    "accessport", "cobb", "ecutek", "dyno", "knock", "fueling", "fuel trim", "closed loop",
    "open loop", "boost target", "boost control", "wastegate", "injector", "timing", "afr",
    "stage 1", "stage 2",
]
_DEFAULT_REJECT = [
    "for sale", "fs:", "f/s", "wtb", "group buy", "gb:", "raffle", "for trade", "ft:",
    "meet", "gtg", "sold",
]


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


def _known_ids(cfg: Config) -> set[str]:
    """Existing forum_legacygt thread ids (read-only) so discovery skips re-fetching them."""
    try:
        dbp = cfg.resolve(cfg.state.db_path)
        if not dbp.exists():
            return set()
        con = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
        try:
            return {r[0] for r in con.execute("SELECT source_id FROM document WHERE source=?", (name,))}
        finally:
            con.close()
    except Exception:
        return set()


def _discover(bf: BrowserFetcher, forum_url: str, keywords: list[str], reject: list[str],
              max_pages: int, limit: int, skip: set[str]) -> list[str]:
    """Crawl a subforum listing; return URLs of NEW in-domain topics (capped at `limit`).

    Walks up to `max_pages` listing pages for COVERAGE/backfill, `skip` already holds every
    stored thread id, so once the recent threads are captured, later runs reach deeper/older
    unseen ones. A title is taken iff it matches a keyword AND no reject term.
    """
    out: list[str] = []
    base = forum_url.rstrip("/")
    for pg in range(1, max_pages + 1):
        listing = base + (f"/page/{pg}/" if pg > 1 else "/")
        try:
            soup = BeautifulSoup(bf.get_html(listing, wait_selector='a[href*="/topic/"]'), "lxml")
        except Exception as e:
            log.warning("discover listing failed %s: %s", listing, e)
            break
        for a in soup.select(".ipsDataItem_title a"):
            href = a.get("href") or ""
            title = (a.get_text(strip=True) or "").lower()
            m = re.search(r"/topic/(\d+)-", href)
            if not m or m.group(1) in skip:
                continue
            if keywords and not any(k in title for k in keywords):
                continue
            if reject and any(r in title for r in reject):
                continue
            skip.add(m.group(1))
            out.append(href if href.startswith("http") else _BASE + href)
            if len(out) >= limit:
                return out
    return out


def fetch(cfg: Config, source_cfg: SourceCfg, http: HttpClient) -> Iterator[Document]:
    extra = source_cfg.model_extra or {}
    seeds: list[str] = extra.get("seed_threads", [])
    discover_forums: list[str] = extra.get("discover_forums", [])
    max_pages = int(extra.get("max_pages", 10))
    delay = max(0.5, 60.0 / max(1, source_cfg.rate_limit_per_min))
    if not seeds and not discover_forums:
        log.warning("forum_legacygt: nothing configured (seed_threads / discover_forums)")
        return
    ua = (cfg.pipeline.user_agent_pool or [None])[0]
    bf = BrowserFetcher(ua)
    try:
        # 1) curated seeds, always re-fetched (catches new posts on watched threads)
        for url in seeds:
            try:
                doc = _fetch_thread(bf, url, max_pages, delay)
            except Exception as e:
                log.warning("thread failed %s: %s", url, e)
                continue
            if doc:
                log.info("legacygt[seed]: %s (%d posts)", doc.title[:55], doc.meta["post_count"])
                yield doc
            time.sleep(delay)
        # 2) discovery, bounded crawl for NEW keyword-matching threads (passive accumulation)
        if discover_forums:
            kws = [k.lower() for k in extra.get("discover_keywords", _DEFAULT_KEYWORDS)]
            rej = [r.lower() for r in extra.get("discover_reject_keywords", _DEFAULT_REJECT)]
            d_pages = int(extra.get("discover_max_pages", 8))
            d_new = int(extra.get("discover_max_new", 8))
            skip = _known_ids(cfg) | {_thread_id(u) for u in seeds}
            new_urls: list[str] = []
            for furl in discover_forums:
                if len(new_urls) >= d_new:
                    break
                new_urls += _discover(bf, furl, kws, rej, d_pages, d_new - len(new_urls), skip)
            for url in new_urls:
                time.sleep(delay)
                try:
                    doc = _fetch_thread(bf, url, max_pages, delay)
                except Exception as e:
                    log.warning("discovered thread failed %s: %s", url, e)
                    continue
                if doc:
                    log.info("legacygt[discovered]: %s (%d posts)", doc.title[:50], doc.meta["post_count"])
                    yield doc
    finally:
        bf.close()
