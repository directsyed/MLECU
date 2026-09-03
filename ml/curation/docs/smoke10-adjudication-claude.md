# Smoke-10 Adjudication: Claude's read (2026-07-05, rubric-r1)

**Purpose:** decide dense-27B vs MoE-35B-A3B for judge duty, and harvest rubric-r1 wording
failures for r2. My scores are stored as `human_label(label_set='smoke-10', rater='claude')`.

**Integrity disclosures, read first:**
1. **I saw both models' scores before rating** (the comparison table). My read is partially
   anchored; every rating below therefore cites the rubric anchor and quoted evidence so the
   reasoning is auditable. **Syed's blind read is the only clean human signal, do yours
   BEFORE reading further.** (Doc list: 880–884, 960–965. `python -m judge.cli` label flow, or
   read from DB and report scores.)
2. **Partial reads:** 883 (read ~5k of 80k + targeted verification), 963 (~5k of 20k),
   884 (~5k of 13k), 960 (sampled + grep-verified pair anchors, not read linearly). Low-confidence
   ratings marked ⚠. Everything else read in full.
3. **Pair verification coverage:** 26 distinctive claims grep-verified against source text
   (all of dense's non-960 pairs; ~half of the 38 total pairs incl. 14 of MoE's 27 on 960).

---

## Per-doc verdicts

### 880 "Ej20X Base Map After Swap" (1.3k chars): **Claude 2** | dense 2 | MoE 2, AGREE
Eight posts of tuner referrals ending in a vendor ad. Zero symptoms, zero data, zero mechanism.
Anchor 2 verbatim ("preference talk... teaches nothing"). Not a 1: nothing dangerous.
*Determinism note: dense judged this doc SIX times across the crash-era runs, score 2 every
time, near-identical rationale wording. Strong reproducibility evidence.*

### 881 "Base Map Needed" (3.2k): **Claude 3** | dense 3 | MoE 3, AGREE
Genuine technical thread: CAL ID conventions (E2ZK003A, "A"=AT), .hex/.bin format guidance, and
a real hypothesis (requested-torque table scaling 100-vs-200 between 05/06 models explaining
power loss). But: symptom is "doesn't have the power it used to" (no logs), no change executed,
no outcome. Anchor 3's exact shape: correct terminology, mechanism talk, nothing to extract.

### 882 "EJ20X Swap" (1.8k): **Claude 2** | dense 2 | MoE 2, AGREE
Swap-opinion posts + shitposting ("MK4 Supras come with 1200hp"). The one technical claim
("more than 5psi will blow the 253") is unsupported opinion. Anchor 2. Harmless, teaches nothing.

