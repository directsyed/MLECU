"""Arm definitions. Protocol rule (ROADMAP): everything identical between arms except the one
variable under test, arm B differs from arm A ONLY by the injected retrieval block. The
system prompt is deliberately minimal: the sim-case prompt carries the task; the E1 signal we
want is the model's diagnostic reasoning, not prompt engineering.

ARM B IS SYED'S BUILD (2026-07-08, learning-priority): the RAG retrieval module
(harness/retrieval.py) and the augmentation branch below were removed so Syed implements
them from scratch. Acceptance suite: tests/test_rag_syed.py (skips until the module exists).
"""
from __future__ import annotations

from . import retrieval
from .config import Config

SYSTEM = (
    "You are diagnosing engine-management problems from datalog evidence. Reason carefully, "
    "then answer with a JSON object containing exactly one key \"fault\" whose value is one "
    "of the identifiers offered in the question."
)

# The cite-or-decline rider rides IN the injected block, never in SYSTEM: that preserves the
# single-variable arm protocol (arm A's prompt is untouched).
_RIDER = ("If asked for a specific calibration value, state it only if an excerpt contains "
          "it (cite its [REF id]); otherwise decline rather than estimate:")

# A16: E1's header was injected into E2 verbatim, telling a value-lookup run to "weigh them
# against the datalog evidence" when there is no datalog in an E2 probe. E2 gets its own
# wording; the rider is identical in both so the guard's contract does not change per suite.
_HEADERS = {
    "e1": ("Reference excerpts retrieved from tuning literature (may or may not be "
           "relevant, weigh them against the datalog evidence). " + _RIDER),
    "e2": ("Reference excerpts retrieved from tuning literature (may or may not contain "
           "the value asked for). " + _RIDER),
}


def answer_schema(choices: list[str]) -> dict:
    """Grammar the server enforces: the model physically cannot answer off-list."""
    return {"type": "object",
            "properties": {"fault": {"type": "string", "enum": choices}},
            "required": ["fault"], "additionalProperties": False}


def build_user(arm: str, cfg: Config, case_prompt: str,
               task: str = "e1") -> tuple[str, list[int], dict]:
    """Returns (user_message, retrieved_doc_ids, retrieval_meta). Arms A/C: the case verbatim.
    Arms B/D: retrieval block prepended (Syed's build). retrieved_doc_ids recorded for audit.

    Arms C/D added 2026-07-22 (showdown night): mechanically identical to A/B, the
    fine-tune is the SERVER-side variable (adapter-loaded llama-server), so the arm letter
    exists only for honest labeling in results files.

    The third return value is retrieval provenance (2026-08-02, audit C5). Nothing about
    retrieval was recorded in result rows before then, not the mode, not top_k, not which
    index, not whether hybrid had silently fallen back to BM25, so cells that differed in
    retrieval were compared as though they had not.
    """
    if arm in ("A", "C"):
        return case_prompt, [], {"retrieval_mode": None, "mode_used": "none", "top_k": 0}
    if arm in ("B", "D"):
        snips, meta = retrieval.retrieve_with_meta(cfg.retrieval, case_prompt)
        if not snips:
            return case_prompt, [], meta      # degrade to arm-A behavior, LOGGED via empty ids
        block = "\n\n".join(f"[REF {s.ref_doc_id}] {s.title}\n{s.snippet}" for s in snips)
        header = _HEADERS.get(task, _HEADERS["e1"])
        return (f"{header}\n\n{block}\n\n---\n\n{case_prompt}",
                [s.ref_doc_id for s in snips], meta)
    raise ValueError(f"unknown arm {arm!r} (implemented: A, B, C, D)")
