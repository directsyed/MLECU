# Scoring rubric — community-tier documents   [rubric-r2]

You are scoring ECU-tuning forum content for a fine-tuning corpus that teaches symptoms →
diagnosis → change → verified-outcome reasoning. Score what the chunk DEMONSTRATES. The
governing principle, set by the project owner: **content without a reported, data-backed
outcome is conversation, not training data — however technical it sounds.**

Score 1–5. When torn between two anchors, take the LOWER.

---

**5 — Verified diagnostic/tuning arc with experimental discipline.**
Everything in anchor 4, PLUS the outcome is verified with rigor: controlled variables,
before/after data under comparable conditions, re-baselining after confounded runs, or
repeated confirmation. The author distinguishes what they proved from what they suspect.
*Real example (from this corpus, doc 960):* seven consecutive highway-MPG runs, one variable
changed per run (WGDC −10 → 30.30 MPG; AVCS 15°→10° → 29.91), a failed richer-AFR experiment
(27.68) honestly reported and then RE-RUN against a corrected baseline (29.57) to isolate the
variable. That re-baselining step is 5-grade discipline.

**4 — Complete arc, data-backed outcome, weaker verification.**
ALL FOUR legs present in the text: (a) symptoms with data — logged trims, AFR, RPM, knock
counts, MPG, not "runs bad"; (b) a diagnosis stating a mechanism; (c) a change naming the
actual table/parameter/part and magnitude; (d) **a REPORTED outcome with at least one number
or unambiguous observed result, stated after the change**. What separates 4 from 5: the
outcome is reported but not rigorously verified (single run, uncontrolled conditions, "trims
settled around +2%" without logs attached).
**Hard rule: no reported outcome = NOT a 4. No exceptions for quality of the rest of the arc.**

**3 — Substantive but incomplete.**
Genuine technical content — correct terminology, mechanism reasoning, possibly real logged
numbers — but the arc is missing legs. This includes: unresolved diagnostic threads (even
quantified ones), planning/advice discussions that never execute, and executed changes whose
outcome is never reported.
*Real example (doc 961):* logged AF corrections (−20 to +20), AF learning (−7), a physical
finding (fuel pooled in a cylinder), a sound suspicion, an executed injector swap — and the
thread ends before any outcome. Excellent fragments; incomplete arc; 3. (Under rubric-r1 two
judges split 4-vs-3 on this doc; r2 resolves it: 3.)

**2 — Opinion, anecdote, noise, or redundant tooling talk.**
Preference talk, hearsay, unsupported claims, vendor showcases (dyno numbers in a promotional
frame are advertising, not arcs), service-request threads — AND software/tooling support
threads with no engine-behavior content (definition-file errors, UI questions): the reference
tier already contains authoritative tool documentation; forum tool-support adds nothing.
*Real examples: doc 880 (tuner referrals), doc 963 (vendor showcase), doc 964 (RomRaider
defs-file troubleshooting — correct terminology, zero engine content, redundant with the
reference tier).*

**1 — Wrong or dangerous.**
Contradicts the reference tier on something that damages engines (fueling/timing direction,
knock response, safety margins), advises bypassing safety verification, or is confidently
wrong about mechanism. Reserved for actively harmful — a kept 1 is the worst failure this
pipeline can produce. Generic junk is a 2, not a 1.

---

## Scoring rules
- Judge the chunk you were given, not the thread's average vibe. One gold exchange in a noisy
  thread deserves its score; pair-harvesting works per-chunk.
- Popularity, post count, author reputation, thread age: not evidence.
- Numbers in a promotional context (vendor dyno lists) do not anchor an arc.
- A synopsis of the full document may be provided for context on multi-chunk documents — use
  it to resolve references ("same map as before"), but score only the chunk's own content.

## Extraction rules (applies at every score — extraction is independent of keep/drop)
- Extract every symptoms/diagnosis/change/outcome arc the text actually states, even from
  chunks scoring 3 (harvest filtering happens downstream). From chunks scoring 1–2, extract
  nothing.
- A leg the author did not state is "" (empty string). Never infer. An extracted outcome must
  quote or tightly paraphrase a stated result.
- Most chunks contain NO extractable pairs. pairs: [] is the normal, correct answer.
