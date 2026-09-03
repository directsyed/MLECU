"""OpenAI-compatible llama-server client, adapted from ml/curation/judge/llm.py (kept as a
copy, not an import: the packages have separate venvs and the judge's client is coupled to its
pydantic config). Grammar-enforced JSON via response_format; latency measured per call."""
from __future__ import annotations

import json
import time
from typing import Any

import requests

from .config import LlmCfg


class LlmError(RuntimeError):
    pass


def health_check(cfg: LlmCfg) -> str:
    """Fail fast before a run: returns the served model id."""
    try:
        r = requests.get(f"{cfg.base_url}/models", timeout=10)
        r.raise_for_status()
        data = r.json().get("data") or []
        return data[0]["id"] if data else "unknown"
    except Exception as e:
        raise LlmError(f"llama-server not reachable at {cfg.base_url}: {e}") from e


def chat(cfg: LlmCfg, system: str, user: str, json_schema: dict | None = None,
         retries: int = 3) -> tuple[str, dict[str, Any], float]:
    """One completion. Returns (content, usage, latency_s). Retries transport errors."""
    body: dict[str, Any] = {
        "model": cfg.model,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_completion_tokens,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }
    if json_schema is not None:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "answer", "strict": True, "schema": json_schema},
        }
    delay = 5.0
    last: Exception | None = None
    for _ in range(retries):
        t0 = time.monotonic()
        try:
            r = requests.post(f"{cfg.base_url}/chat/completions", json=body,
                              timeout=cfg.request_timeout_s)
            r.raise_for_status()
            data = r.json()
            choice = data["choices"][0]
            usage = dict(data.get("usage", {}))
            # A2 (2026-08-02): finish_reason was never read or recorded, so an empty
            # completion from a model that exhausted its token budget was indistinguishable
            # from a model that chose to decline, and E2 scored the former as a virtue.
            usage["finish_reason"] = choice.get("finish_reason")
            return choice["message"]["content"], usage, time.monotonic() - t0
        except (requests.RequestException, KeyError, json.JSONDecodeError) as e:
            last = e
            time.sleep(delay)
            delay *= 2
    raise LlmError(f"chat failed after {retries} attempts: {last}") from last
