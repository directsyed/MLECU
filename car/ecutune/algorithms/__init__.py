"""Deterministic tuning algorithms. Each stage is a pure function that consumes a binned log +
current tables and emits a Proposal; it NEVER applies it (that is safety.apply_proposal's job).
The registry mirrors corpus_pipeline's source REGISTRY pattern."""
from __future__ import annotations

from .controller import BoundedIntegralState, PIConfig, step
from .idle_global_scalar import AlgoState, propose_idle_correction
from .maf_transfer import MafState, grid_spec_for, propose_maf_correction
from .timing_retard import (TimingState, ceiling_grid, grid_spec_for_timing,
                            iam_deficit_degrees, propose_timing_retard)

# stage name -> proposer. The future LLM stage plugs in here as just another producer.
STAGE_REGISTRY = {
    "idle_stage2": propose_idle_correction,
    "maf_transfer": propose_maf_correction,
    "timing_retard": propose_timing_retard,
}

__all__ = ["STAGE_REGISTRY", "propose_idle_correction", "AlgoState",
           "propose_maf_correction", "MafState", "grid_spec_for",
           "propose_timing_retard", "TimingState", "grid_spec_for_timing",
           "iam_deficit_degrees", "ceiling_grid",
           "BoundedIntegralState", "PIConfig", "step"]
