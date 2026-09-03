"""NASIOC forum ingester, vBulletin behind Cloudflare (patchright BrowserFetcher path).

forums.nasioc.com serves a Cloudflare challenge to plain HTTP (probed 403), so this source uses
the same BrowserFetcher fallback as forum_legacygt. vBulletin 3.x markup: forumdisplay.php?f=N
listings with a[id^="thread_title_"], showthread.php?t=N threads with div[id^="post_message_"],
&page=N pagination. Whole thread -> one Document (subaru/community), mirroring the other forums.
"""
from __future__ import annotations

import json
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


def _load_cf_cookies(cfg: Config, rel: str) -> list[dict] | None:
    """Load cf_clearance (+ session) cookies exported from Syed's home browser. Format: a JSON list
    of Playwright cookie dicts, or a {name: value} map (converted to .nasioc.com cookies). Absent =>
    source stays gated (headless can't solve NASIOC's managed challenge unaided)."""
    try:
        p = cfg.resolve(rel)
        if not p.exists():
            return None
        raw = json.loads(p.read_text())
        if isinstance(raw, dict):
            return [{"name": k, "value": v, "domain": ".nasioc.com", "path": "/"}
                    for k, v in raw.items()]
        return raw or None
    except Exception as e:
        log.warning("nasioc: cookie file unreadable: %s", e)
        return None

name = "forum_nasioc"
_BASE = "https://forums.nasioc.com/forums"
_T_ID = re.compile(r"[?&]t=(\d+)")
_PAGE = re.compile(r"[?&]page=(\d+)")
_WAIT_THREAD = 'div[id^="post_message_"]'
_WAIT_LIST = 'a[id^="thread_title_"]'

_DEFAULT_REJECT = ["for sale", "fs:", "f/s", "wtb", "group buy", "gb:", "raffle",
                   "for trade", "ft:", "meet", "gtg", "sold"]


def _thread_links(soup: BeautifulSoup, base_url: str) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for a in soup.select('a[id^="thread_title_"]'):
        href = a.get("href") or ""
        m = _T_ID.search(href) or re.search(r"thread_title_(\d+)", a.get("id") or "")
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        url = href if href.startswith("http") else f"{base_url}/{href.lstrip('./')}"
        out.append((m.group(1), a.get_text(strip=True) or "", url))
    return out


def _posts_from(soup: BeautifulSoup) -> list[tuple[str, str | None, str]]:
    """vB3: each post is a table id="post<N>"; author a.bigusername; body div#post_message_<N>."""
    out: list[tuple[str, str | None, str]] = []
    tables = soup.select('table[id^="post"]')
    if tables:
        for tb in tables:
            body = tb.select_one('div[id^="post_message_"]')
            if body is None:
                continue
            author = safe_text(tb.select_one("a.bigusername") or tb.select_one(".username")) or "?"
            text = body.get_text("\n", strip=True)
            if text:
                out.append((author, None, text))
    else:  # fallback: bodies without the enclosing table (theme variants)
        for body in soup.select('div[id^="post_message_"]'):
            text = body.get_text("\n", strip=True)
            if text:
                out.append(("?", None, text))
    return out


def _max_page(soup: BeautifulSoup) -> int:
    pages = [1]
    for a in soup.select("a[href*='page=']"):
        m = _PAGE.search(a.get("href") or "")
        if m:
            pages.append(int(m.group(1)))
    return max(pages)


def _fetch_thread(bf: BrowserFetcher, base_url: str, tid: str, max_pages: int,
                  delay: float) -> Document | None:
    url0 = f"{base_url}/showthread.php?t={tid}"
    soup = BeautifulSoup(bf.get_html(url0, wait_selector=_WAIT_THREAD), "lxml")
    title = safe_text(soup.select_one("td.navbar strong") or soup.select_one("h1")
                      or soup.select_one("title")) or f"NASIOC thread {tid}"
    posts = _posts_from(soup)
    for pg in range(2, min(_max_page(soup), max_pages) + 1):
        time.sleep(delay)
        try:
            psoup = BeautifulSoup(bf.get_html(f"{url0}&page={pg}", wait_selector=_WAIT_THREAD), "lxml")
            posts += _posts_from(psoup)
        except Exception as e:
            log.warning("nasioc: page %d failed for t=%s: %s", pg, tid, e)
    if not posts:
        return None
    lines = [f"Forum thread: {title}", f"Source: {url0}", f"Posts: {len(posts)}", ""]
    for author, date, text in posts:
        lines.append(f"[{author}{' · ' + date if date else ''}]")
        lines += [text, ""]
    return Document(
        source=name, source_id=tid, title=title, text="\n".join(lines),
        kind="forum_thread", domain="subaru", url=url0,
        meta={"thread_id": tid, "post_count": len(posts),
              "authors": sorted({a for a, _, _ in posts})},
    )


