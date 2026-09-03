# MLECU Master Roadmap: from certified judge to a driving Forester
*Adopted 2026-07-07. The full-project plan: every remaining arc from first ECU read to "the car is tuned." Amend via PR + decisions.md entry.*
as `docs/ROADMAP.md`: this is a durable project document, not just a session plan.)*

## Context

Three days ago this project had a corpus scraper and a convergence sim. Today it has: a
certified LLM judge (93.1% keep/drop vs adjudicated 3-rater ground truth, pre-registered bars),
~3,200 docs judged with ~2,000 reference keeps, 65 provenance-tracked training pairs, the car's
exact stock ROM decoded (A2WC411D), a ROM-grounded convergence sim (PASS), and a hardware fleet
with a convicted-but-derated GPU running 24h+ stable. Syed's questions answered by this plan:
first ECU read, LLM training, LLM→flash pipeline, safety verification, RomRaider setup, corpus
sufficiency, RAG-vs-fine-tune, definition of done, and application packaging.

**New facts shaping the plan:** Openport 2.0 (Rev-E clone) ACQUIRED · wideband days away ·
tune-time architecture = laptop→LAN→T630 · app = local web dashboard.

**Immutable constraints honored throughout:** the LLM proposes, deterministic clamped
human-reviewed code executes (never designed away) · stock ROM sacred, multi-archived before
any write · 93 octane always · vacuum leak ruled out before tuning conclusions · data sets
priorities · quality-over-scale corpus doctrine · EPYC only after fine-tune-beats-RAG eval.

---

## PHASE A: Close the curation era *(this week; mostly autonomous)*
1. Reference tier completes (~2,560 docs left, ~1.4 days at current pace, batch-restart on crash).
2. **Full pair re-harvest** over the entire judged corpus → `pairs-rubric-r2.jsonl` v2 + stats.
3. Sweep stragglers: 9 gone-marked community docs (one-off pattern proven), 5781 manual review,
   gone-sweep-vs-judge policy decision.
4. r3 rubric backlog (batch, single revision): methodology-genre fix, LLM-content policy,
   qualitative-outcome rule, deliberation cap, reference off-domain anchor. Re-judge NOTHING
   retroactively, r3 governs future judging; r2 verdicts stand (versioned by design).
5. Corpus stats report → PROGRESS.md (the "is it enough" question gets its number, see FAQ).

## PHASE B: Laptop + first contact with the ECU *(gated only on wideband arrival)*
1. **RomRaider/ECUFlash laptop setup** (guide: `car/ecu/LAPTOP-SETUP.md`, to be written):
   ECUFlash + RomRaider + drivers for the Openport; defs pointed at our SubaruDefs checkout;
   RomRaider logger defs for A2WC411D family; FreeSSM as sanity tool.
2. **Openport clone validation before trust** (principles.md doctrine): read ROM ID via the
   KKL/FreeSSM path AND via Openport; identical IDs + identical sample logs = clone certified
   for reads. (Flash trust comes later, after Stage-2 need arises.)
3. **THE FIRST ROM READ** (read-only, battery maintainer on the car, laptop on its OWN BATTERY
   - see `car/ecu/INTERFACE-FAILURE-2026-08-31.md` for why "laptop on AC" was wrong):
   - Read via ECUFlash → save .srf/.bin.
   - Archive: `car/ecu/rom-archive/` + `data-backups/` + a copy off-machine (3 places; sacred).
   - **Verify with our own tooling:** `romread` confirms internal ID @0x2000, expected
     A2WC411D, and produces the semantic table report.
   - **THE DIFF THAT ANSWERS "IS IT REALLY STOCK":** new small feature `ecutune.cli --rom-diff
     A B`, table-level comparison (reusing romread + the reconciliation defs) of HIS read vs
     the harvested stock 3B12504206. Any differing cells = prior tune evidence, mapped to
     semantic table names. This single artifact de-risks every assumption downstream.
4. Wideband install (AEM 30-0300 class) + wiring per the harvested NASIOC/AP guide (doc 5774
   covers the exact rear-O2-tap pattern) + first idle logs (RomRaider CSV → our logparse).

