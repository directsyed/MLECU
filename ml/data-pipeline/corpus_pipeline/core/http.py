"""Shared HTTP client: pooled session, UA rotation, retries, per-host rate limit.

Adapted (copied, not imported) from the Hardware Parser's core/http.py — it's generic
plumbing. Used by the scraping sources (forums); the git/file sources don't need it.
Politeness default + tenacity backoff on 429/5xx matches Syed's "hit normally, back off
if blocked."
"""
from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

log = logging.getLogger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """Retry transient errors only. 4xx except 429 are permanent."""
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError):
        resp = exc.response
        if resp is None:
            return True
        return resp.status_code == 429 or resp.status_code >= 500
    return False


class _TokenBucket:
    """Per-host bucket. `rate` = tokens/sec; bucket holds one minute's worth."""

    def __init__(self, per_minute: int):
        self.capacity = max(1, per_minute)
        self.rate = self.capacity / 60.0
        self.tokens = float(self.capacity)
        self.updated = time.monotonic()
        self.lock = threading.Lock()

    def take(self) -> None:
        with self.lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
            self.updated = now
            if self.tokens < 1:
                time.sleep((1 - self.tokens) / self.rate)
                self.tokens = 0
            else:
                self.tokens -= 1


class HttpClient:
    """One client shared by all sources. Per-host rate limiting + UA rotation."""

    def __init__(self, user_agents: list[str] | None = None):
        self.session = requests.Session()
        self.user_agents = user_agents or [
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ]
        self._buckets: dict[str, _TokenBucket] = {}
        self._buckets_lock = threading.Lock()

    def configure_host(self, host: str, per_minute: int) -> None:
        with self._buckets_lock:
            self._buckets[host] = _TokenBucket(per_minute)

    def _bucket_for(self, host: str) -> _TokenBucket:
        with self._buckets_lock:
            return self._buckets.setdefault(host, _TokenBucket(per_minute=30))

    def _ua(self) -> str:
        return random.choice(self.user_agents)

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=20),
        reraise=True,
    )
    def request(
        self,
        method: str,
        url: str,
        *,
        host: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 20.0,
        **kwargs: Any,
    ) -> requests.Response:
        time.sleep(random.uniform(0.1, 0.6))  # politeness jitter
        host = host or url.split("//", 1)[-1].split("/", 1)[0]
        self._bucket_for(host).take()
        merged = {"User-Agent": self._ua()}
        if headers:
            merged.update(headers)
        merged = {k: v for k, v in merged.items() if v is not None}
        resp = self.session.request(method, url, headers=merged, timeout=timeout, **kwargs)
        if resp.status_code == 429 or resp.status_code >= 500:
            log.warning("http %s on %s; will retry", resp.status_code, url)
            resp.raise_for_status()
        resp.raise_for_status()
        return resp

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def get_json(self, url: str, **kwargs: Any) -> Any:
        return self.get(url, **kwargs).json()

    def get_html(self, url: str, **kwargs: Any) -> str:
        return self.get(url, **kwargs).text
