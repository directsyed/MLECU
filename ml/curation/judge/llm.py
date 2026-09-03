"""OpenAI-compatible client for llama-server. Grammar-enforced JSON via response_format.

llama.cpp compiles a json_schema response_format into a GBNF grammar that constrains sampling
itself, the model *cannot* emit schema-invalid JSON. verdict.py's parse/repair is therefore a
second line of defense (for truncation or a server without grammar support), not the primary.
"""
from __future__ import annotations

import json
import time
from typing import Any

import requests

from .config import LlmCfg


class LlmError(RuntimeError):
    pass


def health_check(cfg: LlmCfg) -> str:
    """Fail fast before a batch: returns the served model id."""
    try:
        r = requests.get(f"{cfg.base_url}/models", timeout=10)
        r.raise_for_status()
        data = r.json().get("data") or []
        return data[0]["id"] if data else "unknown"
    except Exception as e:
        raise LlmError(f"llama-server not reachable at {cfg.base_url}: {e}") from e


def chat(cfg: LlmCfg, system: str, user: str, json_schema: dict | None = None,
         retries: int = 3) -> tuple[str, dict[str, Any], str]:
    """One completion. Returns (content, usage, reasoning). Retries transport errors.

    Thinking models (Qwen3.6) emit deliberation as `reasoning_content`, kept separate from
    the grammar-constrained `content` by the server; we pass it through for the audit log."""
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
            "json_schema": {"name": "verdict", "strict": True, "schema": json_schema},
        }
    delay = 5.0
    last: Exception | None = None
    for _ in range(retries):
        try:
            r = requests.post(f"{cfg.base_url}/chat/completions", json=body,
                              timeout=cfg.request_timeout_s)
            r.raise_for_status()
            data = r.json()
            msg = data["choices"][0]["message"]
            return msg["content"], data.get("usage", {}), msg.get("reasoning_content") or ""
        except (requests.RequestException, KeyError, json.JSONDecodeError) as e:
            last = e
            time.sleep(delay)
            delay *= 2
    raise LlmError(f"chat failed after {retries} attempts: {last}") from last
