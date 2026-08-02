"""Phase-4 rundown generator — the corrected bench matrix, old numbers beside new.

CONTRACT (decisions.md 2026-07-25, anti-benchmark-maxxing): when instrumentation changes, every
affected result is re-derived and the OLD number is published NEXT TO the new one, with movement
reported in both directions. A report that only shows the new numbers is a report that cannot be
audited, and a fix that only ever moves numbers upward is a fix that needs auditing.

Run:  car/.venv/bin/python rundown.py > results/RUNDOWN-<date>.md      (cwd: ml/eval)
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import e1, e2                                        # noqa: E402
from harness.config import Config, EVAL_DIR                       # noqa: E402

RESULTS = EVAL_DIR / "results"
NOISE_BAND_PP = 0.7        # measured 2026-07-31: MTP on-vs-off shifted top-1 by +/-0.7pp
N_PROBES = 69

# Cells the ledger marked INVALID and which must never appear in a comparison table. Listed
# here WITH the reason rather than silently filtered — a table that quietly drops rows is the
# same class of dishonesty as one that quietly keeps bad ones.
EXCLUDED = {
    "qwen-next-80b|": "ran the non-thinking Instruct variant (median 8-14 completion tokens); "
                      "the Thinking variant is the valid cell",
}


def excluded_reason(tag: str) -> str | None:
    for k, why in EXCLUDED.items():
        if tag.startswith(k) and "thinking" not in tag:
            return why
    return None


def reclassified(rows: list[dict]) -> list[dict]:
    """Historical rows carry v1 classes in `class`. Re-derive with the CURRENT scorer so a
    table headed 'scorer v2' actually contains scorer-v2 verdicts."""
    out = []
    for r in rows:
        probe = {"probe_id": r.get("probe_id"), "expected_value": r.get("expected_value"),
                 "unit": r.get("unit", ""), "kind": r.get("kind", "recall")}
        r2 = dict(r)
        r2["class"] = e2.classify(probe, r.get("answer") or {},
                                  r.get("tolerance_pct", 1.0), r.get("finish_reason"))
        g = r.get("guard") or {}
        if "pre_guard_class" in r and "original_value" in g:
            # Only rows written after the A8 fix preserve what the model actually said, so only
            # those can have their pre-guard verdict re-derived. For older rows the stored v1
            # pre_guard_class is kept: it is a v1 verdict, but it was at least computed against
            # the real original answer, whereas re-deriving it from the post-guard row would
            # read every blocked answer as a decline and silently zero out "attempted".
            r2["pre_guard_class"] = e2.classify(
                probe, {"value": g["original_value"], "must_retrieve": False},
                r.get("tolerance_pct", 1.0), r.get("finish_reason"))
        out.append(r2)
    return out


def rows_of(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def cells(prefix: str, tag_filter: str = "") -> dict[str, tuple[Path, list[dict]]]:
    """Newest results file per model tag, for files matching `prefix`."""
    out: dict[str, tuple[Path, list[dict]]] = {}
    for p in sorted(RESULTS.glob(f"{prefix}*.jsonl")):
        rs = rows_of(p)
        if not rs:
            continue
        tag = rs[0].get("model", "?")
        if tag_filter and tag_filter not in tag:
            continue
        out[tag] = (p, rs)          # sorted() means the last one wins = newest stamp
    return out


def tok_median(rs: list[dict]) -> int | None:
    t = [r["completion_tokens"] for r in rs if r.get("completion_tokens") is not None]
    return int(statistics.median(t)) if t else None


def decode_ts(rs: list[dict]) -> float | None:
    """tokens/s from the rows themselves — completion tokens over measured latency."""
    pairs = [(r.get("completion_tokens"), r.get("latency_s")) for r in rs]
    pairs = [(c, l) for c, l in pairs if c and l and l > 0]
    return round(sum(c for c, _ in pairs) / sum(l for _, l in pairs), 1) if pairs else None


def e2_block(title: str, tag_filter: str) -> str:
    out = [f"\n### {title}\n",
           "| model tag | n | exact | dang | unit_mm | range_mm | ambig | decline | trunc |"
           " no_ans | precision | coverage | gate | attempted/blocked/leaked | med tok | t/s |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    skipped = []
    for tag, (p, rs) in sorted(cells("e2-", tag_filter).items()):
        why = excluded_reason(tag)
        if why:
            skipped.append((tag, why))
            continue
        s = e2.score_rows(reclassified(rs), n_expected=N_PROBES)
        fab = s.get("fabrications") or {}
        out.append(
            f"| `{tag}` | {s['n']} | **{s['exact']}** | **{s['dangerous_miss']}** | "
            f"{s['unit_mismatch']} | {s['range_mismatch']} | {s['ambiguous_parse']} | "
            f"{s['honest_decline']} | {s['truncated']} | {s['no_answer']} | "
            f"{s['precision']:.3f} | {s['coverage']:.3f} | **{s['hard_gate']}** | "
            f"{fab.get('attempted','-')}/{fab.get('blocked','-')}/{fab.get('leaked','-')} | "
            f"{tok_median(rs)} | {decode_ts(rs)} |")
    for tag, why in skipped:
        out.append(f"\n> EXCLUDED `{tag}`: {why}")
    return "\n".join(out)


E1_DANGEROUS_NOTE = """
> **The E1 `dangerous` column is a NEW, codified metric — read this before comparing it to the
> showdown record.** The figure was reported throughout the showdown but computed ad hoc and
> never committed, so the historical numbers cannot be reproduced from the artifacts. The
> definition used here is physics-grounded and written down in `rundown.py`: every fault has a
> signature — the engine runs lean (ECU adds fuel) or rich (ECU pulls fuel) — and a **flip
> across that boundary sends the correction the wrong way**, which is the failure mode that
> hurts an engine. A wrong answer *within* a signature still moves fuel the right way and is a
> miss, not a danger.
>
> It reproduces Mistral exactly (30 arm A / 22 arm B@3, matching decisions.md 2026-07-31). It
> disagrees on two cells, in both directions:
>
> | cell | historical (ad hoc) | codified | the disputed case |
> |---|---|---|---|
> | Qwen3.6-35B armB@3 | 3 | **0** | `injector_flow_rich` answered `maf_high` x3 — both RICH signature, correction goes the same way |
> | 27B dense armB@3 MTP-off | 0 | **1** | `injector_flow_rich` answered `maf_low` x1 — rich truth, lean answer, correction goes the WRONG way |
>
> The two are inconsistent with each other under any single rule, which is why the old numbers
> are treated as unrecoverable rather than reverse-engineered.
>
> **THIS NEEDS SYED'S RULING, because it touches a pre-registered bar.** The E1 bar is "90%
> top-1 AND zero dangerous". Under the codified definition the incumbent's **MTP-off** cell
> (93.2%) carries **one** directional flip and would not meet a strict zero-veto reading; its
> MTP-on cell (93.9%) carries none. I am NOT selecting the definition that makes the incumbent
> pass. Options: (a) ratify the codified definition and accept that the 93.2% cell has 1 flip,
> (b) rule that a single flip inside the measured noise band is not a veto, (c) define the veto
> on the deployed configuration (MTP-on), which is clean either way.
"""


def hypothesis_block() -> str:
    return """
