"""Config loader — mirrors corpus_pipeline/core/config.py (pydantic + lru_cache + resolve)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[1]   # .../ml/curation/
DEFAULT_CONFIG = REPO_ROOT / "config.yaml"


class LlmCfg(BaseModel):
    base_url: str = "http://127.0.0.1:8080/v1"
    model: str = "unknown"
    temperature: float = 0.0
    max_completion_tokens: int = 1500
    json_retries: int = 2
    request_timeout_s: int = 600


class CorpusCfg(BaseModel):
    db_path: str = "../data-pipeline/data/corpus.sqlite"


class JudgeCfg(BaseModel):
    batch_size: int = 25
    keep_threshold: int = 4
    prompts_dir: str = "prompts/rubric-r1"
    reference_policy: dict[str, str] = Field(default_factory=lambda: {"default": "light_judge"})

    def policy_for(self, source: str, tier: str) -> str:
        """community docs are always fully judged; reference docs follow the per-source map."""
        if tier == "community":
            return "full"
        return self.reference_policy.get(source, self.reference_policy.get("default", "light_judge"))


class ChunkingCfg(BaseModel):
    max_chars: int = 24000
    overlap_chars: int = 600
    aggregate: str = "min"               # min | mean | weighted_mean


class RetrievalCfg(BaseModel):
    mode: str = "fts5"
    top_k: int = 3
    snippet_max_chars: int = 1200


class AuditCfg(BaseModel):
    dir: str = "data/audit"


class CalibrationCfg(BaseModel):
    set_name: str = "calibration-100"
    n: int = 100
    blind_subset: int = 20


class Config(BaseModel):
    llm: LlmCfg = Field(default_factory=LlmCfg)
    corpus: CorpusCfg = Field(default_factory=CorpusCfg)
    judge: JudgeCfg = Field(default_factory=JudgeCfg)
    chunking: ChunkingCfg = Field(default_factory=ChunkingCfg)
    retrieval: RetrievalCfg = Field(default_factory=RetrievalCfg)
    audit: AuditCfg = Field(default_factory=AuditCfg)
    calibration: CalibrationCfg = Field(default_factory=CalibrationCfg)

    def resolve(self, rel: str | Path) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else (REPO_ROOT / p)

    @property
    def rubric_version(self) -> str:
        return Path(self.judge.prompts_dir).name


@lru_cache(maxsize=4)
def load_config(config_path: str | None = None) -> Config:
    path = Path(config_path) if config_path else DEFAULT_CONFIG
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return Config.model_validate(raw or {})