def _known_ids(cfg: Config) -> set[str]:
    try:
        dbp = cfg.resolve(cfg.state.db_path)
        if not dbp.exists():
            return set()
        con = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
        try:
            return {r[0] for r in con.execute(
                "SELECT source_id FROM document WHERE source=?", (name,))}
        finally:
            con.close()
    except Exception:
        return set()


def fetch(cfg: Config, source_cfg: SourceCfg, http: HttpClient) -> Iterator[Document]:
    extra = source_cfg.model_extra or {}
    base_url = (extra.get("base_url") or _BASE).rstrip("/")
    seeds: list[str] = extra.get("seed_threads", [])
    forums: list[int] = [int(f) for f in extra.get("discover_forums", [])]
    max_thread_pages = int(extra.get("max_thread_pages", 8))
    delay = max(0.5, 60.0 / max(1, source_cfg.rate_limit_per_min))
    if not seeds and not forums:
        log.warning("forum_nasioc: nothing configured (seed_threads / discover_forums)")
        return

    ua = (cfg.pipeline.user_agent_pool or [None])[0]
    cookie_file = extra.get("cf_cookie_file", "data/raw/.cf-cookies/nasioc.json")
    cookies = _load_cf_cookies(cfg, cookie_file)
    if cookies is None and extra.get("require_cf_cookies", True):
        log.warning("nasioc: no cf_clearance cookie at %s, skipping (managed challenge). "
                    "Export it from a browser on the T630's network + matching UA.", cookie_file)
        return
    profile = str(cfg.resolve("data/raw/.cf-nasioc-profile"))
    bf = BrowserFetcher(ua, profile_dir=profile, cookies=cookies)
    try:
        # Canary probe (2026-07-07): cf_clearance cookies for this site live only HOURS. A dead
        # cookie previously produced silent "ok, fetched=0" nightly runs, indistinguishable
        # from a genuinely quiet forum. Probe one page first and FAIL LOUDLY so the run summary
        # (and Discord ping) shows the real reason instead of a silent zero.
        canary = bf.get_html(f"{base_url}/forumdisplay.php?f=80")
        if "Just a moment" in (canary or "") or "challenge-platform" in (canary or ""):
            raise RuntimeError(
                "cf_clearance cookie EXPIRED (Cloudflare challenge on canary page). "
                "Re-export from the home browser (SAME browser/UA) to "
                "data/raw/.cf-cookies/nasioc.json")
        skip = _known_ids(cfg)
        for seed in seeds:
            m = _T_ID.search(seed)
            tid = m.group(1) if m else str(seed)
            try:
                doc = _fetch_thread(bf, base_url, tid, max_thread_pages, delay)
            except Exception as e:
                log.warning("nasioc: seed t=%s failed: %s", tid, e)
                continue
            if doc:
                skip.add(tid)
                log.info("nasioc[seed]: %s (%d posts)", doc.title[:55], doc.meta["post_count"])
                yield doc
            time.sleep(delay)

        if not forums:
            return
        kws = [k.lower() for k in extra.get("discover_keywords", [])]
        rej = [r.lower() for r in extra.get("discover_reject_keywords", _DEFAULT_REJECT)]
        d_pages = int(extra.get("discover_max_pages", 3))
        d_new = int(extra.get("discover_max_new", 6))
        picked: list[str] = []
        for f in forums:
            if len(picked) >= d_new:
                break
            for pg in range(1, d_pages + 1):
                listing = f"{base_url}/forumdisplay.php?f={f}" + (f"&page={pg}" if pg > 1 else "")
                try:
                    soup = BeautifulSoup(bf.get_html(listing, wait_selector=_WAIT_LIST), "lxml")
                except Exception as e:
                    log.warning("nasioc: listing f=%d failed: %s", f, e)
                    break
                for tid, title, _url in _thread_links(soup, base_url):
                    t = title.lower()
                    if tid in skip or (rej and any(r in t for r in rej)):
                        continue
                    if kws and not any(k in t for k in kws):
                        continue
                    skip.add(tid)
                    picked.append(tid)
                    if len(picked) >= d_new:
                        break
                if len(picked) >= d_new:
                    break
                time.sleep(delay)
        for tid in picked:
            time.sleep(delay)
            try:
                doc = _fetch_thread(bf, base_url, tid, max_thread_pages, delay)
            except Exception as e:
                log.warning("nasioc: discovered t=%s failed: %s", tid, e)
                continue
            if doc:
                log.info("nasioc[discovered]: %s (%d posts)", doc.title[:50], doc.meta["post_count"])
                yield doc
    finally:
        bf.close()
