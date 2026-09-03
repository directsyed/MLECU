# AUTONOMOUS RUN RUNBOOK: execute tonight, unattended

**You are the executing agent. Syed is asleep. This is a decision TREE, not a script; you choose
branches based on what each step actually returns.** Narrative context:
`2026-08-16-qwen38-eval-and-rom-read-attack.md`. Live tracker: `docs/OPEN-CHECKLIST.md`.

## SYED'S THREE RULINGS (asked and answered before this run, do not re-decide)

1. **STOP BEFORE INSERTION.** Do everything up to and including reviewing the score-3 docs, write
   per-doc recommendations, and **stop**. *Nothing enters the retrieval corpus without his sign-off.*
2. **MVEM: guard + make nominal rpm-dependent.** Add a guard so the estimator refuses a confident
   MAF verdict against an unvalidated baseline, AND restructure `NOMINAL_MAF_IDLE` from a scalar
   into an rpm-indexed function the capture can populate. **Do NOT guess the value.**
3. **Community docs get a SEPARATE index, kept distinct**: tagged by tier, provenance preserved.
   Do NOT relax the reference filter, do NOT rewrite `tier` on surviving docs.

## HARD RULES
- **Never write to `document.tier`.** It is provenance.
- **Never insert anything into a retrieval index tonight.** Build machinery, leave it inert.
- Corpus backup exists: `data-backups/corpus-pre-3.8-judge-20260815.sqlite`. Re-back-up before any
  DB write.
- Harness/eval work runs from **`car/.venv`**. Judge work runs from **`ml/curation/.venv`**.
  `ml/eval/.venv` has no numpy and fails in ways that look like real failures.
- `pgrep`/`pkill -f` **match your own shell**: kill by PID.
- Use a **backgrounded wait that notifies** for long jobs. A watcher writing to a log file does not
  notify anyone and the run sits finished for hours. (This happened; Syed called it out.)
- Verify every change (tests, smoke) and record what you verified. Everything must be revertible.

## PRECONDITIONS
- `llama-server` serving **Qwen3.8 Q8** on `127.0.0.1:8080`, ctx 32768. Confirm:
  `curl -sf http://127.0.0.1:8080/v1/models`. If dead, restart with `/tmp/start_q38.sh`.
  **ctx 65536 fails** (`rs cache` allocation, GPU0 is the constraint), do not raise it.
- Judge config is **3.6** (correct, a premature swap was reverted in `b6ed448`).
  `max_completion_tokens` is already raised to 24576; keep it.
- Repo clean and pushed.

---

# TRACK A: MVEM (no GPU, do FIRST; it is pure code and unblocks nothing else)

**Problem.** `NOMINAL_MAF_IDLE = 2.50` g/s @850 rpm; the real car measures **3.493 g/s @709 rpm**
(+40%, worse normalised). `identify.maf_belief_ratio()` returns **1.397** on that log, a confident
*"MAF believed +39.7% off"* verdict on a car whose total fuel trim is **+0.31%**. The layer would
invent a MAF fault on a healthy engine. That term is the only thing separating a MAF fault from an
injector-flow fault.

**A1. Guard.** `car/ecutune/algorithms/identify.py`: when the nominal baseline is
sim-derived/unvalidated, the estimator must **refuse** to return a confident MAF verdict (use the
existing refusal machinery: `identifiable=False` + `reason`, same shape as *not identifiable* and
*no single fault fits*). It must NOT silently downweight; a refusal is visible, a downweight is not.

**A2. rpm-dependent nominal.** `car/ecutune/simulation/mvem.py`: replace the scalar with an
rpm-indexed lookup the three-hold capture can populate directly. Keep 2.50@850 as the seeded value
but mark it **unvalidated**, which is what A1 keys off. Preserve `PROBE_POINTS` semantics;
`FAST_AIR_SCALE`/`LOW_VOLTAGE` are canonical and load-bearing for identifiability.

**A3. Verify.** New tests: (a) the real-log values produce a **refusal**, not a MAF verdict;
(b) with a validated baseline the estimator still identifies MAF faults correctly (no regression in
capability); (c) full suite green, `cd car && .venv/bin/python -m pytest tests/ -q`
(**91 passing** at handoff; that is the number to beat or match).

