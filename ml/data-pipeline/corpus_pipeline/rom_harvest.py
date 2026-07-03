"""ROM-attachment harvester — pull ROM binaries the same way we pull posts, but targeting the
phpBB `download/file.php` attachments instead of the post text.

Reality (probed 2026-07-03): the thread *text* is public, but the attachment *download* needs a
logged-in session — RomRaider returns 403 to guests. So this is gated on a session cookie the user
exports ONCE from their own free account into data/raw/.cookies/<board>.txt (raw `Cookie:` header
value) or .json ({name: value}) — the same one-time-cookie pattern as the NASIOC cf_clearance path.
It's not a wall we can't pass, it's a cookie: with it, we download exactly like the user's browser.

ROMs feed the CAR side (the car/ecu ROM-value reader + a reference library of stock/tuned ROMs), not
the LLM text corpus, so they land as FILES under data/raw/roms/<board>/ with a JSON manifest — never
as corpus Documents. Everything here is gitignored (data/raw/).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup

from .core.config import Config
from .core.http import HttpClient
from .sources.forum_phpbb import _T_ID, _title_ok, _topic_links, attachment_links

log = logging.getLogger(__name__)

_ROM_ID = re.compile(r"\b([0-9A-Fa-f]{10,16})\b")
_HTML_HEAD = (b"<!doctype", b"<!DOCTYPE", b"<html", b"<HTML")


def _host(url: str) -> str:
    return url.split("//", 1)[-1].split("/", 1)[0]


def load_cookie(cfg: Config, path: str) -> str | None:
    """Return a `Cookie:` header string from a raw-header .txt or a {name: value} .json, or None."""
    p = cfg.resolve(path)
    if not p.exists():
        return None
    txt = p.read_text(encoding="utf-8").strip()
    if not txt:
        return None
    if txt.startswith("{"):
        try:
            d = json.loads(txt)
            return "; ".join(f"{k}={v}" for k, v in d.items())
        except Exception as e:
            log.warning("rom_harvest: bad cookie json %s: %s", p, e)
            return None
    return txt


def _guess_rom_id(fname: str) -> str | None:
    m = _ROM_ID.search(fname)
    return m.group(1) if m else None


def _looks_like_html(data: bytes) -> bool:
    head = data[:64].lstrip()
    return any(head.startswith(h) for h in _HTML_HEAD)


def _discover_rom_threads(http: HttpClient, base: str, host: str, headers: dict,
                          board: dict) -> list[str]:
    """Scan configured subforums for ROM-titled threads (title keyword filter)."""
    urls: list[str] = []
    kws = [k.lower() for k in board.get("title_keywords", [])]
    d_pages = int(board.get("discover_max_pages", 2))
    d_new = int(board.get("discover_max_new", 20))
    for f in board.get("subforums", []):
        if len(urls) >= d_new:
            break
        page_size = 0
        for pg in range(d_pages):
            listing = f"{base}/viewforum.php?f={f}" + (f"&start={pg * page_size}" if pg else "")
            try:
                soup = BeautifulSoup(http.get_html(listing, host=host, headers=headers), "lxml")
            except Exception as e:
                log.warning("rom_harvest: listing f=%s failed: %s", f, e)
                break
            links = _topic_links(soup, base)
            if not links:
                break
            page_size = page_size or len(links)
            for tid, title, url in links:
                if _title_ok(title, kws, []):
                    urls.append(url)
                    if len(urls) >= d_new:
                        break
            if len(urls) >= d_new:
                break
    return urls


def harvest(cfg: Config, http: HttpClient) -> dict:
    hc = cfg.rom_harvest or {}
    if not hc.get("enabled", False):
        return {"downloaded": 0, "skipped": 0, "blocked": 0, "reason": "disabled"}
    out_dir = cfg.resolve(hc.get("out_dir", "data/raw/roms"))
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest: dict = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    downloaded = skipped = blocked = 0
    for board in hc.get("boards", []):
        bname = board["name"]
        base = board["base_url"].rstrip("/")
        host = _host(base)
        cookie = load_cookie(cfg, board.get("cookie_file", f"data/raw/.cookies/{bname}.txt"))
        if not cookie:
            log.warning("rom_harvest[%s]: no session cookie — SKIP. Log in on %s, export the "
                        "phpBB cookie to data/raw/.cookies/%s.txt (attachments 403 for guests).",
                        bname, base, bname)
            continue
        headers = {"Cookie": cookie}
        http.configure_host(host, int(board.get("rate_limit_per_min", 8)))
        delay = max(0.6, 60.0 / max(1, int(board.get("rate_limit_per_min", 8))))

        thread_urls = list(board.get("threads", []))
        thread_urls += _discover_rom_threads(http, base, host, headers, board)

        for turl in thread_urls:
            try:
                soup = BeautifulSoup(http.get_html(turl, host=host, headers=headers), "lxml")
            except Exception as e:
                log.warning("rom_harvest[%s]: thread %s failed: %s", bname, turl, e)
                continue
            for aid, fname, aurl in attachment_links(soup, base):
                key = f"{bname}:{aid}"
                if key in manifest:
                    skipped += 1
                    continue
                time.sleep(delay)
                try:
                    resp = http.get(aurl, host=host, headers=headers)
                    data = resp.content
                except Exception as e:
                    log.warning("rom_harvest[%s]: attachment %s (%s) blocked: %s",
                                bname, aid, fname, str(e)[:80])
                    blocked += 1
                    continue
                if not data or _looks_like_html(data):
                    log.warning("rom_harvest[%s]: attachment %s returned HTML (login/expired cookie?)",
                                bname, aid)
                    blocked += 1
                    continue
                safe = re.sub(r"[^A-Za-z0-9._-]+", "_", fname).strip("_") or f"rom_{aid}"
                dest = out_dir / bname / f"{aid}_{safe}"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                manifest[key] = {
                    "board": bname, "thread": turl, "filename": fname,
                    "rom_id": _guess_rom_id(fname), "bytes": len(data),
                    "sha1": hashlib.sha1(data).hexdigest(), "path": str(dest.relative_to(out_dir)),
                }
                downloaded += 1
                log.info("rom_harvest[%s]: got %s (%d bytes) rom_id=%s",
                         bname, fname, len(data), manifest[key]["rom_id"])

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return {"downloaded": downloaded, "skipped": skipped, "blocked": blocked,
            "total_known": len(manifest), "out_dir": str(out_dir)}
