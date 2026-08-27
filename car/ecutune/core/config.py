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
    boost_load_threshold: float = 0.60   # load (g/rev) above which a cell counts as "boost"
                                         # (measured MAP-crossing point on this car; see config.yaml)
    boost_trim_tol: float = 0.05         # +/-5% trims required before boost edits ungate
    fuel_trim_converged_tol: float = 0.05  # |trim| under this => converged (fuel-before-timing)
    steady_tol: float = 0.05
    default_timing_ceiling: float = 25.0   # deg; used when no per-rpm override matches
    timing_ceilings: list[TimingCeiling] = Field(default_factory=list)
    zero_base_eps: float = 1e-9          # below this |current|, the relative clamp can't apply
    # --- belief sanity envelope (2026-08-05) -------------------------------------------------
    # max_ve_step bounds RATE. Nothing bounded DISPLACEMENT: at 3%/iteration, twelve iterations
    # compounds to 43% away from the stock calibration, and a sustained wrong diagnosis walks a
    # belief arbitrarily far. These are physically-motivated absolute bounds vs the archived
    # stock ROM — an OEM injector does not flow 25% off spec, so hitting the envelope means the
    # DIAGNOSIS is wrong, not that the hardware changed. Per-table so each reflects its own
    # physics. VALUES ARE SYED'S TO RATIFY; these are starting points, not measurements.
    belief_envelope: dict[str, float] = Field(default_factory=lambda: {
        "fuel.injector_flow": 0.25,        # +/-25% of the build-sheet ~500 cc/min
        "fuel.injector_latency": 0.30,     # +/-30% of the stock dead time
        "sensor.maf_transfer": 0.20,       # +/-20% of stock MAF scaling
    })
    belief_envelope_default: float = 0.25

    # --- sensor recalibration (clamp_sensor_calibration, 2026-08-27) -------------------
    # A SENSOR calibration is a different act from a fuel-target correction, so it gets a
    # different bound. `max_ve_step` limits VELOCITY (3%/iteration) because idle fuel
    # convergence must creep toward a moving target. A MAF transfer curve is not a target
    # being chased -- it is a measurement being corrected against ~20k samples of evidence,
    # and creeping there would take ~11 flash cycles to reach a correction the data already
    # supports. So this clamp bounds DISPLACEMENT (how far from stock) and demands EVIDENCE
    # (samples per breakpoint), instead of bounding speed.
    max_sensor_recal: float = 0.40      # hard cap: |new/stock - 1| per cell. Measured worst
                                        # point on the car is 0.363, so this is a real ceiling
                                        # with margin, not a rubber stamp.
    min_sensor_samples: int = 20        # steady samples required per breakpoint before a cell
                                        # may move at all (matches GridSpec.min_samples)
    sensor_require_monotonic: bool = True   # the corrected curve must stay strictly ascending;
                                            # romread.plausible() rejects non-monotonic axes,
                                            # so a curve that breaks this is unflashable anyway

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
    # Fuel trims are noisy: a +/-1% bin mean is indistinguishable from zero. Below this the
    # stage emits NO edit at all, which does two things -- it stops the correction chasing
    # noise, and it leaves regions we have independently validated as healthy (the idle band,
    # trims -0.86% on the three-hold capture) untouched. A smaller diff is also a reviewable
    # diff. 2026-08-27.
    sensor_deadband: float = 0.02
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