### 883 "EJ20X swap?!" (80k, 4 chunks): **Claude 3 ⚠** | dense 2 (min, ch1=2) | MoE 3, SPLIT
The one doc where I side with MoE against dense, with low confidence. Doc-level = min(chunks);
the divergence is chunk 1, which (per both models' own rationales) mixes real integration
content (harness overlay specifics, USDM/JDM wiring) with hearsay performance limits ("couldn't
break 300hp" attributed to forum scraping). Dense weighted the hearsay (anchor 2: "claims with
no support"); MoE weighted the genuine technical discussion (anchor 3). I read anchor 3 as the
better fit, "mostly opinion" (anchor 2's test) is not true of a chunk with concrete harness
detail, but I have NOT fully read ch1. **Guard read should focus here.**
**Extraction findings (important):** dense extracted 5 pairs from chunks 2-3; I verified all
five anchor-quotes exist in the text ("falls on it's face" @5500, air-pump delete → no codes,
"hella rich" exhaust, 240whp build, 20°→10° timing + 25° AVCS @800/1200). Three have honestly
EMPTY legs (change:"" or outcome:""), rubric-compliant (never infer), though incomplete arcs
have limited training value. **MoE extracted ZERO from this doc despite its own ch3 rationale
describing the 240whp arc**, it appears to extract only from docs it scores ≥4. Rubric-r1
never specified extract-always vs extract-on-keep; the two models resolved the ambiguity
differently. → r2 must make this explicit (it was already flagged as Syed's D3 decision).

### 884 "Legacy GT EJ20X/Y Swap" (13k): **Claude 3 ⚠** | dense 3 | MoE 3, AGREE
Excellent *swap execution* log (9-wire AVCS harness merge, TGV delete, immobilizer notes) with
a verified-in-text arc (oil consumption → EJ20Y swap → running, 23mpg; all grep-confirmed).
But by the rubric this is mechanical/electrical content, not a calibration diagnostic arc: no
tables, no logged trims, outcome anecdotal. 3 is right. Dense's 2 extracted pairs are faithful
(both verified); MoE again extracted zero from a sub-4 doc.

### 960 "Tuning for Fuel Economy" (330k, 16 chunks): **Claude 4 ⚠** | dense 4* | MoE 4, AGREE
The gold doc: a years-long disciplined MPG-tuning log with named tables (WGDC, AVCS, IAT comps,
AF3 limits, O2 scaling), quantified before/after outcomes (29.91, 30.30, 27.68→29.57, 28.72,
31.33...), controlled variables (tire pressure, temps, routes), honest failed experiments.
Sampled chunks are textbook 4s and 5s; doc-level min = 4 for both models. *Dense's 4 carries an
asterisk: it only completed 5 of 16 chunks before its old 4096-token budget truncated chunk 5,
re-run at 6144 pending; not held against the model.*
**Pair fidelity (the decisive evidence):**
- Dense 11 pairs: all sampled anchors verified; the 14.3-AFR experiment is framed correctly
  (change=tried 14.3, outcome=27.68, reverted to 14.7 → 29.57).
- MoE 27 pairs: broader and mostly excellent; it caught arcs dense's truncation missed (plug
  experiments BKRE7IEX/SILFR6B8 with exact MPG deltas, MAF-connector fix, caliper regrease,
  87-vs-93 octane, all verified). **BUT one fabricated outcome leg:** its ch0 pair reports
  outcome "29.91 MPG, knock eliminated", the source says the author saw knock at 1.15-1.30
  load, played it safe with AVCS 10°, and got 29.91 MPG. He never verified knock elimination.
  MoE completed an arc leg the author didn't state = the exact failure the pre-registered rule
  disqualifies (a fine-tune learns to assert unverified outcomes, in the safety-critical slot).
  Also minor: its 14.7-AFR pair frames the *revert* as the change (defensible, less faithful).

### 961 "Retune after injector swap?" (2.4k): **Claude 4** | dense 4 | MoE 3, **THE KEEP-FLIP**
My call: **dense is right, and the flip exposes a rubric-r1 wording bug.** The thread has real
logged data (AF correction −20 to +20, learning −7), a physical finding (fuel pooled in a
cylinder, evidence, not speculation), correct causal reasoning (leaking injector → erratic
corrections), and a concrete change (unobtainable DW 650cc side-feeds → OEM 550cc). The arc
lacks only the final confirmation, the thread ends before the outcome. Anchor 4's text
literally names this case: "concrete technical content... but the arc is incomplete: outcome
asserted without data, **thread ends before confirmation**." MoE scored 3 citing anchor 3's
"unresolved diagnostic thread." Both anchors mention unresolved threads → the models forked on
genuinely ambiguous wording. The intended discriminator (concrete values present → 4) favors 4.
→ **r2 fix:** anchor 3 must read "unresolved AND unquantified"; anchor 4 keeps "quantified but
unconfirmed." Note the flip direction: MoE's error is a false REJECT (loses a good doc), the
safe direction, but still a corpus-yield cost.

### 962 "Learning view and reliability tuning" (1.6k): **Claude 3** | dense 3 | MoE 3, AGREE
Correct terminology (LV resolution, CL-to-OL delay), zero data, and the reply is pure anecdote
("would definitely run better"). Anchor 3 on the nose.

### 963 "Cryotune showcase" (20k): **Claude 2 ⚠** | dense 2 | MoE 2, AGREE
Vendor showcase: dyno numbers + mod lists + promos. Numbers without diagnostic reasoning are
advertising, not arcs. Anchor 2. (Partial read; the truncated remainder is more of the same
format per both models' rationales.)

### 964 "Can't open Rom in Romraider" (2.3k): **Claude 2** | dense 2 | MoE 3, SPLIT
Software-support thread: RomRaider defs-vs-ECUFlash-defs confusion, bracket-key UI toggle.
Useful *tooling* trivia, but the corpus trains engine-diagnosis reasoning, zero engine content
here. Anchor 2 ("teaches nothing" for our purpose). **MoE's 3 is the leniency-drift instance:**
it promoted an unresolved app-support thread on terminology alone. → r2: add an explicit
example to anchor 2: "software/tooling support with no engine behavior content scores 2."

### 965 "Deleting CEL and etune options" (2.9k): **Claude 3** | dense 3 | MoE, (not judged; its
run spent the limit on 960's 16 chunks). Planning-phase thread, correct terms (TGV delete, CEL,
break-in), no data, no outcome. The 452whp number is another car entirely. Anchor 3.

---

## Scoreboard

| | exact agreement w/ Claude | keep/drop agreement | fabricated pair legs | pairs verified clean |
|---|---|---|---|---|
| **dense 27B** | 9/10 (miss: 883, Δ1, my ⚠ doc) | **10/10** | **0** | 19/19 sampled (3 with honest empty legs) |
| **MoE 35B-A3B** | 7/10 (misses: 961, 964, +965 n/a) | 9/10 (**false-reject on 961**) | **1** ("knock eliminated") | 26/27, broader coverage |

Temperament: MoE runs ~half a point lenient on noise docs (964) yet flipped conservative on the
one keep-boundary doc (961), inconsistent direction is itself a concern for a gate.
Speed: MoE ~3× faster (27 s vs 78 s per chunk); it alone completed the 16-chunk doc (budget
confound noted). Determinism: dense 6/6 identical on doc 880 across runs; MoE not yet re-run-
tested (do this before final trust).

## Recommendation (pre-registered rule applied)

The rule: MoE takes bulk work only if **no worse on keep/drop AND zero fabrications**. It went
1-for-2 against both conditions, mildly, but the rule exists precisely so "mildly" doesn't get
argued away after the fact. Therefore:

- **Dense 27B = the judge of record for the community tier**: everything that can feed the
  fine-tune. Slow is fine: the community tier is small (~100 docs today) and grows slowly.
- **MoE 35B-A3B = candidate for reference-tier light-judging** (the 4.6k PDF backlog): no pair
  extraction there, keep/drop stakes are lower (a mis-kept page costs noise, not a training
  arc), and 3× speed matters at that volume. Condition: spot-check its reference verdicts in
  the D4 calibration round before the overnight run.
- Re-run doc 960 with dense at the 6144 budget (fairness + the 16 pairs it left unharvested).

## Rubric-r2 work orders harvested from this exercise
1. **3/4 boundary bug (caused the keep-flip):** "unresolved thread" appears in both anchors.
   Fix: 3 = unresolved AND unquantified; 4 = quantified/evidence-backed but unconfirmed outcome.
2. **Extraction policy ambiguity (D3, Syed's call):** extract-always (dense's behavior) vs
   extract-only-on-keep (MoE's). Recommend extract-always ≥3 with per-chunk keep threshold
   governing *harvest*, not extraction.
3. **Empty pair legs:** explicitly allow `""` for absent legs (never infer), and note that
   downstream harvesting requires a non-empty outcome.
4. **Anchor-2 example for tooling threads** (the 964 leniency case).
5. Grounding behavior was correct in every sampled rationale (irrelevant BM25 snippets ignored,
   stated as such), keep that wording as-is.
6. Add Syed's directives: full build-sheet context block + domain-relevance tag
   (subaru-ej / subaru / general) separate from the quality score.
