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
    max_completion_tokens: int = 24576     # thinking model: reasoning + JSON share ONE budget.
                                           # 4096 proved too small overnight 2026-07-09: hard
                                           # E1 cases deliberate past it -> empty content.
                                           # 8192 = the judge's proven value (config.yaml), and
                                           # it in turn truncated Thinking-class models mid-trace
                                           # on 2026-07-31 (blanks scored as misses, understating
                                           # them by up to 14pp).
                                           # 24576 (2026-08-14, Qwen3.8): 3.8 reasons by DEFAULT
                                           # at reasoning_effort=xhigh. Raised for E4 especially,
                                           # whose main() takes no --max-tokens flag and would
                                           # otherwise silently inherit the truncating value.
                                           # This is a CEILING, not a target: measured E1 worst
                                           # case used 1,111 tokens (4.5%), all finish_reason=stop.
    request_timeout_s: int = 1800          # must rise WITH the budget: 600 died mid-cell on
                                           # 2026-08-01 once tokens hit 16384. At the measured
                                           # ~44 t/s a full 24576-token completion needs ~560 s,
                                           # so 600 left no margin at all.


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
    # v2 (2026-08-02, audit A10): v1 was built at 5,608 rows and ref_fts grew to 5,638 — 30
    # chunks were invisible to the dense ranker for the entire showdown, undetected. v2 is a
    # full rebuild carrying an n_rows stamp that retrieval.py checks against the live DB at
    # load. v1 stays on disk (stale, do not use) so showdown cells remain reproducible.
    index_path: Path = EVAL_DIR / "data/ref_dense_v2.npz"
    # Snippet extraction (2026-08-02): unified char-window for every hit in hybrid mode.
    # snippet_max_chars is a target — the window may overshoot by up to one token plus
    # NUM_RUN_MAX_EXTEND chars when the boundary would otherwise cut a number in half.
    snippet_window_lead_frac: float = 0.25   # share of the window placed BEFORE the match


@dataclass(frozen=True)
class Config:
    llm: LlmCfg = field(default_factory=LlmCfg)
    retrieval: RetrievalCfg = field(default_factory=RetrievalCfg)
    cases_path: Path = EVAL_DIR / "data/sim_cases_v1.jsonl"
    results_dir: Path = EVAL_DIR / "results"
    # scoring must be IDENTICAL to the rules-baseline scoring or the 85.7%/100% bar is
    # meaningless — we import the ecutune scorer by file path rather than reimplementing it.
    scoring_py: Path = MLECU / "car/ecutune/evals/scoring.py"
