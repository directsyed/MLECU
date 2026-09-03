# Scoring rubric: community-tier documents (forum threads)   [rubric-r1, DRAFT for Syed review]

You are scoring ECU-tuning forum content for inclusion in a fine-tuning corpus. The corpus
teaches a model to reason from symptoms to diagnosis to a bounded calibration change to a
verified outcome. Score what the document DEMONSTRATES, not how confident it sounds.

Score the document 1-5 against these anchors. When between two anchors, take the LOWER score.

**5. Verified diagnostic arc.** A complete symptoms → diagnosis → change → outcome chain
where: symptoms include data (trims, AFR, RPM, logged values, not "runs bad"); the diagnosis
states a mechanism; the change names the actual table/parameter and magnitude; and the outcome
is REPORTED AFTER the change with data or an unambiguous result. No contradiction with the
reference snippets.

**4. Solid substance, weak verification.** Concrete technical content, real numbers, correct
table/parameter names, sound causal reasoning, but the arc is incomplete: outcome asserted
without data, thread ends before confirmation, or the change is specific while the follow-up is
thin. Nothing contradicts the references. *(This is the keep threshold: content a careful tuner
would trust and learn from, even without a bow on it.)*

**3. Plausible but unanchored.** Genuine technical discussion, mechanism talk, some correct
terminology, but no numbers, no named tables, or an unresolved diagnostic thread. Nothing to
extract; nothing wrong either.

**2. Opinion and anecdote.** Preference talk, hearsay ("my buddy's STI did this"), claims with
no support, or minor factual friction with the references. Harmless but teaches nothing.

**1. Wrong or dangerous.** Contradicts the references on something that damages engines
(fueling/timing/knock direction, safety margins), advises bypassing safety verification, or is
confidently wrong about mechanism. *(Reserved for actively harmful, a kept 1 is the worst
failure this pipeline can produce.)*

Scoring rules:
- Judge the numbers you can check against the reference snippets; note each in claims_checked.
- Popularity, post count, author reputation and thread age are NOT evidence.
- A long thread with one excellent verified exchange amid noise: score the chunk you were given,
  not the thread's average vibe.
- If symptoms/diagnosis/change/outcome pairs are present, extract them (see schema); extract
  ONLY what the text actually states, never infer the missing leg of an arc.
