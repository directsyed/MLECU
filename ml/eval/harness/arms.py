"""Arm definitions. Protocol rule (ROADMAP): everything identical between arms except the one
variable under test — arm B differs from arm A ONLY by the injected retrieval block. The
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


def answer_schema(choices: list[str]) -> dict:
    """Grammar the server enforces: the model physically cannot answer off-list."""
    return {"type": "object",
            "properties": {"fault": {"type": "string", "enum": choices}},
            "required": ["fault"], "additionalProperties": False}


def build_user(arm: str, cfg: Config, case_prompt: str) -> tuple[str, list[int]]:
    """Returns (user_message, retrieved_doc_ids). Arm A: the case verbatim. Arm B: retrieval
    block prepended (Syed's build). retrieved_doc_ids is recorded per-result for audit."""
    if arm == "A":
        return case_prompt, []
    if arm == "B":
        snips = retrieval.retrieve(cfg.retrieval, case_prompt)
        if not snips:
            return case_prompt, []          # degrade to arm-A behavior, LOGGED via empty ids
        block = "\n\n".join(f"[REF {s.ref_doc_id}] {s.title}\n{s.snippet}" for s in snips)
        header = ("Reference excerpts retrieved from tuning literature (may or may not be "
                  "relevant — weigh them against the datalog evidence):")
        return f"{header}\n\n{block}\n\n---\n\n{case_prompt}", [s.ref_doc_id for s in snips]
    raise ValueError(f"unknown arm {arm!r} (implemented: A, B)")
