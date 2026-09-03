# Why the rubric is worded the way it is: teaching notes for Syed's review

Read this alongside rubric_community.md. Every anchor choice below is editable; this explains
what breaks if you change it.

## Why anchored rubrics beat a bare "rate 1-5"
A bare scale makes the model invent its own standard, and that standard DRIFTS with document
tone: confident prose scores high, hedged prose scores low, the opposite of what tuning data
needs. Anchors replace taste with observable tests: *are there numbers? is the outcome reported
after the change? does anything contradict a reference?* Two side effects you want: (a) scores
become comparable across a 5,700-doc run because every doc faces the same tests, and (b) YOUR
guard review gets easier; you're checking "did the test apply" rather than "do I share the
model's taste".

## Why the 4/3 boundary gets the sharpest wording
keep_threshold is 4, so the ONLY boundary that changes what enters the fine-tune corpus is
4-vs-3. The distinguishing test is deliberately crisp: **concrete values + correct table names
+ sound causality = 4; technically literate but unanchored = 3.** If you soften "concrete
numbers" to "technical discussion", the corpus fills with mechanism talk that never commits to
values, exactly the LIMA failure mode ("500 clean > 5,000 noisy").

## Why "when torn, take the LOWER score"
LLM judges have a documented central-tendency + leniency bias (they hand out 4s like candy).
An explicit tie-break rule counters it mechanically instead of hoping the model self-corrects.
This will cost some borderline-4s; that is the right trade at our corpus size: a false-reject
costs one doc; a false-keep pollutes training.

## Why 1 is reserved for "dangerous", not just "bad"
The calibration report has a cell for "trusted label ≤2 but judge kept it", the worst failure.
Making 1 mean *actively harmful* (wrong fueling/timing direction, safety bypasses) keeps that
cell meaningful: a kept-1 is an engine-damage vector, not a taste disagreement. Generic junk
lands at 2 and is filtered just the same.

## Why chunk-score ≠ thread-average
Long legacygt threads are 90% noise around one gold exchange. The chunker scores each chunk
independently; pair-harvesting selects per-chunk at ≥4. If we averaged, gold-in-noise threads
would score 2-3 and the best training pairs in the corpus would be discarded.

## Why "extract only what the text states"
The extraction pairs become training TARGETS. If the judge infers the missing outcome of an
unfinished thread, the fine-tune learns to hallucinate outcomes, in a domain where the outcome
is the safety signal. Null extraction (pairs: []) is the expected, correct result for most docs.

## Why reference docs get a different rubric at all
Their trustworthiness is decided by the tier system (source whitelist), not by an LLM's
opinion, judging their correctness would let a 27B model overrule an FSM (backwards). But
extraction QUALITY still varies wildly (a wideband manual's spec table vs its legal
boilerplate), so the light rubric scores usefulness only. defs/logger/ini sources skip even
that (auto_pass) because they are machine-generated: their "quality" is uniform by construction.

## The two decisions still yours (config keys, not prose)
1. `judge.reference_policy`: the auto_pass list currently covers romraider_defs,
   romraider_logger, tunerstudio_ini. Should local_pdf books/FSMs be light_judge (current) or
   also auto_pass? My recommendation: light_judge, PDF extraction quality genuinely varies
   (we found 3 scanned books that extracted zero text; their siblings may have partial junk).
2. `chunking.aggregate`: doc-level rollup: `min` (current; conservative headline score),
   `mean`, or `weighted_mean`. Pair harvesting is per-chunk either way, so this mostly affects
   reporting and the keep-count statistic.
