"""Config: car/config.yaml validated with pydantic, one lru-cached load.

Mirrors corpus_pipeline/core/config.py (pydantic tree + @lru_cache load_config). The
safety limits and engine constants live in YAML so Syed reviews the *numbers* without
touching code — these are safety-critical ceilings, not implementation details.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]   # .../car/
DEFAULT_CONFIG = REPO_ROOT / "config.yaml"


class TimingCeiling(BaseModel):
    rpm: float          # applies at/above this rpm row
    max_advance: float  # degrees BTDC ceiling


class SafetyCfg(BaseModel):
    max_ve_step: float = 0.03            # +/-3% per iteration — the provable rate bound
    afr_floor: float = 11.5              # AFR leaner (greater) than this at boost => abort
    boost_load_threshold: float = 1.5    # load (g/rev) above which a cell counts as "boost"
    boost_trim_tol: float = 0.05         # +/-5% trims required before boost edits ungate
    fuel_trim_converged_tol: float = 0.05  # |trim| under this => converged (fuel-before-timing)
    steady_tol: float = 0.05
    default_timing_ceiling: float = 25.0   # deg; used when no per-rpm override matches
    timing_ceilings: list[TimingCeiling] = Field(default_factory=list)
    zero_base_eps: float = 1e-9          # below this |current|, the relative clamp can't apply

    def timing_ceiling_for(self, rpm: float) -> float:
        """Tightest configured ceiling whose rpm threshold the cell meets; else the default."""
        best = self.default_timing_ceiling
        for tc in sorted(self.timing_ceilings, key=lambda t: t.rpm):
            if rpm >= tc.rpm:
                best = tc.max_advance
        return best


class EngineCfg(BaseModel):
    stoich: float = 14.7
    displacement_l: float = 2.0          # EJ20X truth (the base ROM assumes 2.5L EJ255)


class AlgoCfg(BaseModel):
    kp: float = 0.5         # proportional: fraction of trim error corrected per step
    ki: float = 0.05        # integral gain (small: kills residual without winding up)
    damping: float = 0.7    # <1 => deliberate under-correction (small steps, low overshoot)
    step_clamp: float = 0.03  # per-iteration cap == SafetyCfg.max_ve_step (anti-windup)
    max_iters: int = 30


class Config(BaseModel):
    safety: SafetyCfg = Field(default_factory=SafetyCfg)
    engine: EngineCfg = Field(default_factory=EngineCfg)
    algo: AlgoCfg = Field(default_factory=AlgoCfg)


@lru_cache(maxsize=1)
def load_config(config_path: str | None = None) -> Config:
    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    else:
        raw = {}
    return Config.model_validate(raw)