## Syed's hypothesis signatures

**H1 — more parameters means better reasoning: NOT SUPPORTED.** The controlled pair is 35B vs
80B (both 3B active, Q8 vs Q6): 90.5% vs 73.5% closed-book. Scaling helped 27B->35B closed-book
and then reversed.

**H2 — retrieval value is MODEL-DEPENDENT, not universal.** +9.5pp for the incumbent at k3,
NEGATIVE for 35B (90.5 -> 83.7) and for gpt-oss (86.4 -> 83.7). A retrieval block is not free:
it is context a model must weigh against its own priors, and the models with stronger priors
were hurt by it.

**H3 — the stored-knowledge signature is absent.** E2 arm A (closed-book) is flat and low across
the whole ladder; every model's value integrity comes from retrieval, not from memorised
calibration constants. This is the finding that most directly justifies the RAG-first
architecture over a bigger fine-tune.
"""


# E1 "dangerous flip", CODIFIED HERE FOR THE FIRST TIME (2026-08-02). The number was reported
# throughout the showdown (Mistral 30, 35B B@3 3, incumbent 0) but computed ad hoc and never
# written down, so it could not be reproduced or audited. Definition, grounded in the physics:
# every fault has a SIGNATURE — whether the engine runs lean (ECU adds fuel, trim positive) or
# rich (ECU pulls fuel). A flip across that boundary sends the correction the WRONG WAY, which
# is the failure mode that hurts an engine. A wrong answer WITHIN a signature still moves fuel
# in the right direction and is merely a miss.
_LEAN_SIG = {"maf_low", "injector_flow_lean", "injector_latency_lean", "vacuum_leak"}
_RICH_SIG = {"maf_high", "injector_flow_rich"}


def _sig(fault: str) -> str:
    return "lean" if fault in _LEAN_SIG else "rich" if fault in _RICH_SIG else "none"


def dangerous_flips(rs: list[dict]) -> int:
    n = 0
    for r in rs:
        got, true = (r.get("answer") or "").strip(), r.get("fault", "")
        if not got or got == true:
            continue
        gs, ts = _sig(got), _sig(true)
        # answering a real fault on a HEALTHY engine also counts: it authorises an edit to a
        # calibration that was correct.
        if (gs != "none" and ts != "none" and gs != ts) or (ts == "healthy" and gs != "none"):
            n += 1
    return n


def e1_block(title: str, tag_filter: str) -> str:
    cfg = Config(cases_path=EVAL_DIR / "data/sim_cases_v2.jsonl")
    out = [f"\n### {title}\n",
           "| model tag | n | top-1 | dangerous | blank | med tok | t/s | finish_reason census |",
           "|---|---|---|---|---|---|---|---|"]
    for tag, (p, rs) in sorted(cells("e1-", tag_filter).items()):
        if len(rs) < 100 or excluded_reason(tag):
            continue                                   # smoke/equivalence artifacts, not cells
        try:
            top1 = f"{e1.score_results(cfg, p).top1:.1%}"
        except Exception as exc:                       # scoring needs the matching case file
            top1 = f"(unscored: {type(exc).__name__})"
        blank = sum(1 for r in rs if not r.get("answer"))
        census = {}
        for r in rs:
            census[str(r.get("finish_reason"))] = census.get(str(r.get("finish_reason")), 0) + 1
        out.append(f"| `{tag}` | {len(rs)} | **{top1}** | **{dangerous_flips(rs)}** | {blank} | "
                   f"{tok_median(rs)} | {decode_ts(rs)} | "
                   f"{', '.join(f'{k}:{v}' for k, v in sorted(census.items()))} |")
    return "\n".join(out)


def bug_ledger() -> str:
    """What each Phase-1 fix actually changed, measured — not asserted."""
    detail = RESULTS / "rescore-v1-vs-v2-detail.tsv"
    lines = ["\n## Bug ledger — what each fix changed (measured)\n",
             "| id | defect | effect on historical verdicts |", "|---|---|---|"]
    rows = [
        ("snippet", "FTS5 24-TOKEN window split `11.8%` into `11`+`8`; token window applied to "
                    "BM25 hits only, so doubly-ranked best docs got the worst evidence",
         "evidence recall 29/69 -> 59/69 (expected value in-window, own source doc)"),
        ("A1", "scorer parsed `[REF n]` citation ids as the stated value",
         "21 rows dangerous_miss -> exact; hit the retrieval arms hardest"),
        ("ranges", "expected values scored on the low endpoint only",
         "folded into the 21 above + 2 exact -> range_mismatch (STRICTER)"),
        ("units", "no unit awareness: 450 mV vs `0.45 V` scored dangerous",
         "36 rows dangerous_miss -> unit_mismatch (gate-neutral, adjudicable)"),
        ("A2", "empty completion scored honest_decline — truncation read as virtue",
         "65 rows honest_decline -> no_answer; cannot be split from `truncated` "
         "retroactively (finish_reason did not exist)"),
        ("A3", "guard blocked every number when retrieval returned nothing",
         "convictions for the RETRIEVER's miss; now abstains (verdict no_evidence)"),
        ("A4", "guard evidence pool included TITLES (page numbers, years)",
         "removed a route by which `p723/1046` could ground a fabrication"),
        ("A7", "score() had no completeness check; EMPTY file returned gate `pass`",
         "the gate was passable by producing no evidence at all"),
        ("A9", "`10-15 psi` healed to 1015 into the evidence pool",
         "healing errors all ran in the permissive direction"),
        ("A10", "dense index built at 5,608 rows while ref_fts held 5,638",
         "30 chunks invisible to the dense ranker for the whole showdown"),
        ("A12", "determinism scored the INTERSECTION; a run that died at case 3 said 3/3",
         "denominator is now the expected case count"),
        ("minus", "infix minus read as a SIGN: `10-15`->[10,-15], `(x-32768)`->[-32768] "
                  "(found by writing the A9 test; in neither audit)",
         "models correctly quoting 15 / 32768 were BLOCKED"),
    ]
    for i, d, e in rows:
        lines.append(f"| {i} | {d} | {e} |")
    if detail.exists():
        n = sum(1 for _ in detail.open())
        lines.append(f"\nPer-probe detail for every changed row: "
                     f"`ml/eval/results/{detail.name}` ({n} rows).")
    return "\n".join(lines)


def main() -> None:
    print("# Bench rundown — corrected matrix (bench-integrity rerun)\n")
    print("All E2 numbers below are scorer v2 on probe file v2 with fixed snippet extraction, "
          "unless the row says otherwise. Old numbers are published beside new in the bug "
          f"ledger. Noise band applied to top-1 comparisons: +/-{NOISE_BAND_PP}pp "
          "(measured 2026-07-31, MTP on-vs-off).\n")
    print("**Caveats that travel with every number in this report:**\n")
    print("- **Quant is a confound across the ladder.** Qwen models run 6-8 bit; the two "
          "100B-class models run 4-bit. The core hypothesis pair (35B Q8 vs 80B Q6, matched "
          "3B active) is unaffected — both above the 4-bit line.")
    print("- **`unit_mismatch` is gate-neutral and does NOT mean 'correct'.** v2 flags unit "
          "differences rather than converting, so a genuinely wrong answer in another unit "
          "(e.g. `30-40 psi` against `300 to 400 kPa`) lands here rather than in "
          "dangerous_miss. These rows need Syed's adjudication before any gate verdict is "
          "treated as final.")
    print("- **Historical rows carry no `finish_reason`**, so their empty completions cannot "
          "be separated into truncated vs no_answer. Only rerun cells have that split.")
    print(e2_block("E2-v2 — value integrity (probes v2, scorer v2)", ""))
    print(e1_block("E1v2 — diagnostic reasoning", ""))
    print(E1_DANGEROUS_NOTE)
    print(hypothesis_block())
    print(bug_ledger())


if __name__ == "__main__":
    main()
