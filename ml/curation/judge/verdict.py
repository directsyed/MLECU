"""Verdict parsing/validation — the judge's output contract, checked in code.

The extraction JSON Schema (prompts/*/extraction_schema.json) is the single source of truth:
it is sent to llama-server as the response_format grammar AND used here to validate what came
back. parse() strips code fences (some models wrap JSON despite instructions) and enforces the
hard invariants the schema can't express numerically-tightly enough to trust blindly.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class VerdictError(ValueError):
    pass


@dataclass
class Verdict:
    score: int
    rationale: str
    pairs: list[dict] = field(default_factory=list)
    claims_checked: list[dict] = field(default_factory=list)

    @property
    def pairs_json(self) -> str:
        return json.dumps(self.pairs, ensure_ascii=False)


def parse(raw: str) -> Verdict:
    txt = _FENCE.sub("", raw.strip()).strip()
    try:
        data = json.loads(txt)
    except json.JSONDecodeError as e:
        raise VerdictError(f"not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise VerdictError("verdict must be a JSON object")
    score = data.get("score")
    if not isinstance(score, int) or not 1 <= score <= 5:
        raise VerdictError(f"score must be an integer 1-5, got {score!r}")
    rationale = data.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise VerdictError("rationale must be a non-empty string")
    pairs = data.get("pairs", [])
    if not isinstance(pairs, list):
        raise VerdictError("pairs must be a list (empty when nothing is extractable)")
    for p in pairs:
        if not isinstance(p, dict):
            raise VerdictError("each pair must be an object")
        missing = {"symptoms", "diagnosis", "change", "outcome"} - set(p)
        if missing:
            raise VerdictError(f"pair missing fields: {sorted(missing)}")
    claims = data.get("claims_checked", [])
    if not isinstance(claims, list):
        raise VerdictError("claims_checked must be a list")
    return Verdict(score=score, rationale=rationale.strip(), pairs=pairs,
                   claims_checked=claims)
