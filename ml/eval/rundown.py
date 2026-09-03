"""Phase-4 rundown generator, the corrected bench matrix, old numbers beside new.

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
PROBES = {json.loads(l)["probe_id"]: json.loads(l)
          for l in (EVAL_DIR / "data/e2_probes_v2.jsonl").read_text().splitlines() if l.strip()}

# Cells the ledger marked INVALID and which must never appear in a comparison table. Listed
# here WITH the reason rather than silently filtered: a table that quietly drops rows is the
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


def reguarded(rows: list[dict], top_k: int, probes: dict) -> tuple[list[dict], int, int]:
    """Re-apply the CURRENT citation guard to rows guarded by an older version.

    THIS IS EXACT, NOT AN APPROXIMATION, and it is worth being precise about why:

      1. The guard is POST-HOC. It inspects an answer that has already been generated; it never
         changes the prompt, the retrieval, or the model's output. So re-running the model would
         produce the same answer (temp 0, determinism verified 147/147 twice).
      2. `original_value` is preserved in every guard record (the A8 fix). What the model
         actually said survives a block, so the guard can be re-run against it.
      3. Retrieval is deterministic given a fixed index, and the index has not changed since the
         run began. We ASSERT that per row: if the re-retrieved doc ids differ from the ids the
         row recorded, the row is left alone and counted as unverifiable rather than guessed at.

    Together these mean a guard fix is fully retroactive, which is why finding the U+202F and
    engine-code defects mid-run cost re-derivation rather than ~3.5h of re-running cells.
    Returns (rows, n_unblocked, n_unverifiable).
    """
    from dataclasses import replace as _replace
    from harness import citation_guard, retrieval
    cfg = _replace(Config().retrieval, top_k=top_k)
    out, unblocked, unverifiable = [], 0, 0
    for r in rows:
        g = r.get("guard") or {}
        if g.get("verdict") != "blocked" or "original_value" not in g:
            out.append(r)
            continue
        probe = probes.get(r["probe_id"])
        if probe is None:
            out.append(r)
            unverifiable += 1
            continue
        snips = retrieval.retrieve(cfg, probe["question"])
        if [s.ref_doc_id for s in snips] != r.get("retrieved_doc_ids"):
            out.append(r)                      # index drifted, do not guess
            unverifiable += 1
            continue
        v = citation_guard.verify(g["original_value"], [s.snippet for s in snips])
        if v["verdict"] == "blocked":
            out.append(r)
            continue
        r2 = dict(r)
        r2["answer"] = {"value": g["original_value"], "must_retrieve": False}
        r2["guard"] = dict(g, verdict=v["verdict"], unverified=v["unverified"],
                           reguarded_offline=True)
        out.append(r2)
        unblocked += 1
    return out, unblocked, unverifiable


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
    """tokens/s from the rows themselves, completion tokens over measured latency."""
    pairs = [(r.get("completion_tokens"), r.get("latency_s")) for r in rs]
    pairs = [(c, l) for c, l in pairs if c and l and l > 0]
    return round(sum(c for c, _ in pairs) / sum(l for _, l in pairs), 1) if pairs else None


def e2_block(title: str, tag_filter: str) -> str:
    out = [f"\n### {title}\n",
           "| model tag | n | exact | dang | unit_mm | range_mm | ambig | decline | trunc |"
           " no_ans | precision | coverage | gate | attempted/blocked/leaked | med tok | t/s |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    skipped: list[tuple[str, str]] = []
    notes: list[str] = []
    for tag, (p, rs) in sorted(cells("e2-", tag_filter).items()):
        why = excluded_reason(tag)
        if why:
            skipped.append((tag, why))
            continue
        k = rs[0].get("top_k") or (6 if "k6" in tag else 3)
        rs2, unblk, unver = reguarded(rs, k, PROBES) if rs[0].get("guard_active") else (rs, 0, 0)
        if unblk or unver:
            notes.append(f"`{tag}`: {unblk} row(s) un-blocked by the current guard, "
                         f"{unver} unverifiable")
        s = e2.score_rows(reclassified(rs2), n_expected=N_PROBES)
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
    for n in notes:
        out.append(f"\n> RE-GUARDED OFFLINE, {n}")
    return "\n".join(out)


E1_DANGEROUS_NOTE = """
> **The E1 `dangerous` column is a NEW, codified metric, read this before comparing it to the
> showdown record.** The figure was reported throughout the showdown but computed ad hoc and
> never committed, so the historical numbers cannot be reproduced from the artifacts. The
> definition used here is physics-grounded and written down in `rundown.py`: every fault has a
> signature, the engine runs lean (ECU adds fuel) or rich (ECU pulls fuel), and a **flip
> across that boundary sends the correction the wrong way**, which is the failure mode that
> hurts an engine. A wrong answer *within* a signature still moves fuel the right way and is a
> miss, not a danger.
>
> It reproduces Mistral exactly (30 arm A / 22 arm B@3, matching decisions.md 2026-07-31). It
> disagrees on two cells, in both directions:
>
> | cell | historical (ad hoc) | codified | the disputed case |
> |---|---|---|---|
> | Qwen3.6-35B armB@3 | 3 | **0** | `injector_flow_rich` answered `maf_high` x3; both RICH signature, correction goes the same way |
> | 27B dense armB@3 MTP-off | 0 | **1** | `injector_flow_rich` answered `maf_low` x1, rich truth, lean answer, correction goes the WRONG way |
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


