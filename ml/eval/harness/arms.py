"""Arm definitions. Protocol rule (ROADMAP): everything identical between arms except the one
variable under test — arm B differs from arm A ONLY by the injected retrieval block. The
system prompt is deliberately minimal: the sim-case prompt carries the task; the E1 signal we
want is the model's diagnostic reasoning, not prompt engineering."""
from __future__ import annotations

from .config import Config
from . import retrieval

SYSTEM = (
    "You are diagnosing engine-management problems from datalog evidence. Reason carefully, "
    "then answer with a JSON object containing exactly one key \"fault\" whose value is one "
    "of the identifiers offered in the question."
)

_RAG_HEADER = (
    "Reference excerpts retrieved from tuning literature (may or may not be relevant — weigh "
    "them against the datalog evidence):"
)


def answer_schema(choices: list[str]) -> dict:
    """Grammar the server enforces: the model physically cannot answer off-list."""
    return {"type": "object",
            "properties": {"fault": {"type": "string", "enum": choices}},
            "required": ["fault"], "additionalProperties": False}


def build_user(arm: str, cfg: Config, case_prompt: str) -> tuple[str, list[int]]:
    """Returns (user_message, retrieved_doc_ids). Arm A: the case verbatim. Arm B: retrieval
    block prepended. retrieved_doc_ids is recorded per-result for auditability."""
    if arm == "A":
        return case_prompt, []
    if arm == "B":
        snips = retrieval.retrieve(cfg.retrieval, case_prompt)
        if not snips:
            return case_prompt, []
        block = "\n\n".join(f"[REF {s.ref_doc_id}] {s.title}\n{s.snippet}" for s in snips)
        return f"{_RAG_HEADER}\n\n{block}\n\n---\n\n{case_prompt}", [s.ref_doc_id for s in snips]
    raise ValueError(f"unknown arm {arm!r} (implemented: A, B)")
