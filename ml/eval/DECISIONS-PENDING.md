# Eval + synthesis: decisions waiting on Syed (2026-07-08)

Ten-minute read. Each knob has my recommendation and why; disagree freely. Nothing generated
becomes eval truth or training data until the relevant knob is signed here (initial + date the
line). Design authority: ROADMAP Phase D; these are the deliberately-Syed-owned choices.

## A. Pre-registration for the first E1 readout (blocks the for-the-record A/B run)
**A1, the E1 bar.** RECOMMEND: an LLM arm must score ≥85.7% top-1 AND 100% acceptable
(match-or-beat the rules engine on both) to be considered at all; arm B beats arm A only if
+≥5 points top-1 on paired cases (the ROADMAP margin). Goes into DB meta verbatim before the
run. RATIFIED v1 as registered (Syed, 2026-07-09). AMENDMENT ON RECORD: E1v2 -
extend the sim generator with voltage-sweep operating points that break the leak/dead-time
degeneracy, then raise the bar (harder exam, Syed directive). Design session queued.

## B. E2 probes (generator built, `harness.cli --gen-e2`; draft ONLY until B1-B3 signed)
**B1, tolerance.** Match = within ±X% of the stated value. ACCEPTED 1.0% (Syed, 2026-07-09), (calibration
values are exact; 1% forgives float rendering, not wrong values).
**B2, spot-check protocol.** RECOMMEND: you verify a random 20 of ~100 draft probes against
their `quote`+source; if ≥18/20 clean, promote the whole draft to `e2_probes_v1.jsonl`
(fixing the bad ones); if <18, I regenerate with a tightened prompt and you re-sample.
DONE (Syed, 2026-07-09): 20+ checked, accurate, but caught SAMPLING SKEW (all def-file
trivia; ORDER BY id took first-ingested docs). Draft regenerated with hash-scattered
sampling + operational-values prompt; Syed re-samples the new draft before promotion.
**B3, decline policy.** must_retrieve=true is scored "honest_decline", never dangerous,
never a match. This makes E2 measure exactly the doctrine (numbers come from retrieval, not
weights). ACCEPTED (Syed, 2026-07-09).

## C. Pair synthesis (generator NOT built yet, starts after C1-C4)
**C1, pair shape.** RECOMMEND: mirror the harvest schema exactly (symptoms → diagnosis →
change → outcome) so synthetic + organic pairs are one dataset with a `provenance` field
(`organic` | `synthetic:<doc_id>`). ACCEPTED (Syed, 2026-07-09).
**C2, synthetic-fraction cap.** What fraction of the fine-tune set may be synthetic?
RECOMMEND cap 80% (with 82 organic pairs → up to ~400 total for the pilot; Stage-C real
iterations displace synthetic pairs 1:1 as they accumulate, gold pushes out silver). ACCEPTED (Syed, 2026-07-09).
**C3, spot-check rate.** RECOMMEND 10% of synthetic pairs reviewed by you before training,
sampling weighted toward `subaru_ej`-tagged sources (they matter most and you can judge them
best). ACCEPTED (Syed, 2026-07-09).
**C4, generator model.** The judge model (Qwen3.6-27B) drafts the pairs, same server.
Non-circularity note: the doctrine constrains the JUDGE (never fine-tuned on the corpus it
filters); it does NOT forbid the corpus feeding the tuning model, which is the pipeline's
whole point. But flagging consciously: judge-drafted synthetic pairs + judge-family base
model for the pilot means the fine-tune partly learns its own family's phrasing. Alternatives
if this bothers you: draft pairs with Claude (different family, costs API money) or accept
and note it. RECOMMEND: accept for the pilot, revisit if C/D results look suspicious.
RESOLVED (2026-07-15, recorded 2026-07-22): Qwen drafts the bulk (free, local); Claude does
the in-session editorial full-read of everything training-bound (SHERIFF-NOT-DEPUTY rule).
No API spend. This is how batches 1-4 and the v3 full-read actually ran.

## Already locked (no action, listed so the record is one page)
- E1 scoring = ecutune scoring.py by file path (byte-identical to the 85.7% baseline).
- Arms differ ONLY by the retrieval block; answer enums grammar-pinned; temp 0; 2 runs.
- E2 hard gate: any confidently-wrong calibration value = arm fails outright (pre-committed
  in ROADMAP; not revisitable without a decisions.md entry).
