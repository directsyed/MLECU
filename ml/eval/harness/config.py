"""Harness config — plain dataclasses, defaults mirror ml/curation/config.yaml so every arm
talks to the same llama-server the judge certified (same model tag recorded into results)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent          # ml/eval/
MLECU = EVAL_DIR.parent.parent                             # repo root


@dataclass(frozen=True)
class LlmCfg:
    base_url: str = "http://127.0.0.1:8080/v1"
    model: str = "qwen3.6-27b-q8_0"        # recorded verbatim into every result row
    temperature: float = 0.0               # eval is measurement, not sampling
    max_completion_tokens: int = 8192      # thinking model: reasoning + JSON share ONE budget.
                                           # 4096 proved too small overnight 2026-07-09: hard
                                           # E1 cases deliberate past it -> empty content.
                                           # 8192 = the judge's proven value (config.yaml).
    request_timeout_s: int = 600


@dataclass(frozen=True)
class RetrievalCfg:
    # Same knobs the judge grounds with (config.yaml D2) — arm B retrieves like the judge does.
    db_path: Path = MLECU / "ml/data-pipeline/data/corpus.sqlite"
    top_k: int = 3
    snippet_max_chars: int = 1200
    # retrieval-v2 (2026-07-22, Syed-ratified): hybrid dense+BM25 behind the same seam.
    # mode="bm25" reproduces retrieval-v1 byte-for-byte (audit/repro); "hybrid" fuses
    # BM25 with BGE-M3 cosine ranks via RRF. Falls back to bm25 if the index is absent.
    mode: str = "hybrid"
    index_path: Path = EVAL_DIR / "data/ref_dense_v1.npz"


@dataclass(frozen=True)
class Config:
    llm: LlmCfg = field(default_factory=LlmCfg)
    retrieval: RetrievalCfg = field(default_factory=RetrievalCfg)
    cases_path: Path = EVAL_DIR / "data/sim_cases_v1.jsonl"
    results_dir: Path = EVAL_DIR / "results"
    # scoring must be IDENTICAL to the rules-baseline scoring or the 85.7%/100% bar is
    # meaningless — we import the ecutune scorer by file path rather than reimplementing it.
    scoring_py: Path = MLECU / "car/ecutune/evals/scoring.py"