**Do NOT** hardcode 3.49. One log, one operating point, a poorly-idling car, rpm mismatch.

---

# TRACK B: 3.6 doc-collapse re-check (free, no GPU, ~15 min)

Only **4 distinct documents** were returned across all 70 E1 cases for 3.8; two on 100% of queries.
**Does 3.6's ratified `base+RAG@3` headline show the same collapse?**

Archived result files in `ml/eval/results/` carry `retrieved_doc_ids` per row. Count distinct docs
and per-query frequency for the 3.6 arm-B runs (July 2026 files), exactly as was done for 3.8.

**If 3.6 collapsed too, its ratification was measuring the base model with constant noise attached
- write that up prominently; it undermines a ratified decision.** If 3.6 retrieved diversely and
3.8 doesn't, something changed in the index/query path and that is a separate bug worth chasing.

---

# TRACK C: Judge pipeline (GPU; the long pole). DECISION TREE.

### C1. Calibrate 3.8: **harness already written and wired**
`ml/curation/judge/recalibrate.py` (new, committed). Scores the calibration docs **in memory**
through the real judging path and passes them to `calibrate.agreement()` via its existing
`judged_scores` parameter. **No DB mutation**: that is deliberate; `judge.cli --run` skips
already-judged docs, and mutating the corpus to run a measurement was the wrong answer.

**Verified so far:** imports clean, 100 adjudicated labels found, prompt pack loads, bars logic
correct (1 dangerous ⇒ FAIL). **NOT yet smoke-tested against the live LLM, do that first:**

```bash
cd ml/curation && .venv/bin/python -m judge.recalibrate --model-tag qwen3.8-27b-q8_0 \
    --limit 3 --out /tmp/recal_smoke.json
```
Expect per-doc `doc N -> score`. If it errors, fix before the full run. Then all 100:
```bash
.venv/bin/python -m judge.recalibrate --model-tag qwen3.8-27b-q8_0 \
    --out ml/eval/results/recal-qwen3.8-$(date +%Y%m%d).json
```

**GATE, pre-registered bars (2026-07-05, measured on 3.6). All three must be met:**
`keep/drop ≥ 93.1%` · `within ±1 ≥ 97.7%` · **`dangerous == 0`**

- **PASS** → 3.8 becomes the judge. Set `model: qwen3.8-27b-q8_0` in `ml/curation/config.yaml`.
  Record the numbers in `decisions.md` as the basis. Proceed to C2.
- **FAIL** → **keep 3.6.** Do not swap. Proceed to C2 *with 3.6*. A failed swap is a real result,
  not a blocked run, write it up and continue.
- **Borderline** (e.g. beats on agreement, 1 dangerous) → **treat as FAIL.** `dangerous` is the bar
  that protects the corpus; do not negotiate it. Note it for Syed.

### C2. Judge the 310 pending community docs
With whichever judge won C1:
```bash
cd ml/curation && .venv/bin/python -m judge.cli --run
```
310 pending: `forum_romraider` 122, `forum_legacygt` 114, `forum_msextra` 72,
`forum_subaruforester` 2. **This DOES write to the corpus, re-back-up first.** Long; background it
with a notifying wait. Check progress with `--status`.

### C3. Analyse the yield: a real decision, not a formality
Compute the new score distribution. Prior state (already-judged community): **19 × score-4,
95 × score-3, 213 × score-2**, 310 unjudged.

Judge the result honestly: **if the 310 yield very few ≥4, say so plainly.** The premise of this
work is that forum threads hold diagnostic content the reference corpus lacks (they contain 4× more
vacuum-leak and 2.5× more smoke-test mentions). If the judge disagrees at scale, that premise is
weaker than assumed and Syed needs to hear it, not a spun number.

### C4. Review the score-3 docs: **your judgement, written up, then STOP**
Syed's ruling: keep the **≥4 bar unchanged**; recover value from the 3s by review rather than by
moving the bar. Review **all** score-3 community docs (95 existing + any new from C2).

