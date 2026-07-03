"""Patchright (stealth Playwright) fetcher — the JS/anti-bot fallback.

For sources whose WAF defeats plain `requests` (legacygt returns a 202 JS-challenge stub).
A real headless browser + `networkidle` + waiting for a content selector renders past the
challenge. Minimal singleton modeled on Hardware Parser's playwright_client.py; the oneshot
process teardown reaps Chromium, and close() is called explicitly by the source.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_DEFAULT_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/124.0.0.0 Safari/537.36")


class BrowserFetcher:
    """Lazily-launched headless Chromium context, reused across page fetches."""

    def __init__(self, user_agent: str | None = None, headless: bool = True):
        from patchright.sync_api import sync_playwright  # imported lazily (heavy dep)
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=headless, args=["--disable-blink-features=AutomationControlled"]
        )
        self._ctx = self._browser.new_context(
            user_agent=user_agent or _DEFAULT_UA,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )

    def get_html(self, url: str, *, wait_selector: str | None = None,
                 timeout: int = 45000, settle_ms: int = 4000,
                 challenge_retries: int = 4) -> str:
        pg = self._ctx.new_page()
        try:
            pg.goto(url, wait_until="networkidle", timeout=timeout)
            if wait_selector:
                try:
                    pg.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    log.debug("wait_selector %s not seen on %s", wait_selector, url)
            pg.wait_for_timeout(settle_ms)
            html = pg.content()
            # Cloudflare managed challenge: page says "Just a moment..." and swaps itself out
            # once cleared (5-15s). Re-read a few times instead of returning the stub.
            for _ in range(challenge_retries):
                if "Just a moment" not in html and "challenge-platform" not in html:
                    break
                log.debug("challenge page on %s — waiting for clearance", url)
                pg.wait_for_timeout(6000)
                if wait_selector:
                    try:
                        pg.wait_for_selector(wait_selector, timeout=8000)
                    except Exception:
                        pass
                html = pg.content()
            return html
        finally:
            pg.close()

    def close(self) -> None:
        for fn in (self._ctx.close, self._browser.close, self._pw.stop):
            try:
                fn()
            except Exception:
                pass
