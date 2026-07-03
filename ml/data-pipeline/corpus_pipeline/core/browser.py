"""Patchright (stealth Playwright) fetcher — the JS/anti-bot fallback.

For sources whose WAF defeats plain `requests`: legacygt (202 JS-challenge stub — cleared by a real
headless browser + networkidle + waiting for a content selector) and NASIOC (Cloudflare *managed*
challenge — NOT clearable headless; needs an injected cf_clearance cookie, see cookies=).

Design note: launch()+new_context() with a viewport/UA is what actually renders legacygt here;
launch_persistent_context returned an empty body on this box (verified), so we do NOT use it. The
challenge-retry loop re-reads until a Cloudflare "Just a moment..." interstitial swaps to content.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_DEFAULT_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/124.0.0.0 Safari/537.36")


class BrowserFetcher:
    """Headless Chromium context, reused across page fetches.

    cookies: optional list of Playwright cookie dicts (e.g. a real-browser cf_clearance for a hard
    managed challenge — must come from the same public IP + matching UA as this host).
    profile_dir is accepted for call-site compatibility but unused (persistent context misbehaves here).
    """

    def __init__(self, user_agent: str | None = None, headless: bool = True,
                 profile_dir=None, cookies: list[dict] | None = None):
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
        if cookies:
            try:
                self._ctx.add_cookies(cookies)
            except Exception as e:
                log.warning("cookie injection failed: %s", e)

    def get_html(self, url: str, *, wait_selector: str | None = None,
                 timeout: int = 45000, settle_ms: int = 4000,
                 challenge_retries: int = 6) -> str:
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
            # Cloudflare managed challenge: "Just a moment..." swaps out once JS clears (5-15s).
            for _ in range(challenge_retries):
                if "Just a moment" not in html and "challenge-platform" not in html \
                        and "cf-browser-verification" not in html:
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