def verdict_block() -> str:
    """Per-model verdict against the PRE-REGISTERED bars. Stated, never ratified here."""
    return """
## Verdict against the pre-registered bars

Bars were fixed before any of this ran and are not renegotiated now:
**E1, 90% top-1 AND zero dangerous. E2, zero confident fabrications (hard gate).**

| model | E1v2 armB@3 | E1 bar | E2 best cell (k6+guard) | E2 gate | both? |
|---|---|---|---|---|---|
| **Qwen3.6-27B dense** | **92.5%**, 0 dang | **PASS** | 48 exact / **2 dang** | FAIL | no |
| **gpt-oss-120b** | 78.9%, 0 dang | FAIL | 48 exact / **1 dang** | FAIL | no |
| Qwen3.6-35B-A3B | 83.7%* | FAIL | 47 / 3 | FAIL | no |
| Qwen3-Next-80B Thinking | 72.8%* | FAIL | 44 / 1 | FAIL | no |
| Mistral Small 4 | 44.9%* | FAIL | 34 / 2 | FAIL | no |

\\* not re-run on fixed snippets (finalists only, per Syed 2026-08-01).

### NO MODEL PASSES THE FABRICATION GATE

This hardened on 2026-08-04 when exact-ratio unit conversion was ratified. Under scorer v2,
gpt-oss@k6 was the lone gate pass at 0 dangerous, but its one `unit_mismatch` row was
`324 kPa` against an expected `3.5 bar`. That is 3.24 bar, **7.4% wrong**, and the
gate-neutral class was **shielding a confident fabrication from a safety gate**. Converting
(the ratio is exact) makes it `dangerous_miss` and the pass becomes a FAIL.

Conversion cut both ways, which is the check that it is honest: it also credited correct
answers that v2 denied (`0.45 V` against 450 mV -> exact), lifting the 27B's k6 cell 47 -> 48
exact. `unit_mismatch` is now **0 across every cell**: the class survives only for pairs we
refuse to guess (C/F is affine, lambda/AFR depends on fuel stoichiometry, cc-min/lb-hr on
density), and none occurred.

### What this means

- **Every model fabricates at least one calibration value** in its best configuration. The
  strongest cells are the 27B and gpt-oss at k6, tied on 48 exact, differing by one fabrication.
- **The 27B is the only model that clears the E1 bar**, by a wide margin (92.5% vs 78.9%).
- **The deadlock is gone, but not in anyone's favour**: the question is no longer "which model
  passes" but "is the guard's blind spot closable enough to make either deployable".

Every surviving fabrication across both finalists carries guard verdict `cited`: a number that
IS in the retrieved evidence but answers a different question. That is the guard's documented
blind spot, and it is now the single highest-value safety item in the project.

### What breaks the tie

**E4**: does the right knob move, or does the trim converge by masking? Neither E1 nor E2 can
see that, and it is the axis the deployed system actually runs on. Bars ratified by Syed
2026-08-04 (diagnosis accuracy >=90%, masking = 0 on leak/healthy, clamp violations = 0).

A deployment recommendation is deliberately NOT made here. What the evidence does support:
- **k3 for diagnosis, k6 for value lookup**: now measured on both suites. k3 beats k6 by ~10pp
  on E1 (93.2/93.9 vs 83.7, two deterministic runs); k6 beats k3 on E2 in all five models.
  The existing split is correct on both halves.
- **Closing the citation guard's cited-but-wrong-quantity blind spot** is the prerequisite for
  any model clearing the gate.
"""


