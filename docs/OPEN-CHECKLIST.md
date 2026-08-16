# MLECU — open checklist

Live tracker of every open thread, both halves of the project. Updated 2026-08-16 (overnight run).
Ordered by **what blocks the car**, because that is the actual objective.

---

## A. CAR / PHYSICAL — the critical path

The ROM read gates the write path, and a tune must be **written to be tested**. Deadline ~2 weeks
from 2026-08-14; target = **safe daily driving** (correct idle, no stumble, safe AFR under load,
no knock). Conservative, not a power tune.

### A1. ROM read — BLOCKED at kernel upload  ← highest priority
Settled by byte-level J2534 capture (`car/logging/j2534_shim.log`):
**the ECU is NOT locked** (seed returned, key accepted, programming session granted) and
**the cable is NOT faulty** (clean checksummed NRC returned). Failure is isolated to
`RequestDownload` → `7F 34 10 generalReject`.

- [ ] **Build the key-substituting shim on Windows** — code written, tested, pushed.
      `cargo +stable-i686-pc-windows-gnu build --release` in `car/ecu/j2534-shim/`
- [ ] **Verify the shim loads in EcuFlash** (copy into EcuFlash's own folder as `op20pt32.dll`).
      **Untested — everything in Track A depends on it.** Success = `==== shim init:` in DebugView.
- [ ] Enable `TACTRIX_SHIM_FIXKEY=1`, attempt read. EcuFlash's key is replaced with FastECU's
      (proven-accepted) key → EcuFlash proceeds into its own sti05 kernel upload.
- [ ] Fallback: FastECU rebuild with the hardcoded `dataFormatIdentifier` (0x04) parameterised.
      Plan: `~/.claude/plans/rebuild-the-fastecu-plan-velvety-anchor.md`
- [ ] File the upstream bug report — `car/ecu/FASTECU-SH7058-KLINE-BUG.md` is written and ready.
      **Do this in parallel from day one**, not as a last resort.
- [ ] Last resort only (Syed's call): bench `shbootmode` (Renesas boot mode bypasses OBD security).

### A2. Data capture — UNBLOCKED, do in parallel
- [ ] **Stage 0 smoke/leak test** — non-negotiable, precedes all logging. Do we have a smoke tester?
- [ ] Read stored DTCs. TGV / catless / exhaust-AVCS deletes should all set codes; their presence
      argues the ROM is unmodified, their absence argues someone suppressed monitors.
- [ ] **Rebuild the DB9 shell** against the molded pin numbers. Dupont jumpers are fine for a
      stationary test, not for a real capture. (Original crimp landed on the wrong pin.)
- [ ] Run the **three-hold capture** (`car/logging/CAPTURE-PROTOCOL.md`) — warm idle / fast idle /
      loaded idle. Channels per `car/logging/IDLE-LOG-PROFILE.md`.
- [ ] **Measure the MAF baseline on THIS engine** and populate `mvem.MafBaseline.from_capture()`.
      2026-08-16: the sim seed is now `SIM_MAF_BASELINE` (`validated=False`) and the estimator
      REFUSES MAF verdicts against it (D20) — so this is no longer "provisional", it is "withheld".
- [ ] Ground-loop remedy stays in force: DB9 **pin 5 omitted**, signal wire only.

---

## A3. ⚠ MVEM IS MIS-CALIBRATED FOR THIS ENGINE — validated 2026-08-15

**The deterministic layer would misdiagnose this healthy car.** Measured against the first real
warm-idle log:

| | value |
|---|---|
| `NOMINAL_MAF_IDLE` (sim constant) | **2.50 g/s** @ 850 rpm |
| real car, warm idle | **3.493 g/s** @ **709 rpm** |
| error | **+40%** (and worse normalised — *lower* rpm should mean *less* air) |

Feeding the real log to `identify.maf_belief_ratio()` returns **1.397** — a confident
**"MAF believed +39.7% off"** verdict, on a car whose total fuel trim is **+0.31%**, i.e. fuelling
is essentially correct. That term is the *only* thing separating a MAF fault from an injector-flow
fault, so today the layer is primed to invent a MAF fault on a healthy engine.

Cause is almost certainly the **TGV deletes** (plus exhaust-AVCS delete) raising idle airflow —
exactly what `CAPTURE-PROTOCOL.md` predicted when it flagged 2.50 as a sim value that "must be
established empirically on this engine."

- [x] **Do NOT simply hardcode 3.49** — nothing does (D20, commit `58c8ec2`).
- [x] rpm-indexed baseline exists: `mvem.MafBaseline` (points, `validated`, `provenance`; `.at(rpm)`);
      the sim seed is marked UNVALIDATED. Populate via `MafBaseline.from_capture()` after Stage 0 +
      the three holds. **The value is still unmeasured** — that is the open item, above in A2.
- [x] Until then the layer **refuses** MAF verdicts on unvalidated data (`identify()` returns
      `identifiable=False` with the ratio + trims-only ranking; `clamp_diagnosis_agreement` blocks
      writes). Bluntness note for Syed: any ratio outside 0.999–1.001 refuses — widen if desired.

### ⚠ What this means for every benchmark number
All of E1/E2/E4 are **sim-bound** — E4's own status string says
`"sim-calibrated-pending (MVEM not yet validated against the real engine)"`. We now have the first
evidence the sim's healthy baseline is 40% off for this car. **Chasing eval scores has unproven
transfer until MVEM is re-grounded.** The real-car data is what makes the numbers mean anything.

## B. ML / EVAL

### B1. Qwen3.8-27B evaluation — COMPLETE
- [x] E1v1 arm A **94.3%** top-1, 100% acceptable
- [x] E1v1 arm B@3 **90.0%** — *measures our retrieval, not the model* (see B2)
- [x] E2 arm B@6+guard — 48 exact / 2 dangerous, **hard gate FAIL** (same as 3.6)
- [x] **E4 — passes all four ratified bars; BEATS 3.6 on convergence (15/15 vs 13/15)**
- [x] **E1v2 (147 cases, the set matching 3.6's headline) — SPLIT VERDICT:**
      | | top-1 | dangerous |
      |---|---|---|
      | 3.6 (ratified) | 93.9% | **0** |
      | 3.8 arm A | **95.2%** | **7** |
      | 3.8 arm B@3 | **95.2%** | **7** |
      **3.8 is more accurate but FAILS the zero-dangerous half of the ratified bar
      (90% + zero dangerous).** All 14 dangerous misses across both arms are the same
      confusion: `vacuum_leak` → `injector_latency_lean`. 6 of 7 identical in shape; arm A and
      arm B fail on *different cases* but the same count — retrieval changes which ones, not how
      many, consistent with the B2 doc-collapse.
- [ ] **DECISION NEEDED: does 3.8 displace 3.6?** E4 says yes, E1v2 says no. Not auto-decidable.
- [x] RUNDOWN written 2026-08-16: `ml/eval/results/RUNDOWN-2026-08-16-qwen38.md` — every number
      recomputed. **⚠ E1v2 "7 dangerous" is 0 under the codified `dangerous_flips()`** (the six
      leak→latency misses are lean→lean); the handoff used an unwritten "edit on a no-edit fault"
      reading. Which reading is ratified decides the E1 verdict — see F below. PROGRESS entry: with
      the overnight morning report.

### B2. Retrieval is degenerate — the real finding
Only **4 distinct documents** returned across all 70 E1 cases; two appear on **100%** of queries.
Index is healthy (no stale, no fallback) — this is a **corpus/query-type mismatch**, not a bug.
- [x] **Re-checked 2026-08-16 — 3.6 collapsed WORSE: exactly 3 distinct docs (5714, 621, 5502), each on
      100% of all 147 E1v2 queries; the SAME three 3.8 got.** Both models saw byte-identical evidence,
      so the 93.9/0 vs 95.2/7 gap is model-side only. The ratified "+RAG@3" was a constant 3-page
      preamble (+10 pp for 3.6, 0 for 3.8; 6 pages → back to 83.7). E2 does NOT collapse (325 distinct).
      Writeup `ml/eval/results/DOC-COLLAPSE-2026-08-16.md`, tool `ml/eval/doc_collapse.py`, decisions
      2026-08-16 entry. **Fixing it needs a log-pattern → diagnosis query representation and/or the
      community index — Syed's design call.**
- [ ] Corpus lacks *differential-diagnosis* content (what separates leak from latency). The
      discriminating fact is in our own `CAPTURE-PROTOCOL.md` but not in the retrieval corpus.

### B3. Judge — calibration-gated, NOT swapped
Config reverted to **3.6, the calibrated judge** (2026-07-05: keep/drop 93.1%, ±1 97.7%, dangerous 0).
- [x] Raise judge `max_completion_tokens` 8192 → 24576 (model-agnostic truncation fix)
- [x] **3.8 calibrated 2026-08-16 (n=100, r2, in-memory): keep/drop 91.0 · within±1 98.0 · dangerous 1
      (doc 1081) → FAILS the pre-registered 90/90/0. NOT swapped.** `recal-qwen3.8-20260816.json`.
- [x] **3.6 like-for-like on the Aug-14 build: 90.0 · 98.0 · 0 → PASS by zero margin** (July: 93.1/97.7
      at n=87). `recal-qwen3.6-newengine-20260816.json`. Both judges recall only 4/9 adjudicated 4s.
      decisions.md 2026-08-16 calibration entry.
- [ ] Judge the **314 pending** community docs — **RUNNING since 2026-08-16 13:20 UTC** on 3.6/new
      engine, `--no-reindex`, sources romraider/legacygt/msextra/forester (303 of them were invisible
      until the gone-filter fix `7e0c5d5`). Doc-atomic + resumable; yield via
      `judge.yield_report --since 2026-08-16T13:00`. See the morning report.

### B4. Community corpus — 637 forum docs invisible to retrieval
`ref_fts` is **reference-tier by construction**; all forum threads are excluded. They hold 4× more
vacuum-leak and 2.5× more smoke-test content than everything currently indexed.
- [ ] **Keep the ≥4 bar unchanged** (Syed). Do NOT lower it.
- [x] **The 95 threes reviewed 2026-08-16** — `ml/curation/docs/community-3s-review-2026-08-16.md`:
      **28 keep / 67 drop** on retrieval usefulness (markers of verifiability, not correctness);
      needs census: MegaSquirt/generic dominate, `maf_baseline` = 0 docs. New 3s from the C2 run
      need the same pass. **Awaiting Syed's sign-off — nothing indexed.**
- [ ] Review ALL docs before anything enters the corpus (Syed) — nothing indexed unreviewed.
- [x] Index-coverage machinery built INERT 2026-08-16 (commit `806ce68`): SEPARATE `community_fts`
      + `community_dense_v2.npz`, tier-tagged `RefSnippet`, `RetrievalCfg.community_*` all default
      off, `ensure_community_index()` tested on a tmp DB only. Per-parent cap (`max_per_parent`,
      B7 idea) also built, OFF. Switch-on recipe in the 2026-08-17 process doc.
- [ ] **Syed:** decide whether/when to build the community index on the real corpus, and how the
      reviewed 3s get in without rewriting `tier`/`judge_score` (proposal: a `human_label` row the
      predicate ORs into).

### B5. Fine-tune pairs as RAG content — viable, sequenced second
242 train + 28 val pairs, format `symptom → diagnosis → change → expected result`.
- Contamination: **E1 0/217 clean**, E2 3/69 need a manual look.
- Coverage gap: **0 pairs mention injector latency, 3 mention vacuum leak** — will NOT fix the
  failures we found. The 27 forum docs discussing leaks are the better target.
- [ ] Add **provenance** before indexing. Pairs carry no source link, and mean 3.4 numbers per
      answer would enter the grounding path unsourced — the exact fabrication surface E2 polices.

### B7. E2 hard gate — root cause of the 2 leaks (IDEAS, not commitments)

Traced both dangerous misses to source. **They are different failures wearing the same label**, and
one of them is not a model error at all.

**Leak 1 — `e2-2097-0`: the true D16 blind spot.** Source doc 2097 *was* retrieved and contains the
truth (`SOi at 20° crank-angle BTC`). But an adjacent chunk of the **same Heywood book** (doc 2096)
was also retrieved and contains `HCCI, θinj = 64° BTC`. Model answered 64°. Guard said `cited` —
**correctly**, since 64 genuinely appears in evidence. Right topic, right book, adjacent page,
wrong quantity.

**Leak 2 — `e2-5668-0`: a RETRIEVAL MISS, not a fabrication.** Source doc 5668 (`...upgrading
214 cc/min Bosch injectors to 288 cc/min Lucas injectors`) was **never retrieved** — five of its own
neighbouring chunks were. The model read doc 5663's spec table faithfully and answered
`237 cc/min for the six-injector, one-turbo configuration; 218 cc/min for the 12-injector,
three-turbo configuration` — **verbatim accurate to the evidence it was given**, qualifiers intact.
It was asked a question whose answer was not in its context. Scored as a dangerous fabrication;
the model did nothing wrong.

**Ideas to evaluate — none committed:**
- **Fix retrieval first.** Half the gate failure is a retrieval miss. The B2 corpus/retrieval work
  would take this from 2 leaks to 1 without touching model or guard. *Cheapest, highest confidence.*
- **Chunk-neighbour suppression / de-dup at retrieval.** Both leaks involved 4–6 adjacent chunks of
  one book filling top-k — crowding out the source in one case, supplying the distractor in the
  other. Retrieval-side only; no model or guard implications.
- **Supporting-sentence-verbatim (the deferred D16 schema change).** Only thing that catches leak 1:
  requiring the model to return the sentence it drew the number from would expose that the cited
  sentence is about a different case. Deterministic, no second model. Schema change.
- **Semantic check** — rejected reasoning stands: makes the clamp only as trustworthy as a model.
- **A fine-tune would NOT fix either, and likely worsens it.** Arm C's recorded failure was an
  E2 fabrication explosion (confident-wrong 45/69 = 65%) because pairs taught *register, not values*.
  Both leaks are number-*selection* problems under evidence; parametric confidence is the wrong
  medicine. **This is the strongest evidence in the suite against a fine-tune for E2.**

### B6. Honest limit on "judging for retrieval value"
**A text judge cannot know whether a fix actually worked.** A confidently wrong forum post is
indistinguishable from a correct one. A judge can only assess *markers of verifiability* —
outcome reported, causal chain present, numbers with units and conditions, thread resolved,
corroboration. Correctness would require cross-checking claims against MVEM / the deterministic
layer (narrow and expensive), which is the only path that does not reduce to one model grading
another's confidence.

---

## C. STANDING RULES EARNED THE HARD WAY
- **D18 — performance beats comparability** when they conflict; disclose confounds, don't preserve
  stale configs to protect a historical number.
- Any reboot **silently disarms** the Openport driver-signature bypass. Check it first on every
  "logging stopped working."
- Never use **Shut down** on the tuning laptop — Fast Startup preserves wedged driver state. Restart.
- `ml/eval/.venv` has no numpy; the harness runs from **`car/.venv`**.
- `pgrep`/`pkill -f` match **your own shell** — kill by PID.
- Token budget and timeout must rise **together**; 8192/600s truncated thinking-models and
  understated them by up to 14pp.

---

## D. TONIGHT — runnable with Syed asleep (no human input needed)
- [x] **3.6 doc-collapse re-check — DONE 2026-08-16: collapsed worse (3 constant docs, 100% coverage,
      same as 3.8).** See B2.
- [x] **Judge calibration of 3.8** — running 2026-08-16 (in-memory via `judge.recalibrate`, no DB
      mutation; the "skips judged docs" blocker never applied to this path). Results in the
      2026-08-17 morning report.
- [ ] **File the FastECU upstream bug report** — Syed chose to skip it on 2026-08-16; still ready.

## E. NEEDS SYED PHYSICALLY (car)
- [ ] **The 5-value SID 0x34 sweep** — everything is built and verified; see handoff §1 for the
      exact commands. Control run first (unset ⇒ must still fail `7F 34 10`).
- [ ] Stage 0 smoke/leak test · DTC re-read after a drive cycle · DB9 shell rebuild ·
      the three-hold capture.

## F. NEEDS SYED'S DECISION (do not decide unilaterally)
- [ ] **Does 3.8 displace 3.6?** E4 says yes (15/15 vs 13/15); E1v2 says no (7 dangerous vs 0).
- [ ] **Retrain QLoRA on 3.8?** Arms C/D can't run — the adapter is welded to Qwen3.6. My read is
      *not yet* (the pilot failed on data, not base model), but it's his call.