For each, recommend **keep / drop** with a one-line reason, judged on **retrieval usefulness**, not
prose quality. A post reading *"same thing happened to me, smoke test found a torn intake boot"*
may score 3 on substance while being exactly what a vacuum-leak query needs.

**Be honest about the limit** (recorded in the checklist §B6): *a text judge cannot know whether a
fix actually worked.* You can assess markers of verifiability, outcome reported, causal chain
present, numbers with units and conditions, thread resolved, corroboration, **not correctness**.
Say which you are assessing.

Write to `ml/curation/docs/community-3s-review-<date>.md`: doc id, source, title, one-line content
summary, recommendation, reason. **Then STOP. Do not index anything.**

---

# TRACK D: Community index machinery (build INERT, do not populate)

Per ruling 3: a **separate** community index queried alongside the reference one, results **tagged
by tier** so retrieval can weight/cap them and the citation guard can still tell a forum post from
a textbook.

Mirror the existing pattern: `ml/eval/harness/retrieval.py` (`ref_fts`, `ref_dense_v2.npz`,
`n_rows` staleness stamp, A10, 2026-08-02, exists because a stale index silently starved the dense
ranker for a whole showdown; **carry that stamp forward**).

**Build the code path and leave it switched off.** Nothing indexed, no default behaviour change.
Add tests proving: (a) with the community index absent, retrieval is byte-identical to today;
(b) tier tagging survives to the result rows.

**Also worth fixing here (idea, not a commitment. Syed's framing):** both E2 gate failures had
**4–6 adjacent chunks of ONE book** filling top-k. A per-source cap (max ~2 chunks/document) would
have prevented both. Retrieval-side only, no model or guard implications.

---

# WHAT YOU CANNOT DO TONIGHT

**The verification re-run Syed asked for is BLOCKED by his own insertion gate.** The test of
"did the RAG work actually help" is re-running **E1v2 arm B** (147 cases, ~2 h) *after* new content
is indexed. Since nothing gets indexed tonight, that re-run has nothing to measure. **Do not run it
- it would just reproduce 95.2%/7-dangerous and waste GPU hours.** Queue it for after his sign-off.

Note for when it runs: **arm A is final at 95.2%** (it uses no retrieval, so corpus changes cannot
move it). Only **arm B** is worth re-running, and arm A is the control that proves the model didn't
change underneath you.

---

# MORNING REPORT: write this before you finish

`sessions/handoffs/`: one file, covering:
1. **Calibration verdict** with the actual numbers and whether the judge was swapped.
2. **Yield from the 310**: score distribution, honestly characterised.
3. **The 3s review**: counts and the recommendation file path.
4. **MVEM**: what changed, what the tests prove, test count before/after.
5. **3.6 doc-collapse**: collapsed or not, and what it implies for the ratified decision.
6. **Anything you decided that Syed might disagree with**, flagged explicitly so he can reverse it.
7. Update `docs/OPEN-CHECKLIST.md` and commit everything with descriptive messages.

**Two decisions remain HIS, do not make them:** whether 3.8 displaces 3.6 as the working model
(E4 says yes, E1v2 says no), and whether to retrain QLoRA on 3.8.

---

# CONTEXT YOU NEED THAT ISN'T OBVIOUS

- **Syed corrected the previous agent four times and was right every time**: a premature judge
  swap, calling the ROM read "not on the critical path", preserving a stale inference engine for
  comparability, and a watcher that didn't notify. **Take his pushback seriously. Do not defend a
  position because you already stated it.**
- **D18: performance beats comparability** when they conflict. Disclose confounds; don't preserve
  stale configs to protect a historical number.
- **D19: the deterministic layer needs VE + timing axes**, MVEM is fuel-only. VE correction is
  *measured*, never simulated; knock is never simulated; **timing is a retreat mechanism, not an
  optimiser** (the layer may remove timing autonomously, adding it needs human review).
- **The evals are sim-bound and the sim is now known to be 40% off on the one constant validated
  against real data.** Chasing eval scores has unproven transfer. Syed asked directly whether the
  RAG fixes were "benchmark maxxing", the honest answer was *partly yes*. Keep that honesty.
