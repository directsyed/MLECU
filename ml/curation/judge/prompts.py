"""Prompt pack loader, a rubric version is a DIRECTORY of editable files, never code.

prompts/rubric-r1/
  system.md              judge role + output contract
  rubric_community.md    1-5 anchors for community (forum) docs
  rubric_reference.md    light-judge anchors for reference docs
  grounding.md           how to treat retrieved reference snippets
  extraction_schema.json JSON Schema for the verdict (also the response_format grammar)

The rubric_version recorded on every judgment is the directory name, so a rubric edit means
making rubric-r2/, old verdicts stay attributable to the exact wording that produced them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .retrieval import RefSnippet


@dataclass(frozen=True)
class PromptPack:
    version: str
    system: str
    rubric_community: str
    rubric_reference: str
    grounding: str
    extraction_schema: dict
    synopsis: str = ""              # pre-pass prompt; empty in packs without one (r1)

    def render_user(self, *, title: str, source: str, tier: str, text: str,
                    chunk_index: int, n_chunks: int, refs: list[RefSnippet],
                    policy: str, doc_synopsis: str = "") -> str:
        rubric = self.rubric_community if tier == "community" else self.rubric_reference
        parts = [rubric]
        if doc_synopsis:
            parts.append("# Document synopsis (context for this chunk, score ONLY the "
                         "chunk's own content)\n" + doc_synopsis)
        if refs:
            lines = [f"[REF {s.ref_doc_id}] {s.title}\n{s.snippet}" for s in refs]
            parts.append(self.grounding + "\n\n" + "\n\n".join(lines))
        pos = f" (chunk {chunk_index + 1} of {n_chunks})" if n_chunks > 1 else ""
        parts.append(f"# Document to judge{pos}\nsource: {source} | tier: {tier} | "
                     f"policy: {policy}\ntitle: {title}\n\n{text}")
        return "\n\n---\n\n".join(parts)


def load_prompt_pack(prompts_dir: Path) -> PromptPack:
    d = Path(prompts_dir)
    def read(name: str) -> str:
        p = d / name
        if not p.exists():
            raise FileNotFoundError(f"prompt pack incomplete: missing {p}")
        return p.read_text(encoding="utf-8")
    synopsis_path = d / "synopsis.md"
    return PromptPack(
        version=d.name,
        system=read("system.md"),
        rubric_community=read("rubric_community.md"),
        rubric_reference=read("rubric_reference.md"),
        grounding=read("grounding.md"),
        extraction_schema=json.loads(read("extraction_schema.json")),
        synopsis=synopsis_path.read_text(encoding="utf-8") if synopsis_path.exists() else "",
    )
