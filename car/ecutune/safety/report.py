"""The disagreement report — what the human gets when the layer refuses a proposal.

SYED'S REQUIREMENT (2026-08-05), verbatim in intent: *"we need the system to give a DETAILED
excerpt of why there was a disagreement, all the data from the LLM that led it to the diagnosis,
and all the data and computations from the DL to make it disagree, so the human has both sides
of the coin."*

The point is not to announce a verdict. A refusal means the two independent analyses reached
different conclusions and **we do not know which one is right** — so the report has to put the
human in a position to adjudicate, not to rubber-stamp. That means showing the runner-up
hypotheses and how close they were, not just the winner; and showing the exact evidence the
model was given, not a summary of it.

This extends the existing audit-trail doctrine in clamps.py ("auditability is itself a safety
property") from "which clamp fired" to "why the two halves of the system disagreed".
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass

from ..core.models import ClampContext, ClampResult, Proposal


def _fmt(v: float, places: int = 4) -> str:
    return f"{v:.{places}g}"


def disagreement_report(prop: Proposal, ctx: ClampContext, result: ClampResult,
                        llm_context: dict | None = None) -> dict:
    """Machine-readable record of a refused proposal. `to_markdown` renders it for a human.

    `llm_context` carries everything the model side knows and the safety layer does not: the
    prompt it was shown, the retrieved excerpts, the per-iteration diagnosis history, the model
    tag, finish_reason and token counts. The layer cannot reconstruct these, so the orchestrator
    passes them in — and if it passes nothing, the report says so loudly rather than implying
    the model had no reasoning.
    """
    est = ctx.fault_estimate
    residuals = dict(getattr(est, "residuals", {}) or {})
    ranked = sorted(residuals.items(), key=lambda kv: kv[1])

    return {
        "verdict": "REFUSED — deterministic layer disagrees with the diagnosis",
        "aborted_by": result.aborted_by,
        "proposal": {
            "proposal_id": prop.proposal_id,
            "stage": prop.stage,
            "provenance": prop.provenance,
            "targets_kind": prop.targets_kind,
            "tables_it_would_move": sorted({e.table_id for e in prop.edits}),
            "edits": [e.to_dict() for e in prop.edits],
            "metadata": prop.metadata,
        },
        "llm_side": llm_context or {
            "WARNING": "no LLM context supplied by the caller — the model's reasoning is NOT "
                       "recoverable from the safety layer alone; the orchestrator must pass it",
        },
        "deterministic_side": {
            "verdict": getattr(est, "fault_id", None),
            "would_move": (est.knob() if hasattr(est, "knob") else None),
            "identifiable": getattr(est, "identifiable", None),
            "why_not": getattr(est, "reason", "") or None,
            "fitted_magnitude": getattr(est, "magnitude", None),
            "margin_over_next_different_action": getattr(est, "margin", None),
            "n_observations": getattr(est, "n_observations", None),
            # the WHOLE ranking, so the human can see how close the runner-up was rather than
            # being handed a bare winner
            "hypothesis_ranking": [{"fault": k, "residual": v} for k, v in ranked],
            "observations": [asdict(o) if is_dataclass(o) else o
                             for o in (getattr(est, "observations", None) or [])],
        },
        "clamp_violations": [
            {"clamp": v.clamp, "table": v.table_id, "row": v.row, "col": v.col,
             "requested": v.requested, "allowed": v.allowed, "action": v.action}
            for v in result.violations],
        "what_the_human_must_decide": (
            "Two independent analyses of the same engine disagree about WHICH belief is wrong. "
            "Nothing has been written. Either (a) accept the deterministic estimate and re-run, "
            "(b) accept the model's diagnosis and override, or (c) capture more probe points — "
            "the layer's `why_not` field says whether the data was simply insufficient."
        ),
    }


def to_markdown(rep: dict) -> str:
    """Human-facing rendering. Deliberately puts BOTH conclusions adjacent and near the top —
    the whole purpose is that the reader compares them rather than reads a verdict."""
    d, p = rep["deterministic_side"], rep["proposal"]
    llm = rep["llm_side"]
    out = [f"# {rep['verdict']}", "",
           f"**Aborted by:** `{rep['aborted_by']}`", "",
           "## The two conclusions", "",
           "| | concluded | would move |",
           "|---|---|---|",
           f"| **LLM** | `{llm.get('diagnosis', '(not supplied)')}` | "
           f"`{', '.join(p['tables_it_would_move']) or '(none)'}` |",
           f"| **Deterministic layer** | `{d['verdict']}` | `{d['would_move'] or '(no table edit)'}` |",
           "", f"Layer identifiable: **{d['identifiable']}**"
           + (f" — {d['why_not']}" if d["why_not"] else ""),
           f"  ·  fitted magnitude `{d['fitted_magnitude']}`"
           f"  ·  margin over next different action `{d['margin_over_next_different_action']}`"
           f"  ·  {d['n_observations']} probe points", "",
           "## Deterministic side — every hypothesis, ranked", "",
           "Lower residual = better fit. The runner-up matters: a narrow gap means the data",
           "genuinely does not separate them, which is a different problem from a wrong model.", "",
           "| rank | hypothesis | residual (SSE) |", "|---|---|---|"]
    for i, h in enumerate(d["hypothesis_ranking"], 1):
        out.append(f"| {i} | `{h['fault']}` | {_fmt(h['residual'])} |")

    if d["observations"]:
        out += ["", "### Observations it fitted", "",
                "| air_scale | voltage | trim | MAF reading | nominal MAF |", "|---|---|---|---|---|"]
        for o in d["observations"]:
            out.append(f"| {o.get('air_scale')} | {o.get('voltage')} | {_fmt(o.get('trim', 0))} "
                       f"| {o.get('maf_reading')} | {o.get('nominal_maf')} |")

    out += ["", "## LLM side — the evidence it was given", ""]
    if "WARNING" in llm:
        out.append(f"> **{llm['WARNING']}**")
    else:
        if llm.get("diagnosis_history"):
            out.append(f"**Per-iteration diagnoses:** `{llm['diagnosis_history']}`")
        for k in ("model", "finish_reason", "completion_tokens", "top_k", "retrieval_mode"):
            if llm.get(k) is not None:
                out.append(f"- {k}: `{llm[k]}`")
        if llm.get("retrieved_doc_ids"):
            out.append(f"- retrieved refs: `{llm['retrieved_doc_ids']}`")
        if llm.get("prompt"):
            out += ["", "<details><summary>Exact prompt shown to the model</summary>", "",
                    "```", llm["prompt"], "```", "", "</details>"]
        if llm.get("retrieved_excerpts"):
            out += ["", "<details><summary>Retrieved excerpts</summary>", ""]
            for ex in llm["retrieved_excerpts"]:
                out.append(f"- **[REF {ex.get('ref_doc_id')}]** {ex.get('title', '')}\n\n"
                           f"  > {ex.get('snippet', '')[:600]}")
            out += ["", "</details>"]

    if rep["clamp_violations"]:
        out += ["", "## Clamps that fired", "",
                "| clamp | table | requested | allowed | action |", "|---|---|---|---|---|"]
        for v in rep["clamp_violations"]:
            out.append(f"| `{v['clamp']}` | `{v['table']}` | {_fmt(v['requested'])} "
                       f"| {_fmt(v["allowed"])} | {v["action"]} |")

    out += ["", "## Decision required", "", rep["what_the_human_must_decide"], "",
            "**Nothing has been written to any table.**"]
    return "\n".join(out)


def dumps(rep: dict) -> str:
    return json.dumps(rep, indent=2, default=str)
