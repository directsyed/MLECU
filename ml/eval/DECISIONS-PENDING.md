# Eval + synthesis — decisions waiting on Syed (2026-07-08)

Ten-minute read. Each knob has my recommendation and why; disagree freely. Nothing generated
becomes eval truth or training data until the relevant knob is signed here (initial + date the
line). Design authority: ROADMAP Phase D — these are the deliberately-Syed-owned choices.

## A. Pre-registration for the first E1 readout (blocks the for-the-record A/B run)
**A1 — the E1 bar.** RECOMMEND: an LLM arm must score ≥85.7% top-1 AND 100% acceptable
(match-or-beat the rules engine on both) to be considered at all; arm B beats arm A only if
+≥5 points top-1 on paired cases (the ROADMAP margin). Goes into DB meta verbatim before the
run. [sign: ____]

## B. E2 probes (generator built: `harness.cli --gen-e2`; draft ONLY until B1-B3 signed)
**B1 — tolerance.** Match = within ±X% of the stated value. RECOMMEND 1.0% (calibration
values are exact; 1% forgives float rendering, not wrong values). [sign: ____]
**B2 — spot-check protocol.** RECOMMEND: you verify a random 20 of ~100 draft probes against
their `quote`+source; if ≥18/20 clean, promote the whole draft to `e2_probes_v1.jsonl`
(fixing the bad ones); if <18, I regenerate with a tightened prompt and you re-sample.
[sign: ____]
**B3 — decline policy.** must_retrieve=true is scored "honest_decline" — never dangerous,
never a match. This makes E2 measure exactly the doctrine (numbers come from retrieval, not
weights). Confirm this is the intent. [sign: ____]

## C. Pair synthesis (generator NOT built yet — starts after C1-C4)
**C1 — pair shape.** RECOMMEND: mirror the harvest schema exactly (symptoms → diagnosis →
change → outcome) so synthetic + organic pairs are one dataset with a `provenance` field
(`organic` | `synthetic:<doc_id>`). [sign: ____]
**C2 — synthetic-fraction cap.** What fraction of the fine-tune set may be synthetic?
RECOMMEND cap 80% (with 82 organic pairs → up to ~400 total for the pilot; Stage-C real
iterations displace synthetic pairs 1:1 as they accumulate — gold pushes out silver).
[sign: ____]
**C3 — spot-check rate.** RECOMMEND 10% of synthetic pairs reviewed by you before training,
sampling weighted toward `subaru_ej`-tagged sources (they matter most and you can judge them
best). [sign: ____]
**C4 — generator model.** The judge model (Qwen3.6-27B) drafts the pairs, same server.
Non-circularity note: the doctrine constrains the JUDGE (never fine-tuned on the corpus it
filters) — it does NOT forbid the corpus feeding the tuning model, which is the pipeline's
whole point. But flagging consciously: judge-drafted synthetic pairs + judge-family base
model for the pilot means the fine-tune partly learns its own family's phrasing. Alternatives
if this bothers you: draft pairs with Claude (different family, costs API money) or accept
and note it. RECOMMEND: accept for the pilot, revisit if C/D results look suspicious.
[sign: ____]

## Already locked (no action — listed so the record is one page)
- E1 scoring = ecutune scoring.py by file path (byte-identical to the 85.7% baseline).
- Arms differ ONLY by the retrieval block; answer enums grammar-pinned; temp 0; 2 runs.
- E2 hard gate: any confidently-wrong calibration value = arm fails outright (pre-committed
  in ROADMAP; not revisitable without a decisions.md entry).
