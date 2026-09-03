"""E1, diagnostic-reasoning eval runner + scorer.

Scoring is delegated to car/ecutune/evals/scoring.py loaded BY FILE PATH (importlib): the LLM
arms must be scored by byte-identical code to the rules baseline (85.7% top1 / 100% acceptable)
or the comparison is meaningless. The module is stdlib-only, so loading it cross-venv is safe.

Results are JSONL, one row per case per run, with full provenance (arm, model tag, retrieved
doc ids, latency, token usage), the raw material for the paired-comparison stats when C/D
exist. chat_fn is injectable for tests (stub instead of a live server).
"""
from __future__ import annotations

import importlib.util
import sys
import json
import time
from pathlib import Path
from typing import Callable

from . import arms, llm
from .config import Config


def load_scoring(path: Path):
    spec = importlib.util.spec_from_file_location("ecutune_scoring", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load scoring module at {path}")
    mod = importlib.util.module_from_spec(spec)
    # must register BEFORE exec: the module defines @dataclass classes, and dataclass
    # creation resolves cls.__module__ through sys.modules, unregistered means None.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_cases(path: Path, limit: int | None = None) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return cases[:limit] if limit else cases


def run_arm(cfg: Config, arm: str, run_idx: int, cases: list[dict],
            chat_fn: Callable | None = None, log=print) -> Path:
    """Run every case through one arm; write one results JSONL; return its path."""
    chat_fn = chat_fn or llm.chat
    cfg.results_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = cfg.results_dir / f"e1-arm{arm}-run{run_idx}-{stamp}.jsonl"
    with out.open("w") as f:
        for i, case in enumerate(cases):
            user, ref_ids, rmeta = arms.build_user(arm, cfg, case["prompt"], task="e1")
            content, usage, latency = chat_fn(
                cfg.llm, arms.SYSTEM, user, json_schema=arms.answer_schema(case["choices"]))
            # The grammar guarantees shape ONLY if generation reached the content phase, a
            # thinking model that exhausts its budget mid-deliberation returns "" (overnight
            # 2026-07-09, case 43). An unanswerable case is a MISS for that arm, never a
            # harness crash.
            try:
                answer = json.loads(content)["fault"] if content else ""
            except (json.JSONDecodeError, KeyError, TypeError):
                answer = ""
            f.write(json.dumps({
                "case_id": case["case_id"], "arm": arm, "run": run_idx,
                "model": cfg.llm.model, "answer": answer,
                "fault": case["fault"], "acceptable": case["acceptable"],
                "retrieved_doc_ids": ref_ids, "latency_s": round(latency, 2),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                # provenance (audit C3/C5), an empty answer from a model that hit the token
                # ceiling is a DIFFERENT fact from one that answered off-grammar, and until
                # 2026-08-02 the row could not tell them apart.
                "finish_reason": usage.get("finish_reason"),
                "n_expected": len(cases),
                "retrieval_mode": rmeta.get("retrieval_mode"),
                "retrieval_mode_used": rmeta.get("mode_used"),
                "top_k": rmeta.get("top_k"),
                "index_mtime": rmeta.get("index_mtime"),
                "index_stale": rmeta.get("index_stale"),
                "dense_fallback": rmeta.get("dense_fallback"),
                "missing_rowids": rmeta.get("missing_rowids"),
            }) + "\n")
            f.flush()                                  # crash-safe: every row lands on disk
            log(f"  [{arm}/run{run_idx}] {i+1}/{len(cases)} {case['case_id']}: "
                f"{answer} ({latency:.0f}s)")
    return out


def score_results(cfg: Config, results_path: Path):
    """Score one results file with the ecutune scorer. Returns its EvalReport."""
    rows = [json.loads(l) for l in results_path.read_text().splitlines() if l.strip()]
    cases = load_cases(cfg.cases_path)
    by_id = {c["case_id"]: c for c in cases}
    answered = {r["case_id"]: r["answer"] for r in rows}
    scored_cases = [by_id[cid] for cid in answered]   # score exactly what was answered
    scoring = load_scoring(cfg.scoring_py)
    return scoring.score(scored_cases, answered)


def determinism(path_a: Path, path_b: Path, n_expected: int | None = None) -> tuple[int, int]:
    """(identical, total) answers across two runs of the same arm, temp-0 sanity check.

    A12 (2026-08-02): v1 scored the INTERSECTION of the two files, so a run that died after
    case 3 reported a triumphant "3/3 identical", the denominator shrank to match the
    damage. Worse, two empty answers ("" == "") counted as agreement, so a pair of runs that
    both failed to answer scored as perfectly deterministic. The denominator is now the
    expected case count (from the rows, or the caller), missing cases count as disagreement,
    and empty-vs-empty is not evidence of anything.
    """
    def rows(p: Path) -> list[dict]:
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]

    ra, rb = rows(path_a), rows(path_b)
    a = {r["case_id"]: r["answer"] for r in ra}
    b = {r["case_id"]: r["answer"] for r in rb}
    if n_expected is None:
        stated = {r.get("n_expected") for r in ra + rb if r.get("n_expected")}
        n_expected = stated.pop() if len(stated) == 1 else max(len(a), len(b))
    agree = sum(1 for k in a.keys() & b.keys() if a[k] == b[k] and a[k] != "")
    return agree, n_expected
