"""Config loader: YAML + .env, validated with pydantic. One global cached load.

Mirrors the Hardware Parser config.py convention: pydantic models, lru-cached load_config(),
a SourceCfg with `extra='allow'` so each source reads its own keys via `model_extra`.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]   # .../ml/data-pipeline/
DEFAULT_CONFIG = REPO_ROOT / "config.yaml"
DEFAULT_SECRETS = REPO_ROOT / "secrets.env"

_DEFAULT_UA = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
]


class PipelineCfg(BaseModel):
    data_dir: str = "data"            # relative to REPO_ROOT unless absolute
    user_agent_pool: list[str] = Field(default_factory=lambda: list(_DEFAULT_UA))


class StateCfg(BaseModel):
    db_path: str = "data/corpus.sqlite"
    gone_after_misses: int = 3


class GatesCfg(BaseModel):
    min_chars: int = 40               # drop near-empty fragments
    require_alpha: bool = True        # must contain some letters (not pure markup/numbers)


class SourceCfg(BaseModel):
    enabled: bool = True
    rate_limit_per_min: int = 30
    # Per-source extras (repo_url, local_path, subforums, ...) reachable via model_extra.
    model_config = {"extra": "allow"}


class NotifyCfg(BaseModel):
    enabled: bool = True
    discord_webhook_env: str = "DISCORD_WEBHOOK_URL"  # set in secrets.env
    only_when_new: bool = False                        # True = ping only when new docs added


class Config(BaseModel):
    pipeline: PipelineCfg = Field(default_factory=PipelineCfg)
    state: StateCfg = Field(default_factory=StateCfg)
    gates: GatesCfg = Field(default_factory=GatesCfg)
    notify: NotifyCfg = Field(default_factory=NotifyCfg)
    sources: dict[str, SourceCfg] = Field(default_factory=dict)
    rom_harvest: dict = Field(default_factory=dict)   # ROM-attachment harvester (car-side, not corpus)

    def resolve(self, p: str | Path) -> Path:
        """Resolve a config path: absolute as-is, else relative to REPO_ROOT."""
        p = Path(p)
        return p if p.is_absolute() else (REPO_ROOT / p)

    @property
    def data_dir_path(self) -> Path:
        return self.resolve(self.pipeline.data_dir)


def _load_secrets(path: Path) -> None:
    if path.exists():
        load_dotenv(path, override=False)


@lru_cache(maxsize=1)
def load_config(config_path: str | None = None, secrets_path: str | None = None) -> Config:
    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG
    sec_path = Path(secrets_path) if secrets_path else DEFAULT_SECRETS
    _load_secrets(sec_path)
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    else:
        raw = {}
    return Config.model_validate(raw)


def env(name: str, *, required: bool = False, default: str | None = None) -> str | None:
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(f"required env var {name!r} is unset")
    return val
