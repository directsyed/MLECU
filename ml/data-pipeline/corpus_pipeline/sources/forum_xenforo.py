"""Generic XenForo forum ingester, ONE engine, multiple config-bound instances.

XenForo 2.x markup is stable across boards: /forums/<slug.NN>/ listings with div.structItem--thread,
/threads/<slug.NNNN>/ threads with article.message--post (author in the data-author attr, body in
.bbWrapper), page-N pagination. Concrete sources are bound in the registry via fetch_for():

  * forum_subaruforester, subaruforester.org  (Syed's exact chassis; incl. the
                           'engine-management-tuning-and-datalogging' + EJ25-turbo-2004-2013 nodes)
  * forum_iwsti, iwsti.com           (STI tuning; 'ecu-tuning-performance-electronics')

Both are VerticalScope boards behind a 202 JS stub (like legacygt) -> BrowserFetcher (patchright).
Whole thread -> one Document, mirroring the other forum sources.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import time
from typing import Callable, Iterator

from bs4 import BeautifulSoup

from ..core.browser import BrowserFetcher
from ..core.config import Config, SourceCfg
from ..core.http import HttpClient
from ..core.models import Document
from .base import safe_text

log = logging.getLogger(__name__)

name = "forum_xenforo"  # generic engine; Document.source comes from the bound instance
_THREAD = re.compile(r"/threads/([a-z0-9][a-z0-9-]*\.(\d+))/?")
_WAIT_LIST = ".structItem-title"
_WAIT_THREAD = ".message-body, .bbWrapper"

_DEFAULT_REJECT = ["for sale", "fs:", "f/s", "wtb", "group buy", "gb:", "raffle",
                   "for trade", "ft:", "sold", "wanted"]


def _slug_and_id(href: str) -> tuple[str, str] | None:
    m = _THREAD.search(href)
    return (m.group(1), m.group(2)) if m else None


def _thread_links(soup: BeautifulSoup) -> list[tuple[str, str, str]]:
    """(thread_id, slug, title) for each thread on a forum listing page."""
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for a in soup.select(".structItem-title a[href*='/threads/']"):
        si = _slug_and_id(a.get("href") or "")
        if not si:
            continue
        slug, tid = si
        if tid in seen:
            continue
        seen.add(tid)
        out.append((tid, slug, a.get_text(strip=True) or ""))
    return out


def _posts_from(soup: BeautifulSoup) -> list[tuple[str, str | None, str]]:
    out: list[tuple[str, str | None, str]] = []
    for art in soup.select("article.message--post, article.message"):
        body = art.select_one(".message-body .bbWrapper") or art.select_one(".bbWrapper")
        if body is None:
            continue
        # drop quoted blocks so we keep each poster's own words (quotes duplicate upstream posts)
        for q in body.select("blockquote, .bbCodeBlock--quote"):
            q.decompose()
        author = art.get("data-author") or safe_text(art.select_one(".message-name .username")) or "?"
        t = art.select_one(".message-attribution time[datetime]") or art.select_one("time[datetime]")
        date = t.get("datetime") if t else None
        text = body.get_text("\n", strip=True)
        if text:
            out.append((author, date, text))
    return out


def _max_page(soup: BeautifulSoup) -> int:
    pages = [1]
    for a in soup.select("a[href*='/page-']"):
        m = re.search(r"/page-(\d+)", a.get("href") or "")
        if m:
            pages.append(int(m.group(1)))
    return max(pages)


def _fetch_thread(bf: BrowserFetcher, base_url: str, slug: str, tid: str, max_pages: int,
                  delay: float, source_name: str, domain: str) -> Document | None:
    url0 = f"{base_url}/threads/{slug}/"
    soup = BeautifulSoup(bf.get_html(url0, wait_selector=_WAIT_THREAD, wait_until="networkidle", timeout=25000, settle_ms=2000), "lxml")
    title = safe_text(soup.select_one("h1.p-title-value") or soup.select_one("h1")) or f"thread {tid}"
    posts = _posts_from(soup)
    for pg in range(2, min(_max_page(soup), max_pages) + 1):
        time.sleep(delay)
        try:
            psoup = BeautifulSoup(bf.get_html(f"{url0}page-{pg}", wait_selector=_WAIT_THREAD,
                                              wait_until="networkidle", timeout=25000, settle_ms=2000), "lxml")
            posts += _posts_from(psoup)
        except Exception as e:
            log.warning("%s: page %d failed for %s: %s", source_name, pg, slug, e)
    if not posts:
        return None
    lines = [f"Forum thread: {title}", f"Source: {url0}", f"Posts: {len(posts)}", ""]
    for author, date, text in posts:
        lines.append(f"[{author}{' · ' + date if date else ''}]")
        lines += [text, ""]
    return Document(
        source=source_name, source_id=tid, title=title, text="\n".join(lines),
        kind="forum_thread", domain=domain, url=url0,
        meta={"thread_id": tid, "slug": slug, "post_count": len(posts),
              "authors": sorted({a for a, _, _ in posts})},
    )


def _known_ids(cfg: Config, source_name: str) -> set[str]:
    try:
        dbp = cfg.resolve(cfg.state.db_path)
        if not dbp.exists():
            return set()
        con = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
        try:
            return {r[0] for r in con.execute(
                "SELECT source_id FROM document WHERE source=?", (source_name,))}
        finally:
            con.close()
    except Exception:
        return set()


def _title_ok(title: str, keywords: list[str], reject: list[str]) -> bool:
    t = title.lower()
    if reject and any(r in t for r in reject):
        return False
    return not keywords or any(k in t for k in keywords)


def _fetch(source_name: str, cfg: Config, source_cfg: SourceCfg,
           http: HttpClient) -> Iterator[Document]:
    extra = source_cfg.model_extra or {}
    base_url = (extra.get("base_url") or "").rstrip("/")
    if not base_url:
        log.warning("%s: base_url not configured", source_name)
        return
    domain = extra.get("domain", "subaru")
    max_thread_pages = int(extra.get("max_thread_pages", 8))
    delay = max(0.5, 60.0 / max(1, source_cfg.rate_limit_per_min))
    seeds: list[str] = extra.get("seed_threads", [])
    forums: list[str] = [str(f) for f in extra.get("discover_forums", [])]

    ua = (cfg.pipeline.user_agent_pool or [None])[0]
    bf = BrowserFetcher(ua)
    try:
        skip = _known_ids(cfg, source_name)
        # 1) curated seeds (always re-fetched)
        for seed in seeds:
            si = _slug_and_id(seed)
            if not si:
                log.warning("%s: bad seed url %s", source_name, seed)
                continue
            slug, tid = si
            try:
                doc = _fetch_thread(bf, base_url, slug, tid, max_thread_pages, delay,
                                    source_name, domain)
            except Exception as e:
                log.warning("%s: seed %s failed: %s", source_name, slug, e)
                continue
            if doc:
                skip.add(tid)
                log.info("%s[seed]: %s (%d posts)", source_name, doc.title[:55], doc.meta["post_count"])
                yield doc
            time.sleep(delay)

        # 2) bounded discovery over configured forum nodes
        if not forums:
            return
        kws = [k.lower() for k in extra.get("discover_keywords", [])]
        rej = [r.lower() for r in extra.get("discover_reject_keywords", _DEFAULT_REJECT)]
        d_pages = int(extra.get("discover_max_pages", 2))
        d_new = int(extra.get("discover_max_new", 6))
        picked: list[tuple[str, str]] = []
        for node in forums:
            if len(picked) >= d_new:
                break
            for pg in range(1, d_pages + 1):
                listing = f"{base_url}/forums/{node}/" + (f"page-{pg}" if pg > 1 else "")
                try:
                    soup = BeautifulSoup(bf.get_html(listing, wait_selector=_WAIT_LIST,
                                                     wait_until="networkidle", timeout=25000, settle_ms=2000), "lxml")
                except Exception as e:
                    log.warning("%s: listing %s failed: %s", source_name, node, e)
                    break
                links = _thread_links(soup)
                if not links:
                    break
                for tid, slug, title in links:
                    if tid in skip or not _title_ok(title, kws, rej):
                        continue
                    skip.add(tid)
                    picked.append((slug, tid))
                    if len(picked) >= d_new:
                        break
                if len(picked) >= d_new:
                    break
                time.sleep(delay)
        for slug, tid in picked:
            time.sleep(delay)
            try:
                doc = _fetch_thread(bf, base_url, slug, tid, max_thread_pages, delay,
                                    source_name, domain)
            except Exception as e:
                log.warning("%s: discovered %s failed: %s", source_name, slug, e)
                continue
            if doc:
                log.info("%s[discovered]: %s (%d posts)", source_name, doc.title[:50],
                         doc.meta["post_count"])
                yield doc
    finally:
        bf.close()


def fetch_for(source_name: str) -> Callable[[Config, SourceCfg, HttpClient], Iterator[Document]]:
    """Bind the generic engine to a concrete registry key (Document.source == source_name)."""
    def fetch(cfg: Config, source_cfg: SourceCfg, http: HttpClient) -> Iterator[Document]:
        yield from _fetch(source_name, cfg, source_cfg, http)
    fetch.__name__ = f"fetch_{source_name}"
    return fetch