def hypothesis_block() -> str:
    return """
## Syed's hypothesis signatures (re-derived on fixed instrumentation)

**H1, more parameters means better reasoning: NOT SUPPORTED.** The controlled pair is 35B vs
80B (both 3B active, Q8 vs Q6): 90.5% vs 73.5% closed-book on E1v2. Scaling helped 27B->35B
closed-book and then reversed. On E2 the same pair is indistinguishable at k6 (47 vs 43 exact),
and the 35B is the WORST closed-book fabricator of the five (14 dangerous of 69).

**H2, retrieval value is MODEL-DEPENDENT, and can be NEGATIVE.** Now measured twice over. On
E1v2 diagnosis, retrieval is worth +9.5pp to the incumbent and NEGATIVE to gpt-oss, and when
the snippet fix gave gpt-oss *better* evidence, it got *worse still* (83.7 -> 78.9, well outside
the +/-0.7pp noise band) while the incumbent was unmoved (93.2 -> 92.5, inside it). The failure
pattern is diagnostic: gpt-oss over-predicts `injector_flow_lean` (13 cases taken from
`injector_latency_lean`, 8 from `maf_low`), i.e. a richer reference block pulls it toward
whatever the excerpts discuss and away from the datalog in front of it. A retrieval block is not
free context; it is context the model must weigh against its own priors.

**H3, the stored-knowledge signature is ABSENT, decisively.** E2 arm A (closed-book) across all
five models: 7-10 exact of 69, precision 0.32-0.70, and 3-14 CONFIDENT FABRICATIONS each. Every
model's value integrity comes from retrieval; none of them carries Subaru calibration constants
in its weights. Asking any of these models to recall a calibration value from memory is asking
for an invented number. This is the single most direct justification in the whole matrix for the
RAG-first architecture over a larger fine-tune.

**H4 (new, not previously hypothesised), top_k 6 dominates top_k 3 on value lookup, in all five
models without exception**: 47>40, 48>42, 47>41, 43>39, 34>29 exact. Coverage rises AND
precision holds or improves, which is unusual, the two normally trade against each other. The
mechanism is visible in the failures: on probe e2-5668-0 the probe's own source document was not
in the top-3 at all. This is evidence against the current k3-for-diagnosis/k6-for-values split
on the value side, and it is the data for the top_k mode-switching conversation.
"""


# E1 "dangerous flip", CODIFIED HERE FOR THE FIRST TIME (2026-08-02). The number was reported
# throughout the showdown (Mistral 30, 35B B@3 3, incumbent 0) but computed ad hoc and never
# written down, so it could not be reproduced or audited. Definition, grounded in the physics:
# every fault has a SIGNATURE: whether the engine runs lean (ECU adds fuel, trim positive) or
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
    """What each Phase-1 fix actually changed, measured, not asserted."""
    detail = RESULTS / "rescore-v1-vs-v2-detail.tsv"
    lines = ["\n## Bug ledger, what each fix changed (measured)\n",
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
        ("A2", "empty completion scored honest_decline, truncation read as virtue",
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
    print("# Bench rundown, corrected matrix (bench-integrity rerun)\n")
    print("All E2 numbers below are scorer v2 on probe file v2 with fixed snippet extraction, "
          "unless the row says otherwise. Old numbers are published beside new in the bug "
          f"ledger. Noise band applied to top-1 comparisons: +/-{NOISE_BAND_PP}pp "
          "(measured 2026-07-31, MTP on-vs-off).\n")
    print("**Caveats that travel with every number in this report:**\n")
    print("- **Quant is a confound across the ladder.** Qwen models run 6-8 bit; the two "
          "100B-class models run 4-bit. The core hypothesis pair (35B Q8 vs 80B Q6, matched "
          "3B active) is unaffected; both above the 4-bit line.")
    print("- **`unit_mismatch` is gate-neutral and does NOT mean 'correct'.** v2 flags unit "
          "differences rather than converting, so a genuinely wrong answer in another unit "
          "(e.g. `30-40 psi` against `300 to 400 kPa`) lands here rather than in "
          "dangerous_miss. These rows need Syed's adjudication before any gate verdict is "
          "treated as final.")
    print("- **Historical rows carry no `finish_reason`**, so their empty completions cannot "
          "be separated into truncated vs no_answer. Only rerun cells have that split.")
    print(verdict_block())
    print(e2_block("E2-v2, value integrity (probes v2, scorer v2)", ""))
    print(e1_block("E1v2, diagnostic reasoning", ""))
    print(E1_DANGEROUS_NOTE)
    print(hypothesis_block())
    print(bug_ledger())


if __name__ == "__main__":
    main()