## PHASE C: Stage 0→2: the manual idle-tuning arc *(the learning arc; weeks, Syed drives)*
Per the staged doctrine (Stage 0 mechanical truth → Stage 1 instrument+baseline → Stage 2 idle):
1. Stage 0: smoke/leak test FIRST (a leak poisons every log), compression sanity, cam/timing.
2. Baseline logging sessions: idle + free-rev, the channel set from car/CLAUDE.md.
3. The loop, manually but tool-assisted: logs → `ecutune` binning → bounded proposal → clamp
   report → **Syed reviews** → edit in RomRaider/apply changeset → flash via ECUFlash → re-log.
   Starting scalars stolen from EJ20X-swap threads (already in corpus: docs 883/884/1107...).
4. **Every iteration archived as a training pair** (trims→change→result); this is simultaneously
   tuning the car and building the finest training data the project will ever have.
5. Stage-2 exit gate: trims ±5%, wideband tracking target, stable warm+cold idle.

## PHASE D: The tuning LLM v1 *(parallel with C; learning-priority, Syed drives decisions)*
**RAG vs fine-tune, the standing answer (FAQ #2, doctrine-fixed):** it is not either/or.
- **RAG serves exact values** (table addresses, spec numbers, scalars), weights-recall of
  precise numbers is unreliable and a confident near-miss is engine-grenading. The retrieval
  store = kept reference chunks (FTS5 now, embeddings when dedupe lands).
- **Fine-tune serves reasoning** (the diagnostic arc discipline), pilot QLoRA on a base model
  re-verified at execution time (July pick: Qwen3.6-27B), trained ON the judge-curated corpus,
  that is the pipeline's whole point. Non-circularity constrains the JUDGE, not the tuning
  model: the judge stays a general model never fine-tuned on the corpus it filters.
- **The empirical gate decides the balance:** pilot fine-tune vs RAG-only baseline vs
  RAG+fine-tune hybrid, all on the held-out eval. Winner becomes the brain. EPYC money moves
  ONLY if fine-tune wins AND ambitions exceed 24GB (doctrine).
**Corpus sufficiency (FAQ #1):** for the PILOT: nearly, need ~500–1,000 reasoning exemplars;
have 65 community pairs + ~2,000 reference keeps (knowledge, not arcs) + Stage-C iterations
incoming (gold). Bridge plan: (a) judge-assisted pair synthesis FROM kept reference chunks
(generated Q→reasoning→A grounded in real text, human-spot-checked, provenance-tagged as
synthetic, consciously managed, given we've SEEN LLM-content pollution in the wild), (b)
Stage-C real iterations, (c) scraping continues (weekly NASIOC cookie ritual). For the FULL
model: the 10k–50k target stands, fed by the same pipeline over months.
### The RAG-vs-fine-tune eval: full protocol (the gate, specified)

**Four arms, everything else identical** (same base model, same quant, temp 0, same prompt
family, grammar-constrained JSON, 2 runs each to confirm determinism):
- **A. Base model alone**: the floor/control.
- **B. Base + RAG**: retrieval over judge-kept corpus chunks (FTS5/BM25 now, embeddings later).
- **C. Fine-tuned (QLoRA on curated pairs), no retrieval.**
- **D. Fine-tuned + RAG**: the hypothesized winner.

**Three eval sets, each testing a different failure mode:**
- **E1. Diagnostic reasoning** (extends the existing `sim_cases_v1.jsonl`: 70 → ~150 cases,
  richer multi-point logs): symptoms→cause selection with acceptable-sets. *Mechanical scoring*
  (no judge needed): top-1 % and acceptable-set %, against the standing rules baseline
  (85.7% / 100%). An LLM arm that can't beat a 40-line rules engine has no business near a car.
- **E2. Exact-value integrity** (~100 probes auto-generated FROM reference-tier docs with
  provenance, e.g. "stock Injector Flow Scaling for A2WC411D?"): tests the engine-grenade
  dimension, precise numbers. Scored mechanically: exact/tolerance match %, and separately the
  **dangerous near-miss rate**: a confidently stated wrong value (vs an honest "must retrieve").
  This is the eval's dangerous-cell analog, and it is a HARD GATE: any arm that fabricates
  calibration values with confidence fails outright, whatever its other scores.
- **E3. Real-car cases** (born from Stage-C iterations; starts ~10–20, grows): given real
  binned logs + build context → produce diagnosis + proposed change. Scored against what
  actually fixed the car, adjudicated Syed+Claude **blind to which arm wrote which answer**
  (shuffled, unattributed, the anti-anchoring discipline applied to ourselves). Metrics:
  diagnosis top-1/acceptable %, lever-direction correctness (right table, right direction),
  **unsafe-proposal rate** (changes that would violate clamp bounds pre-clamp, a model that
  habitually proposes clamp-violating magnitudes is a worse partner even though clamps catch it).

**Scoring discipline:** all bars and margins pre-registered in DB meta BEFORE any arm runs
(house rule, third application). Paired comparison on identical items; a winner must clear the
loser by a pre-registered margin (≥5 points on the primary metric or p<0.05 McNemar on paired
outcomes, small-N honesty enforced; no winner declared inside the noise). Also recorded per
arm: latency/doc and VRAM footprint (a 2-point win that doesn't fit in 24GB is not a win yet,
it's the EPYC clause's evidence).

**Decision rule (what "better" means, pre-committed):**
- **C or D beats B** on E1+E3 by margin, with **zero E2 hard-gate violations** → fine-tuning
  proved its value; hybrid D becomes the brain; EPYC clause satisfiable if ambitions also
  exceed 24GB.
- **B ≈ D on everything** → RAG-primary architecture; the fine-tune money/time goes elsewhere;
  EPYC stays closed.
- **Hypothesis on record** (to be validated, not assumed): D wins E3 (reasoning discipline from
  fine-tuning), B and D tie on E2 (retrieval supplies numbers), C alone fails E2, yielding the
  final architecture: *fine-tuned reasoner + mandatory retrieval for exact values + a system
  rule that calibration numbers are never stated from weights, always cited from retrieval*,
  the data-layer mirror of "the LLM never writes the ECU."

**Harness home:** `ml/eval/`: E1 generator extension, E2 probe generator (reads reference
chunks + provenance), E3 case format (mirrors sim_cases contract), arm runners against
llama-server, scoring + report CLI. Built build-priority; eval *design* decisions above stay
Syed-owned and amendable before pre-registration locks them.

## PHASE E: The LLM→ECU bridge *(build-priority; the safety showpiece)*
The pipeline that turns model output into a flashable file; every stage already has its
skeleton in `car/ecutune`:
1. **Diagnosis** (LLM, JSON-schema'd like the judge): reads binned logs + RAG context →
   diagnosis + PROPOSED semantic-table changes with rationale + predicted effect.
2. **Proposal objects** (`ecutune.core.models.Proposal`: exists): LLM output parsed into typed
   cell edits. The LLM string never touches a table directly.
3. **Clamp pipeline** (exists, property-tested): ±3%/iteration, timing ceilings, knock abort,
   fuel-before-timing, ordering gates. Anything clamped is REPORTED as clamped.
4. **NEW `romwrite` module** (the one genuinely new safety-critical build): applies approved
   cell edits to a COPY of the current ROM via the same defs/reconciliation as romread;
   **verification stack:** (a) byte-diff whitelist, only cells belonging to whitelisted
   semantic tables may differ, ANY other byte difference aborts; (b) read-back, romread the
   output file, confirm intended values landed and nothing else moved; (c) checksum handling,
   verify at build time whether ECUFlash auto-fixes Subaru checksums at flash (believed yes) or
   we implement checksum correction ourselves; (d) bounds; every written value re-checked
   against def min/max. Module emits a human-readable CHANGE REPORT (table, cell, old→new,
   which log evidence, which clamps fired).
5. **Human gate:** Syed reviews the change report + diff in the dashboard, ticks the flash
   checklist (battery maintainer on the car, laptop on BATTERY, stock-ROM archived), and ONLY then is the flash file
   released to him. **Flashing itself stays a human act in ECUFlash**: we generate files, we
   never drive the flash tool programmatically. (This is the "LLM never writes the ECU"
   doctrine extended one layer: OUR CODE never writes the ECU either; it writes files a human
   flashes with battle-tested community tools.)
6. **Post-flash verification loop:** next log session auto-compared against predicted effect
   (did trims move the predicted direction/magnitude?); regression = automatic revert
   recommendation with the archived prior ROM.

## PHASE F: The dashboard *(the application; after E's pieces exist as CLIs)*
Local web app served from the T630 (FastAPI + HTMX/simple frontend, stack verified at build
time), LAN-only. Views map 1:1 onto existing artifacts: corpus/judge status (judgment tables) ·
pair browser (harvest JSONL) · log uploader/viewer (logparse) · diagnosis reports · proposal
diffs with clamp annotations + the approve gate · ROM archive/lineage (which ROM is in the car
NOW, tracked forever) · flash checklist ritual. The CLIs remain the engine; the dashboard is
a veneer over the same libraries (mirrors how judge.cli wraps the judge package). Tune-time
flow: laptop logs at the car → drops CSV on the share (or dashboard upload) → T630 analyzes →
Syed approves at any browser.

## PHASE G: Definition of DONE *(FAQ #3, pre-registered now, like everything else)*
**"v1.0; the car is tuned":** all of,
- Idle: trims within ±5%, RPM stable ±50 at target (700/hot per the real ROM), warm AND cold,
  no lean excursions, no hunting. (Stage 2 exit.)
- Cruise/part-throttle: closed-loop trims ±5% across visited load sites; A/F learning stable
  across a week of driving (no runaway relearn).
- Boost: wideband within ±0.3 AFR of target across full pulls; zero sustained knock retard at
  93 oct; no overboost/fuel-cut events. (Stage 3 exit.)
- Drivability: no stumble/hesitation on tip-in (logged + seat-of-pants).
- Durability proof: ~500 miles with stable learning, no new codes beyond the known catless/TGV
  set, timing behavior boring.
- Every table change that got there: proposed→clamped→approved→archived with its evidence.
**"v2.0; the thesis is proven":** a NEW log from the car, fed to the pipeline cold, produces a
diagnosis matching Syed's own read + a proposal he'd have made, the fine-tune-vs-RAG eval run
on real-car cases, passed. That's the portfolio claim: an AI system that tuned a real car
safely. **The EPYC/scale-up question is answered by this gate, not before it.**

## Hardware side-quests (interleaved, non-blocking)
3090 repad/teardown forensics (tamper evidence documented; 1-minute provoked retest exists) →
repair/retire/replace decision · chassis fans → then repad-era PL restoration · CPU2 pair +
BIOS-first discipline · RAM (enables bigger judge/fine-tune models, standing directive) ·
weekly NASIOC cookie ritual · DB snapshot habit before risky ops.

## Immediately executable on approval (today's "go for it" list)
1. Commit this roadmap as `docs/ROADMAP.md` (+ PROGRESS pointer).
2. Write `car/ecu/LAPTOP-SETUP.md`: the full RomRaider/ECUFlash/Openport guide against the
   real defs and the A2WC411D family, ready for the wideband's arrival.
3. Build `--rom-diff` (small: romread twice + table-level compare + report) with tests, ready
   for the first real ECU read.
4. **Eval harness head-start (buildable NOW):** E2 probe generator over the ~2,000 existing
   reference keeps (judge-assisted generation, Syed spot-check) + arm runners/scorers + arms
   A (base) and B (RAG over ref_fts). First base-vs-RAG readout on E1v1+E2 within days,
   locks the baseline side of the gate and produces the weights-recall-danger number that
   underwrites the RAG-for-exact-values doctrine. Arms C/D and E3 remain gated (pairs / car).
5. Keep the tier grinding; full re-harvest when it completes; corpus stats report.
6. Handoff/PROGRESS updates; DB snapshot.

## Verification
- Each phase has its own gate baked in above (clone cross-check, rom-diff clean, Stage-2 trim
  gate, eval bars, byte-diff whitelist, post-flash prediction check, v1.0 checklist).
- Roadmap-level: every safety-critical new module (romwrite) ships with property tests like the
  clamp layer; nothing touches a ROM copy without the whitelist+readback pair passing in CI.
