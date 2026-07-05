"""The batch judge loop. Doc-atomic by construction: nothing reaches the DB until every chunk
of a doc has a verdict, so a crash mid-doc leaves it 'pending' and the next run re-picks it.

Flow per doc: policy -> (auto_pass | chunk -> ground -> judge -> parse) -> aggregate ->
State.mark_judged (one transaction). Failures after retries park the doc as 'failed'
(pending_for_judge naturally excludes it; --retry-failed flips them back).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from corpus_pipeline.core.state import State

from . import chunker, llm, retrieval, verdict as verdict_mod
from .audit import AuditLog
from .config import Config
from .prompts import PromptPack, load_prompt_pack

log = logging.getLogger(__name__)

AUTO_PASS_MODEL = "auto-pass"     # policy verdicts are attributed to the policy, not a model


@dataclass
class RunStats:
    judged: int = 0
    auto_passed: int = 0
    failed: int = 0
    chunks: int = 0
    score_hist: dict[int, int] = field(default_factory=dict)

    def record(self, score: int) -> None:
        self.score_hist[score] = self.score_hist.get(score, 0) + 1


def _doc_synopsis(cfg: Config, pack: PromptPack, doc, first_chunk_text: str) -> str:
    """Per-doc synopsis pre-pass for multi-chunk docs (context decision 2026-07-05).

    Built from the doc HEAD (title + first ~10k chars) — thread subject and setup are
    established early; a full-doc synopsis wouldn't fit the context. Factual-only prompt so
    it can't bias chunk scores."""
    if not pack.synopsis:
        return ""
    head = f"title: {doc['title']}\nsource: {doc['source']}\n\n{first_chunk_text[:10000]}"
    text, _usage, _ = llm.chat(cfg.llm, pack.synopsis, head)
    return (text or "").strip()[:1500]


def _judge_chunk(cfg: Config, pack: PromptPack, state: State, doc, ch: chunker.Chunk,
                 policy: str, doc_synopsis: str = "") -> tuple[verdict_mod.Verdict, list, dict]:
    refs = (retrieval.grounding(state, cfg, ch.text)
            if doc["tier"] == "community" and cfg.retrieval.top_k > 0 else [])
    user = pack.render_user(title=doc["title"] or "", source=doc["source"], tier=doc["tier"],
                            text=ch.text, chunk_index=ch.index, n_chunks=ch.n_chunks,
                            refs=refs, policy=policy, doc_synopsis=doc_synopsis)
    attempts = cfg.llm.json_retries + 1
    last_err: Exception | None = None
    for attempt in range(attempts):
        raw, usage, reasoning = llm.chat(cfg.llm, pack.system, user,
                                         json_schema=pack.extraction_schema)
        try:
            return verdict_mod.parse(raw), refs, {"raw": raw, "usage": usage,
                                                  "reasoning": reasoning}
        except verdict_mod.VerdictError as e:
            last_err = e
            # re-ask with the validation error appended — the model sees WHY it failed
            user = f"{user}\n\n---\nYour previous reply was invalid: {e}. " \
                   f"Reply again with ONLY the JSON object."
            log.warning("doc %s chunk %d: invalid verdict (attempt %d): %s",
                        doc["id"], ch.index, attempt + 1, e)
    raise llm.LlmError(f"verdict invalid after {attempts} attempts: {last_err}")


def run(cfg: Config, state: State, *, limit: int | None = None,
        sources: set[str] | None = None, dry_run: bool = False) -> RunStats:
    served = llm.health_check(cfg.llm)
    log.info("llama-server up, serving %s", served)
    retrieval.ensure_index(state, cfg)
    pack = load_prompt_pack(cfg.resolve(cfg.judge.prompts_dir))
    audit = AuditLog(cfg.resolve(cfg.audit.dir))
    stats = RunStats()

    while limit is None or stats.judged + stats.auto_passed < limit:
        batch = state.pending_for_judge(cfg.judge.batch_size,
                                        sources=tuple(sorted(sources)) if sources else None)
        if not batch:
            break
        for doc in batch:
            if limit is not None and stats.judged + stats.auto_passed >= limit:
                break
            policy = cfg.judge.policy_for(doc["source"], doc["tier"])
            try:
                if policy == "auto_pass":
                    if not dry_run:
                        state.mark_judged(doc["id"], score=5, judge_model=AUTO_PASS_MODEL,
                                          rubric_version=pack.version,
                                          chunks=[{"score": 5, "rationale":
                                                   f"auto_pass policy for {doc['source']}"}])
                        audit.write(doc_id=doc["id"], source=doc["source"], policy=policy,
                                    score=5, judge_model=AUTO_PASS_MODEL,
                                    rubric_version=pack.version)
                    stats.auto_passed += 1
                    continue

                chunks = chunker.chunk(doc["text"], cfg.chunking.max_chars,
                                       cfg.chunking.overlap_chars)
                synopsis = ""
                if len(chunks) > 1:
                    synopsis = _doc_synopsis(cfg, pack, doc, chunks[0].text)
                    if synopsis:
                        audit.write(doc_id=doc["id"], source=doc["source"],
                                    synopsis=synopsis, rubric_version=pack.version)
                rows: list[dict] = []
                scores: list[int] = []
                lengths: list[int] = []
                for ch in chunks:
                    v, refs, extra = _judge_chunk(cfg, pack, state, doc, ch, policy, synopsis)
                    scores.append(v.score)
                    lengths.append(len(ch.text))
                    rows.append({
                        "chunk_index": ch.index, "n_chunks": ch.n_chunks, "score": v.score,
                        "rationale": v.rationale, "pairs_json": v.pairs_json,
                        "grounding_json": json.dumps([r.__dict__ for r in refs]),
                        "prompt_tokens": extra["usage"].get("prompt_tokens"),
                        "completion_tokens": extra["usage"].get("completion_tokens"),
                        "relevance": v.relevance,
                        "evidence_in_images": int(v.evidence_in_images),
                    })
                    audit.write(doc_id=doc["id"], source=doc["source"], policy=policy,
                                chunk_index=ch.index, n_chunks=ch.n_chunks, score=v.score,
                                rationale=v.rationale, pairs=v.pairs,
                                relevance=v.relevance, evidence_in_images=v.evidence_in_images,
                                grounding=[r.__dict__ for r in refs],
                                raw=extra["raw"], usage=extra["usage"],
                                reasoning=extra["reasoning"],
                                judge_model=cfg.llm.model, rubric_version=pack.version)
                doc_score = chunker.aggregate(scores, lengths, cfg.chunking.aggregate)
                if not dry_run:
                    state.mark_judged(doc["id"], score=doc_score, judge_model=cfg.llm.model,
                                      rubric_version=pack.version, chunks=rows)
                stats.judged += 1
                stats.chunks += len(chunks)
                stats.record(doc_score)
                log.info("judged doc %s (%s) score=%d chunks=%d",
                         doc["id"], (doc["title"] or "")[:48], doc_score, len(chunks))
            except Exception as e:
                log.error("doc %s failed: %s", doc["id"], e)
                if not dry_run:
                    state.mark_judge_failed(doc["id"], str(e))
                    audit.write(doc_id=doc["id"], source=doc["source"], error=str(e))
                stats.failed += 1
        if dry_run:
            break     # dry runs don't mark anything, so the same batch would loop forever
    return stats
