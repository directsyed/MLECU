# MLECU: open checklist

> **2026-08-27, STATE CHANGE.** Root cause found (**MAF transfer curve**, not the fuel maps -
> Subaru's 32-bit ECU has no VE table), the deterministic stage + a new sensor-calibration clamp
> category are built and property-tested, and **`romwrite` exists**: including the SH7058
> checksum, which was previously an open ROADMAP question. `ecutune --tune-maf` now produces a
> verified candidate ROM + CHANGE REPORT end to end. Car suite **138 passed**.
> See decisions.md **D22–D25**.
>
> **⏭ SYED'S NEXT ACTIONS ARE NOW:** (1) review the CHANGE REPORT; (2) rule on the two
> safety-config numbers below; (3) flash, then a post-flash verification log.

Live tracker of every open thread, both halves of the project. Updated 2026-08-17 (extended-param
def installed). Ordered by **what blocks the car**, because that is the actual objective.

---


## ⏭ SYED'S NEXT ACTIONS

**Physical (car), the two logs that unblock everything downstream:**
1. **Extended-param VALIDATION log** (short; the def is built AND installed in RomRaider as of
   2026-08-17). Select the new extended params + `P21 Injector PW` + `P7 MAP` + the usual idle set,
   then one continuous file, engine warm: ~30 s idle → a few blips to ~2500 in neutral → ~1 min
   gentle vacuum driving. Claude then validates each channel per the gate in
   `car/ecu/defs/EXTENDED-PARAMS-RECOVERY.md` (IAM ≈1.00, CL/OL flips, injector PW ≈ P21,
   Feedback Knock ~0, Engine Load tracks P200). Channels that fail are DROPPED.
2. **Driving log** (`car/logging/DRIVING-CAPTURE-PROTOCOL.md`): **no boost, vacuum only, P7 MAP
   below ~100 kPa** (that IS your boost gauge; no physical gauge needed), cruise ~1500–3500 rpm,
   light-to-moderate load, many load/rpm cells, 15–30 min, one file. Watch the wideband; lean on
   rising load or any knock retard ⇒ lift. Raw material for the VE/timing build (D19).
   Can be merged with #1 into one session if channel count allows; validation log first regardless.
- **Cold-idle verification**: Syed reports one of the older committed logs
  (`car/logging/idle/`) is a genuine cold start (visible via ECT ramp). Claude:
  verify and, if genuinely cold-stable, close the Stage-2 "warm AND cold" gate. Not yet verified.
- Disconnect the green connectors for normal driving; off-machine ROM copy (3rd location);
  optional 2nd confirming read for byte-stability.

**Desk decisions (from the overnight run; nothing moves until you say):**
1. **Sign off / edit the 74 keeps** in `ml/curation/docs/community-3s-review-2026-08-16.md` (parts 1+2,
   222 docs). Read doc 5793 (ROM read) and 884/944 (EJ20X-in-EJ255-ECU swaps) regardless.
2. **Rule on the E1 "dangerous" definition**: codified lean/rich flip (3.8 E1v2 = 95.2 % / 0) vs "edit
   authorised on a no-table-edit fault" (95.2 % / 6). Decides 3.8's E1 verdict; then re-run `rundown.py`
   over every historical E1 file before comparing models. (`decisions.md` 2026-08-16 finding.)
3. **`judge.cli --reindex`** (+11 reference docs into `ref_fts`) and rebuild `ref_dense_v2.npz`
   (`python -m harness.embed_index --device cuda`, ~4 min, GPU idle), or leave as is.
4. **Community index:** build it or not (`ensure_community_index` + `embed_index --table community_fts
   --out …`, then `RetrievalCfg.community_*`), and how the reviewed keeps get in without rewriting
   `tier`/`judge_score` (proposal: a `human_label` row the predicate ORs into).
5. **Is ≥4 still the right promotion gate** for community docs, given BOTH judges recall only 4/9 of the
   adjudicated 4s? A rubric conversation, not a bar-lowering one.
6. **3.8 as the diagnosis model?** (E4 15/15 vs 13/15; E1v2 depends on #2.) And QLoRA retrain, still yours.
7. Push the unpushed commits when satisfied.

## A. CAR / PHYSICAL: the critical path

Target = **safe daily driving** (correct idle, no stumble, safe AFR under load, no knock).
Conservative, not a power tune. We are now in the **tuning-loop build** (ROADMAP Phase B→C).

### A1. ROM read: ✅ DONE 2026-08-16
Stock 1 MB SH7058 dump captured (FastECU + **green test-mode connectors** = the missing read/write
permission; the ECU was never locked), **byte-identical to a harvested known-stock reference** ⇒
read complete AND ECU un-tuned. Archived (`car/ecu/rom read/` + `data-backups/rom/` + provenance).
History: `car/ecu/ROM-READ-BLOCKER.md` (RESOLVED banner), its "green connectors not applicable to
2005 DBW" elimination was the exact error; corpus doc 5793 (2026-08-16 review) had the fix.
Remaining: off-machine ROM copy (3rd location); optional 2nd confirming read for byte-stability.

### A1b. The MAF correction: BUILT 2026-08-27, awaiting Syed's review
- [x] **Root cause: `sensor.maf_transfer` under-reads progressively above ~10 g/s** (corr +0.838
      vs load +0.708 / rpm +0.737; the hold-one-fixed test moves trim 0.3–5.0 pp vs 3.1–15.3 pp).
      Supersedes the "2.0 L on a 2.5 L VE map" framing; there is no VE table on this platform.
- [x] **Sensor contamination RULED OUT**: cleaned the element, re-drove, curve shape unchanged.
      Remaining candidates: wrong calibration for this intake, or unmetered air through the
      custom MAF→turbo tubing. Only the smoke test separates them; failure direction if a leak
      is later sealed is **rich**, which is safe.
- [x] **Authority finding:** A/F Learning clamps at +14.84%, Correction at ±25.00%. Above 20 g/s
      the car uses ~75% of that ceiling, 6.2% of samples have both maxed. ROM's own
      `fuel.cl_learning_limits` reads ±15.00%. There is no margin left for highway.
- [ ] **SYED: review the CHANGE REPORT**, 14 of 48 cells, 47 bytes + checksum, read-back error
      1.8e-06, no other table moved. Regenerate any time with
      `ecutune --tune-maf logging/drive/drive-2026*.csv --rom <stock> --out cand.bin`
- [ ] **SYED: ratify two safety numbers.** (a) `boost_load_threshold: 1.5` g/rev is wrong for
      this car, `clamp_afr_floor`, whose whole job is preventing lean-at-boost, only acts above
      that load, but this car crosses atmospheric MAP at **≈0.6 g/rev**. (b) `belief_envelope` is
      absent from `config.yaml` and running on pydantic defaults marked "SYED'S TO RATIFY".
- [ ] **First flash**, then a post-flash log. The question it answers: **does the ECU now leave
      closed loop under boost?** That is where the surviving Run 4 channels earn their place.

### A2. Data capture: three-hold DONE; remaining physical items
- [x] **Three-hold capture DONE 2026-08-16** (`car/logging/idle/idle-20260816-0{1,2,3}-*.csv`): warm idle
      **healthy**: trims −0.86 %, no leak signature, no knock. The layer's own verdict via
      `--diagnose`: no confident fault (maf_high vs injector_flow degenerate, honestly refused).
- [x] **MAF baseline MEASURED 2026-08-16**: `MEASURED_MAF_BASELINE_20260816` (708.65 rpm → 3.08 g/s,
      1637.14 → 6.55; ~12 % cross-session variance in provenance). D20 refusal flips to *use* for
      real captures; the sim seed stays `validated=False`.
- [x] **Extended-param logger def built, validated, and INSTALLED in RomRaider (2026-08-17)** -
      57 params for `3B12504206` by sibling reconciliation, cross-corroborated byte-identical
      across two def versions (2009 + v370/2021). `car/ecu/defs/romraider defs/
      logger_STD_EN_v370_3B12504206.xml`. **Channels UNVALIDATED until the live log** (see ⏭).
- [ ] **Stage 0 smoke/leak test, RESEQUENCED by Syed (2026-08-16): after vacuum VE work, before
      ANY boost tuning.** A vacuum-side leak is a trim offset; a boost leak is the lean-detonation
      path. The boost line is absolute (`DRIVING-CAPTURE-PROTOCOL.md`).
- [ ] Read stored DTCs. TGV / catless / exhaust-AVCS deletes should all set codes; their presence
      argues the ROM is unmodified, their absence argues someone suppressed monitors.
- [ ] **Rebuild the DB9 shell** against the molded pin numbers. Dupont jumpers held for the
      stationary three-hold; a *driving* capture shakes connectors, do this before/with the
      driving log if feasible.
- [ ] Ground-loop remedy stays in force: DB9 **pin 5 omitted**, signal wire only.

---

## A3. MVEM re-grounded 2026-08-16 (was, mis-calibrated) - history + residual limits

The 2026-08-15 finding stands as history: the sim constant (2.50 g/s @ 850) was +40 % off this
TGV-deleted engine and would have invented a MAF fault on a healthy car. **Resolved by measurement,
not assumption:** D20 guard built (refuse MAF verdicts on unvalidated baseline), then the three-hold
capture measured the real baseline (A2 above) and the idle operating point was re-grounded
(target 700 rpm, measured airflow). The layer now diagnoses the real holds honestly.

**Residual limits (open, honest):**
- [ ] MVEM *fault dynamics* (leak/latency response curves) are still model-bound, not measured -
      `e4.py`'s status string says exactly this. Only the healthy idle point is real-grounded.
- [ ] ~12 % cross-session MAF variance between the 08-13 log and the 08-16 holds, inside noise for
      idle-fuel work, but it is why `--diagnose` refuses to call maf_high vs injector_flow apart
      without an independent baseline. More captures tighten it.
- E1/E2/E4 remain **sim-bound** for fault cases; re-running them buys comparability, not truth.
      Real-data progress outranks re-scoring sims (workflow directive, 2026-08-16).

## B. ML / EVAL

### B1. Qwen3.8-27B evaluation: COMPLETE
- [x] E1v1 arm A **94.3%** top-1, 100% acceptable
- [x] E1v1 arm B@3 **90.0%**: *measures our retrieval, not the model* (see B2)
- [x] E2 arm B@6+guard, 48 exact / 2 dangerous, **hard gate FAIL** (same as 3.6)
- [x] **E4, passes all four ratified bars; BEATS 3.6 on convergence (15/15 vs 13/15)**
- [x] **E1v2 (147 cases, the set matching 3.6's headline), SPLIT VERDICT:**
      | | top-1 | dangerous |
      |---|---|---|
      | 3.6 (ratified) | 93.9% | **0** |
      | 3.8 arm A | **95.2%** | **7** |
      | 3.8 arm B@3 | **95.2%** | **7** |
      **3.8 is more accurate but FAILS the zero-dangerous half of the ratified bar
      (90% + zero dangerous).** All 14 dangerous misses across both arms are the same
      confusion: `vacuum_leak` → `injector_latency_lean`. 6 of 7 identical in shape; arm A and
      arm B fail on *different cases* but the same count, retrieval changes which ones, not how
      many, consistent with the B2 doc-collapse.
- [ ] **DECISION NEEDED: does 3.8 displace 3.6?** E4 says yes, E1v2 says no. Not auto-decidable.
- [x] RUNDOWN written 2026-08-16: `ml/eval/results/RUNDOWN-2026-08-16-qwen38.md`: every number
      recomputed. **⚠ E1v2 "7 dangerous" is 0 under the codified `dangerous_flips()`** (the six
      leak→latency misses are lean→lean); the handoff used an unwritten "edit on a no-edit fault"
      reading. Which reading is ratified decides the E1 verdict, see F below. PROGRESS entry: with
      the overnight morning report.

### B2. Retrieval is degenerate: the real finding
Only **4 distinct documents** returned across all 70 E1 cases; two appear on **100%** of queries.
Index is healthy (no stale, no fallback); this is a **corpus/query-type mismatch**, not a bug.
- [x] **Re-checked 2026-08-16, 3.6 collapsed WORSE: exactly 3 distinct docs (5714, 621, 5502), each on
      100% of all 147 E1v2 queries; the SAME three 3.8 got.** Both models saw byte-identical evidence,
      so the 93.9/0 vs 95.2/7 gap is model-side only. The ratified "+RAG@3" was a constant 3-page
      preamble (+10 pp for 3.6, 0 for 3.8; 6 pages → back to 83.7). E2 does NOT collapse (325 distinct).
      Writeup `ml/eval/results/DOC-COLLAPSE-2026-08-16.md`, tool `ml/eval/doc_collapse.py`, decisions
      2026-08-16 entry. **Fixing it needs a log-pattern → diagnosis query representation and/or the
      community index. Syed's design call.**
- [ ] Corpus lacks *differential-diagnosis* content (what separates leak from latency). The
      discriminating fact is in our own `CAPTURE-PROTOCOL.md` but not in the retrieval corpus.

### B3. Judge: calibration-gated, NOT swapped
Config reverted to **3.6, the calibrated judge** (2026-07-05: keep/drop 93.1%, ±1 97.7%, dangerous 0).
- [x] Raise judge `max_completion_tokens` 8192 → 24576 (model-agnostic truncation fix)
- [x] **3.8 calibrated 2026-08-16 (n=100, r2, in-memory): keep/drop 91.0 · within±1 98.0 · dangerous 1
      (doc 1081) → FAILS the pre-registered 90/90/0. NOT swapped.** `recal-qwen3.8-20260816.json`.
- [x] **3.6 like-for-like on the Aug-14 build: 90.0 · 98.0 · 0 → PASS by zero margin** (July: 93.1/97.7
      at n=87). `recal-qwen3.6-newengine-20260816.json`. Both judges recall only 4/9 adjudicated 4s.
      decisions.md 2026-08-16 calibration entry.
- [x] **314 pending community docs judged 2026-08-16 13:20–19:40 UTC** on 3.6/new engine, `--no-reindex`,
      0 failed: **2 × 206 · 3 × 93 · 4 × 15 (4.8 % ≥ 4; prior 5.8 %)**; romraider 1 four in 125. Community
      tier fully judged: 641 docs, 34 ≥ 4, 188 at 3. `judge.yield_report --since 2026-08-16T13:00`.

### B4. Community corpus: 637 forum docs invisible to retrieval
`ref_fts` is **reference-tier by construction**; all forum threads are excluded. They hold 4× more
vacuum-leak and 2.5× more smoke-test content than everything currently indexed.
- [ ] **Keep the ≥4 bar unchanged** (Syed). Do NOT lower it.
- [x] **Whole community tier reviewed 2026-08-16**: `ml/curation/docs/community-3s-review-2026-08-16.md`:
      part 1 (95 old 3s) 28 keep / 67 drop; part 2 (93 new 3s + all 34 fours) 46 keep / 81 drop →
      **222 docs, 74 keep, 18 high-value** (884/944 EJ20X-in-EJ255-ECU swaps, 5793 05-Forester ROM-read
      recipe, 5818 05 FXT/VF48/TGV-delete, 891 leak guide + smoke tester, 5891 first EJ255 idle-MAF datum
      4 g/s @850). 17 of the 34 fours recommended NOT to index (need-fit; 6 genuine over-promotions).
      Fable-5 reviewers, 35/222 spot-checked. **Awaiting Syed's sign-off; nothing indexed.**
- [ ] Review ALL docs before anything enters the corpus (Syed); nothing indexed unreviewed.
- [x] Index-coverage machinery built INERT 2026-08-16 (commit `806ce68`): SEPARATE `community_fts`
      + `community_dense_v2.npz`, tier-tagged `RefSnippet`, `RetrievalCfg.community_*` all default
      off, `ensure_community_index()` tested on a tmp DB only. Per-parent cap (`max_per_parent`,
      B7 idea) also built, OFF. Switch-on recipe in the 2026-08-17 process doc.
- [ ] **Syed:** decide whether/when to build the community index on the real corpus, and how the
      reviewed 3s get in without rewriting `tier`/`judge_score` (proposal: a `human_label` row the
      predicate ORs into).

### B5. Fine-tune pairs as RAG content: viable, sequenced second
242 train + 28 val pairs, format `symptom → diagnosis → change → expected result`.
- Contamination: **E1 0/217 clean**, E2 3/69 need a manual look.
- Coverage gap: **0 pairs mention injector latency, 3 mention vacuum leak**: will NOT fix the
  failures we found. The 27 forum docs discussing leaks are the better target.
- [ ] Add **provenance** before indexing. Pairs carry no source link, and mean 3.4 numbers per
      answer would enter the grounding path unsourced, the exact fabrication surface E2 polices.

### B7. E2 hard gate: root cause of the 2 leaks (IDEAS, not commitments)

Traced both dangerous misses to source. **They are different failures wearing the same label**, and
one of them is not a model error at all.

**Leak 1, `e2-2097-0`: the true D16 blind spot.** Source doc 2097 *was* retrieved and contains the
truth (`SOi at 20° crank-angle BTC`). But an adjacent chunk of the **same Heywood book** (doc 2096)
was also retrieved and contains `HCCI, θinj = 64° BTC`. Model answered 64°. Guard said `cited` -
**correctly**, since 64 genuinely appears in evidence. Right topic, right book, adjacent page,
wrong quantity.

**Leak 2, `e2-5668-0`: a RETRIEVAL MISS, not a fabrication.** Source doc 5668 (`...upgrading
214 cc/min Bosch injectors to 288 cc/min Lucas injectors`) was **never retrieved**: five of its own
neighbouring chunks were. The model read doc 5663's spec table faithfully and answered
`237 cc/min for the six-injector, one-turbo configuration; 218 cc/min for the 12-injector,
three-turbo configuration`, **verbatim accurate to the evidence it was given**, qualifiers intact.
It was asked a question whose answer was not in its context. Scored as a dangerous fabrication;
the model did nothing wrong.

**Ideas to evaluate, none committed:**
- **Fix retrieval first.** Half the gate failure is a retrieval miss. The B2 corpus/retrieval work
  would take this from 2 leaks to 1 without touching model or guard. *Cheapest, highest confidence.*
- **Chunk-neighbour suppression / de-dup at retrieval.** Both leaks involved 4–6 adjacent chunks of
  one book filling top-k, crowding out the source in one case, supplying the distractor in the
  other. Retrieval-side only; no model or guard implications.
- **Supporting-sentence-verbatim (the deferred D16 schema change).** Only thing that catches leak 1:
  requiring the model to return the sentence it drew the number from would expose that the cited
  sentence is about a different case. Deterministic, no second model. Schema change.
- **Semantic check**: rejected reasoning stands: makes the clamp only as trustworthy as a model.
- **A fine-tune would NOT fix either, and likely worsens it.** Arm C's recorded failure was an
  E2 fabrication explosion (confident-wrong 45/69 = 65%) because pairs taught *register, not values*.
  Both leaks are number-*selection* problems under evidence; parametric confidence is the wrong
  medicine. **This is the strongest evidence in the suite against a fine-tune for E2.**

### B6. Honest limit on "judging for retrieval value"
**A text judge cannot know whether a fix actually worked.** A confidently wrong forum post is
indistinguishable from a correct one. A judge can only assess *markers of verifiability* -
outcome reported, causal chain present, numbers with units and conditions, thread resolved,
corroboration. Correctness would require cross-checking claims against MVEM / the deterministic
layer (narrow and expensive), which is the only path that does not reduce to one model grading
another's confidence.

---

## C. STANDING RULES EARNED THE HARD WAY
- **D18, performance beats comparability** when they conflict; disclose confounds, don't preserve
  stale configs to protect a historical number.
- Any reboot **silently disarms** the Openport driver-signature bypass. Check it first on every
  "logging stopped working."
- Never use **Shut down** on the tuning laptop. Fast Startup preserves wedged driver state. Restart.
- `ml/eval/.venv` has no numpy; the harness runs from **`car/.venv`**.
- `pgrep`/`pkill -f` match **your own shell**: kill by PID.
- Token budget and timeout must rise **together**; 8192/600s truncated thinking-models and
  understated them by up to 14pp.

---

## D. CLAUDE'S NEXT BUILDS (gated on Syed's two logs)
- [ ] **Validate the extended-param channels** against Syed's validation log (the gate table in
      `EXTENDED-PARAMS-RECOVERY.md`); add ONLY the passing ones as canonical roles in
      `car/ecutune/logparse/schema.py` (`feedback_knock`, `target_afr`, `iam`, `target_boost`,
      `manifold_pressure`, …).
- [ ] **VE + timing proposers (D19)** from the driving log: per-cell `VE_correction =
      measured_AFR / target_AFR` (target from the validated `CL/OL Fueling Target` channel, else
      the ROM's `fuel.target_afr_primary` map); timing retreat-only on `Feedback Knock`. Plug into
      `STAGE_REGISTRY` behind the existing clamps (`ve_rate_limit ±3 %`, `knock_auto_abort`,
      `timing_row_ceiling`).
- [ ] **`romwrite`** (ROADMAP Phase E; nothing exists): inverse encoder, byte patcher on a copy,
      SH7058 checksum recompute, byte-diff whitelist · read-back · bounds · human CHANGE REPORT -
      all behind `safety/` so the `test_write_path.py` source-scan invariant holds.
- [ ] Then the **first FastECU write** (a milestone of its own; write path UNPROVEN, only read is)
      → re-log → post-flash verify → the first closed iteration → **E3 becomes runnable** (bars
      pre-registered in DB meta before any arm runs).
- [ ] (Parked, Syed skipped:) file the FastECU upstream bug report, still ready if wanted.

## E. NEEDS SYED PHYSICALLY (car)
- [x] ~~SID 0x34 sweep~~, OBSOLETE: the ROM read succeeded 2026-08-16 (green test-mode
      connectors); the sweep was diagnostic scaffolding for a solved problem.
- [ ] **Extended-param validation log** then **the vacuum driving log**: see ⏭ at top; these are
      the two that unblock D19.
- [ ] DTC re-read after a drive cycle · DB9 shell rebuild · Stage 0 smoke test (resequenced:
      before boost, after vacuum VE) · off-machine ROM copy.

## F. NEEDS SYED'S DECISION (do not decide unilaterally)
- [ ] **Does 3.8 displace 3.6?** E4 says yes (15/15 vs 13/15); E1v2 says no (7 dangerous vs 0).
- [ ] **Retrain QLoRA on 3.8?** Arms C/D can't run; the adapter is welded to Qwen3.6. My read is
      *not yet* (the pilot failed on data, not base model), but it's his call.
