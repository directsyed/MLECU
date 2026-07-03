"""Generic phpBB forum ingester — ONE engine, multiple config-bound instances.

phpBB markup is stable across boards (viewforum.php?f=N listings, viewtopic.php?t=N threads,
start=K pagination), so one parser serves every phpBB site in the whitelist. Concrete sources
are bound in the registry via `fetch_for(<source_name>)`:

  * forum_speeduino  — speeduino.com/forum      (universal EFI reasoning; domain=general)
  * forum_msextra    — msextra.com/forums       (MegaSquirt theory goldmine; domain=general)
  * forum_romraider  — romraider.com/forum      (Subaru tuning/logging/defs + the stock-ROM
                       archive threads — text/metadata; ROM *attachments* need a logged-in
                       account, so binaries are Syed-manual into data/raw/roms/)

Plain HttpClient (both probed boards serve 200 to a browser UA); selectors cover prosilver and
subsilver2 themes. Whole thread -> one Document, mirroring forum_legacygt.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import time
from typing import Callable, Iterator

from bs4 import BeautifulSoup

from ..core.config import Config, SourceCfg
from ..core.http import HttpClient
from ..core.models import Document
from .base import safe_text

log = logging.getLogger(__name__)

name = "forum_phpbb"  # generic engine; Document.source comes from the bound instance name

_SID = re.compile(r"[?&]sid=[0-9a-f]+")
_T_ID = re.compile(r"[?&]t=(\d+)")
_START = re.compile(r"[?&]start=(\d+)")
_ATT_ID = re.compile(r"download/file\.php\?id=(\d+)")
# strong ROM formats (always a ROM) vs archives (ROM only if the filename hints it)
_ROM_EXT = re.compile(r"\.(srf|hex|bin|rom|mot|s19)$", re.I)
_ARCHIVE_EXT = re.compile(r"\.(zip|7z|rar|gz)$", re.I)
_ROM_HINT = re.compile(
    r"\brom\b|fxt|wrx|\bsti\b|legacy|forester|impreza|outback|baja|"
    r"stock|\becu\b|tune|base\s*map|basemap|4eat|5mt|6mt|[0-9A-Fa-f]{10,16}",
    re.I,
)


def attachment_links(soup: BeautifulSoup, base_url: str) -> list[tuple[str, str, str]]:
    """(attachment_id, filename, absolute_url) for ROM-like phpBB attachments in a thread.

    phpBB attachments are `download/file.php?id=N` anchors whose link text is the filename. We keep
    real ROM formats (.srf/.hex/.bin/...) unconditionally and archives (.zip/...) only when the
    filename hints a ROM (chassis code, "stock", or a ROM-id-like hex token). Avatars (`?avatar=`)
    are excluded.
    """
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for a in soup.select('a[href*="download/file.php?id="]'):
        href = _strip_sid(a.get("href") or "")
        m = _ATT_ID.search(href)
        if not m or "avatar=" in href:
            continue
        aid, fname = m.group(1), (a.get_text(strip=True) or "").strip()
        if not fname or aid in seen:
            continue
        is_rom = bool(_ROM_EXT.search(fname)) or (
            bool(_ARCHIVE_EXT.search(fname)) and bool(_ROM_HINT.search(fname)))
        if not is_rom:
            continue
        seen.add(aid)
        url = href if href.startswith("http") else f"{base_url}/{href.lstrip('./')}"
        out.append((aid, fname, url))
    return out

_DEFAULT_REJECT = ["for sale", "fs:", "f/s", "wtb", "group buy", "gb:", "raffle",
                   "for trade", "ft:", "meet", "gtg", "sold"]


def _strip_sid(url: str) -> str:
    return _SID.sub("", url)


def _topic_links(soup: BeautifulSoup, base_url: str) -> list[tuple[str, str, str]]:
    """(thread_id, title, absolute_url) for every topic link on a viewforum page."""
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for a in soup.select("a.topictitle"):
        href = _strip_sid(a.get("href") or "")
        m = _T_ID.search(href)
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        url = href if href.startswith("http") else f"{base_url}/{href.lstrip('./')}"
        out.append((m.group(1), a.get_text(strip=True) or "", url))
    return out


def _posts_from(soup: BeautifulSoup) -> list[tuple[str, str | None, str]]:
    """(author, date, text) per post. Covers prosilver (.post .content) and subsilver2 (.postbody)."""
    out: list[tuple[str, str | None, str]] = []
    posts = soup.select("div.post") or soup.select("div.postbody")
    for p in posts:
        content = p.select_one("div.content") if p.name == "div" and "post" in (p.get("class") or []) else p
        if content is None or not (content.get_text(strip=True) or ""):
            content = p.select_one("div.content") or p
        author_el = (p.select_one(".username") or p.select_one(".username-coloured")
                     or p.select_one("p.author strong") or p.select_one("b.postauthor"))
        author = safe_text(author_el) or "?"
        t = p.select_one("time")
        date = t.get("datetime") if t else None
        text = content.get_text("\n", strip=True)
        if text:
            out.append((author, date, text))
    return out


def _page_starts(soup: BeautifulSoup) -> list[int]:
    """Pagination offsets present on the page (phpBB paginates with &start=K)."""
    starts = {0}
    for a in soup.select("a[href*='start=']"):
        m = _START.search(a.get("href") or "")
        if m:
            starts.add(int(m.group(1)))
    return sorted(starts)


def _fetch_thread(http: HttpClient, host: str, base_url: str, tid: str,
                  max_pages: int, delay: float, source_name: str,
                  domain: str) -> Document | None:
    url0 = f"{base_url}/viewtopic.php?t={tid}"
    soup = BeautifulSoup(http.get_html(url0, host=host), "lxml")
    title = safe_text(soup.select_one("h2.topic-title a") or soup.select_one("h2 a")
                      or soup.select_one("h2") or soup.select_one("h3 a"))
    if not title and soup.title:  # theme without an h2 title (e.g. speeduino) -> <title> minus board name
        title = soup.title.get_text(strip=True).replace("\xa0", " ").rsplit(" - ", 1)[0].strip()
    title = title or f"thread {tid}"
    posts = _posts_from(soup)
    for start in _page_starts(soup)[1:max_pages]:
        time.sleep(delay)
        try:
            psoup = BeautifulSoup(http.get_html(f"{url0}&start={start}", host=host), "lxml")
            posts += _posts_from(psoup)
        except Exception as e:
            log.warning("%s: page start=%d failed for t=%s: %s", source_name, start, tid, e)
    if not posts:
        return None
    lines = [f"Forum thread: {title}", f"Source: {url0}", f"Posts: {len(posts)}", ""]
    for author, date, text in posts:
        lines.append(f"[{author}{' · ' + date if date else ''}]")
        lines += [text, ""]
    return Document(
        source=source_name, source_id=tid, title=title, text="\n".join(lines),
        kind="forum_thread", domain=domain, url=url0,
        meta={"thread_id": tid, "post_count": len(posts),
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
    host = base_url.split("//", 1)[-1].split("/", 1)[0]
    http.configure_host(host, source_cfg.rate_limit_per_min)
    domain = extra.get("domain", "general")
    max_thread_pages = int(extra.get("max_thread_pages", 8))
    delay = max(0.5, 60.0 / max(1, source_cfg.rate_limit_per_min))

    seeds: list[str] = extra.get("seed_threads", [])
    skip = _known_ids(cfg, source_name)

    # 1) curated seeds — always re-fetched (catches new posts on watched threads)
    for seed in seeds:
        m = _T_ID.search(seed)
        tid = m.group(1) if m else str(seed)
        try:
            doc = _fetch_thread(http, host, base_url, tid, max_thread_pages, delay,
                                source_name, domain)
        except Exception as e:
            log.warning("%s: seed t=%s failed: %s", source_name, tid, e)
            continue
        if doc:
            skip.add(tid)
            log.info("%s[seed]: %s (%d posts)", source_name, doc.title[:55], doc.meta["post_count"])
            yield doc
        time.sleep(delay)

    # 2) bounded discovery over configured subforums
    forums: list[int] = [int(f) for f in extra.get("discover_forums", [])]
    if not forums:
        return
    kws = [k.lower() for k in extra.get("discover_keywords", [])]
    rej = [r.lower() for r in extra.get("discover_reject_keywords", _DEFAULT_REJECT)]
    d_pages = int(extra.get("discover_max_pages", 4))
    d_new = int(extra.get("discover_max_new", 6))
    picked: list[tuple[str, str]] = []
    for f in forums:
        if len(picked) >= d_new:
            break
        page_size = 0
        for pg in range(d_pages):
            listing = f"{base_url}/viewforum.php?f={f}" + (f"&start={pg * page_size}" if pg else "")
            try:
                soup = BeautifulSoup(http.get_html(listing, host=host), "lxml")
            except Exception as e:
                log.warning("%s: listing f=%d failed: %s", source_name, f, e)
                break
            links = _topic_links(soup, base_url)
            if not links:
                break
            page_size = page_size or len(links)
            for tid, title, _url in links:
                if tid in skip or not _title_ok(title, kws, rej):
                    continue
                skip.add(tid)
                picked.append((tid, title))
                if len(picked) >= d_new:
                    break
            if len(picked) >= d_new:
                break
            time.sleep(delay)
    for tid, title in picked:
        time.sleep(delay)
        try:
            doc = _fetch_thread(http, host, base_url, tid, max_thread_pages, delay,
                                source_name, domain)
        except Exception as e:
            log.warning("%s: discovered t=%s failed: %s", source_name, tid, e)
            continue
        if doc:
            log.info("%s[discovered]: %s (%d posts)", source_name, doc.title[:50], doc.meta["post_count"])
            yield doc


def fetch_for(source_name: str) -> Callable[[Config, SourceCfg, HttpClient], Iterator[Document]]:
    """Bind the generic engine to a concrete registry key (Document.source == source_name)."""
    def fetch(cfg: Config, source_cfg: SourceCfg, http: HttpClient) -> Iterator[Document]:
        yield from _fetch(source_name, cfg, source_cfg, http)
    fetch.__name__ = f"fetch_{source_name}"
    return fetch
