# 2026-08-02/03 — BENCH-INTEGRITY EXECUTION: instrumentation rebuilt, E2 gate pass reverses

**READ THIS FIRST on session start. Supersedes 2026-08-02-session-close-bench-complete.md.**
Syed gave the word to execute the held plan
([docs/PLAN-bench-integrity-e4-2026-08-01.md](../../docs/PLAN-bench-integrity-e4-2026-08-01.md)).
**Phases 1-5 are COMPLETE.** The 17-cell rerun finished; the rundown is at
[ml/eval/results/RUNDOWN-2026-08-03.md](../../ml/eval/results/RUNDOWN-2026-08-03.md).
The ONLY thing left in the plan is E4 execution, which is blocked on Syed ratifying its bars.

## START HERE (next agent, in order)

1. **Read the rundown** — `ml/eval/results/RUNDOWN-2026-08-03.md`. Headline: **NO MODEL PASSES
   BOTH PRE-REGISTERED BARS**, and the two finalists fail in OPPOSITE directions (27B: E1 92.5%
   PASS / E2 47ex-2dg FAIL; gpt-oss: E1 78.9% FAIL / E2 48ex-0dg PASS). E4 is the tiebreaker.
   Regenerate any time with `cd ml/eval && ../../car/.venv/bin/python rundown.py`.
2. **FOUR THINGS NEED SYED** — all pinned in `ml/eval/bench/PHASE-STATUS.md`:
   - **E4 pre-registered bars** ([docs/E4-DESIGN.md](../../docs/E4-DESIGN.md) §8). E4 is built
     and dry-run green; NO model runs against it until he signs.
   - **The E1 dangerous-flip ruling** — consequential, see §3 below.
   - **top_k mode-switching** (deferred from last session at his request; there is now data).
   - **Adjudicate the `unit_mismatch` rows** (see §4).
3. **Wideband/car data still outranks everything** if it lands in `car/dataset/*.csv` or
   `car/ecu/rom-archive/*.bin`. The driver's car-data preemption is ARMED again (it hard-pauses
   the queue and sets `paused=1` in ledger meta).

## §1 — What was wrong, and what it cost

The plan's premise held up and then some: **the benchmark was measuring the harness at least as
much as the models.** Reproduced on disk before anything was touched — FTS5's 24-TOKEN snippet
window splits `11.8%` into the tokens `11` and `8` and emitted
`… increases effective injector size by 11 … `. Three models were scored `dangerous_miss` — the
class that means "this model fabricates engine calibration values" — for faithfully quoting the
evidence we handed them.

Fixed, with measurements:

| fix | measured effect |
|---|---|
| unified char-window snippet extraction (never bisects a token or a number run) | evidence recall **29/69 → 59/69** (expected value present in its own source doc), zero regressions |
| A1 `[REF n]` parsed as the stated value | 21 historical rows `dangerous_miss → exact` |
| range-aware expected values + `range_mismatch` class | folded into the above, **+2 rows got STRICTER** |
| `unit_mismatch` class (450 mV vs "0.45 V", λ vs AFR) | 36 rows `dangerous_miss → unit_mismatch` |
| A2 empty completion scored as virtue | 65 rows `honest_decline → no_answer` |
| A7 `score()` had no completeness check | an EMPTY file used to return gate **"pass"** |
| A3/A4/A8/A9 guard fixes | guard no longer convicts on the retriever's miss, no longer grounds on titles, preserves `original_value`, no longer heals `10-15 psi` into `1015` |
| A10 stale dense index (5,608 vs 5,638 rows) | 30 chunks were invisible to the dense ranker for the whole showdown |
| **infix minus read as a SIGN** (found by writing the A9 test, in NEITHER audit) | `10-15 psi`→[10,**-15**], `(x-32768)`→[**-32768**]; models correctly quoting 15 or 32768 were BLOCKED |

Re-score of all 28 historical E2 files, published both ways: **exact 558 → 577, dangerous
265 → 201**, stricter in 2 rows. Detail: `ml/eval/results/rescore-v1-vs-v2-detail.tsv`.
LIMIT STATED: historical rows carry no `finish_reason`, so their empty completions cannot be
separated into truncated vs no_answer retroactively.

## §2 — THE HEADLINE: the 27B's E2 gate PASS reverses

Same configuration, old instrumentation vs new:

| 27B armB@3 + guard | old (v1) | new (fixed) |
|---|---|---|
| exact | 19 | **39** |
| dangerous | 0 | **3** |
| coverage | 27.5% | **62.3%** |
| precision | 1.000 | 0.907 |
| **gate** | **PASS** | **FAIL** |

**The old PASS was substantially an artifact of our own snippet bug.** The model declined 50/69
times because the evidence usually didn't contain the answer. Zero fabrications is easy when the
model almost never commits. With recall fixed it engages 2x as often, gets 2x as many right, and
3 fabrications leak.

All 3 leaks carry guard verdict `cited` — they are the guard's **explicitly named blind spot**
(documented in its docstring since it was built): *cannot catch a present-but-wrong-selection
number (right doc, wrong quantity)*. The guard works as designed; the design has a hole that only
became load-bearing once the evidence got good enough to use.

**k6 beats k3 on every axis** (46/2, precision 0.939, coverage 0.710) — unusual, since coverage
and precision normally trade. Mechanism visible in the failures: on `e2-5668-0` the probe's own
source doc wasn't in the top-3 at all. This weakens the k3-for-diagnosis/k6-for-values split on
the value-lookup side.

**E1 diagnosis is UNCHANGED**: 92.5% vs 93.2% historical = −0.7pp, exactly the measured noise
band, 0 blanks, 0 truncation. So the snippet bug hit **value lookup only, not diagnosis** — the
showdown's E1 verdicts, including the 27B's win on the deployed config, stand.

## §3 — The E1 dangerous-flip ruling (NEEDS SYED, and it is consequential)

The E1 `dangerous` count was reported all through the showdown but **computed ad hoc and never
committed**, so the historical figures are not reproducible from the artifacts. It is now
codified in `ml/eval/rundown.py` with a physics definition: each fault has a lean or rich
signature, and a flip across that boundary sends the correction **the wrong way**.

It reproduces Mistral exactly (30 arm A / 22 arm B@3) but disagrees on two cells **in both
directions**, and those two are mutually inconsistent under any single rule:

| cell | historical | codified | disputed case |
|---|---|---|---|
| 35B armB@3 | 3 | **0** | `injector_flow_rich`→`maf_high` ×3 |
| 27B armB@3 MTP-off | 0 | **1** | `injector_flow_rich`→`maf_low` ×1 |

**Why it matters now:** the fresh 27B re-verify cell contains `injector_flow_rich`→`maf_high` ×3.
Under the codified rule that cell scores **0 dangerous → PASS at 92.5%**. Under the historical
treatment of that same case it scores **3 → FAIL** the zero-veto bar. Same data, opposite verdict
on the working model.

**Recommendation: ratify the codified rule.** `injector_flow_rich` and `maf_high` both mean "we
are over-fuelling"; the correction moves the same direction. What differs is *which belief moves*
— and that is **masking**, which is E4's job. E1's veto exists to catch a wrong *direction*.
Conflating the two is most likely why the historical numbers came out incoherent. Ratifying this
RAISES the burden on E4 rather than lowering it: the failure mode doesn't vanish, it moves to the
suite that can see it.

## §4 — Probe file v2, and three audit claims that did not survive

Every disposition was decided against the **source text in ref_fts**, not the audit's summary.

- **No probe qualifies as `derived`.** The audit proposed excluding 8–9 probes from the
  fabrication hard gate. Checked against source: **0 of 69** probes have an expected value absent
  from their source document; all nine candidates state theirs verbatim. Excluding them would
  have softened a pre-committed safety gate on an unsupported premise. They stay gated, flagged
  `derivable_wording`.
- **`e2-500-1` was a PARSER bug, not a probe bug** (the infix minus above). Probe untouched.
- **`e2-5401-1` was never defective** — quote verbatim, question matches.
- Quote fidelity is sound: 18/69 quotes differ from source only by PDF artifacts
  (`injec - tion`, `particu late`).

**One genuine defect, and not the one the audit named:** `e2-3927-1`. Bosch gives pilot NOP
~180 bar and main NOP "at approximately 300 bar higher than pilot" — an awkward translation
reading two ways; the unit-pump design settles it (main = 300 absolute). v1 asked "by how many
bar higher", so a model that read the source correctly and answered 120 was scored
`dangerous_miss` **for being right**. Question rewritten to the absolute form, expected value
unchanged, `question_v1` preserved in the row.

v2 = 69 probes: 59 keep / 9 keep+flag / 1 fix-question / **0 drop**. Table:
`ml/eval/results/probe-v2-dispositions.md`. The probe file now has a CI calibration certificate
(`tests/test_probes_v2.py`): every probe answered with its own expected value must score `exact`,
and a wildly wrong answer must still trip the gate on every probe.

**PENDING ADJUDICATION:** `unit_mismatch` is gate-neutral and does NOT mean "correct". v2 flags
unit differences rather than converting them, so a genuinely wrong answer in another unit
(`30-40 psi` against `300 to 400 kPa`) lands there. Also `e2-5579-0` (expected `11.1:1` AFR,
model answered "equivalence ratio of 1.2") scored `dangerous_miss` only because "equivalence
ratio" is not in the units table. **I deliberately did NOT add it after seeing that row** —
changing the scorer in response to a specific failing case is the benchmark-maxxing pattern.
Syed's call.

## §5 — E4 built (Phase 5), bars await signature

`ml/eval/harness/e4.py` + `e4_map.py` + 13 tests. The composed loop: LLM diagnoses → deterministic
layer acts → MVEM re-simulates. Scores **masking** — converging the trim by moving a belief that
was RIGHT, which is how an injector-latency table ends up bent to hide a vacuum leak.

`e4_map.py` is the entire model→ECU interface, deliberately dull, no ecutune imports, one screen.
The model emits ONE enum token; the map yields three weights; the magnitude comes from the
MEASURED trim; `safety.apply_proposal` clamps it. **There is no path from model output to a table
value.** Unrecognised token → NO_EDIT, never the neutral split.

Fake-LLM dry run (no server, no GPU): **7/7**. The load-bearing check is
`wrong_knob_masking_fires` — if a deliberately wrong model can't make `masking` fire, then
`masking = 0` on a real run means nothing. Measured separation: oracle residual 3.8% vs
wrong-knob 9.3%.

`E4_STEP_CLAMP = 0.029` against the 0.03 safety bound: with one weight at 1.0 the request equals
the bound exactly and float rounding trips a spurious `ve_rate_limit` on ~2/3 of sampled values.
**This narrows what the algorithm ASKS for; the safety clamp is untouched and never relaxed.**

Labelled `sim-calibrated-pending` throughout — MVEM is not validated against the real engine, so
E4 measures the loop, not the car, until wideband logs land.

## §6 — Deviations logged (full reasoning in decisions.md D1–D9)

- **D1** multi-window snippets measured (63/69 at the same budget, 68/69 at 2400 chars) and
  **NOT adopted** — I would have been choosing it *because it scored better on the benchmark's
  own answers*. Available as a deliberate retrieval change with its own before/after.
- **D2** Phase 3 expanded 10 → 17 cells (~+4h): `finish_reason` didn't exist when the arm-A cells
  ran, so the A2 fix is unmeasurable on them without a rerun.
- **D8** index rebuilt on the **GPU**. The docstring's "~15-25 min" was never measured — 5,638
  chunks × ~2,700 chars ≈ 3.8M tokens through a 568M model is **~4 hours** on 28 Broadwell cores.
  Added `--device`; rebuilt on the idle Ti in 380 s. **CPU remains the default** so the
  safe-alongside-serving property is unchanged.

## §7 — System state

- Driver **enabled and running** (`systemctl --user is-active mlecu-bench`). Resumable ledger, so
  a reboot mid-run continues on its own.
- GPU locks verified (3090 810MHz/300W, Ti 1500/400, persistence on). 3090 held ~106W idle.
- Dense index **v2** at `ml/eval/data/ref_dense_v2.npz` (5,638 rows + freshness stamp). v1 kept on
  disk, STALE, for showdown reproducibility.
- `llama-judge` **still disabled from the pipeline** — unchanged from last session; ~300+ docs
  pending incl. the re-queued 5781. First sudo action when someone wants it:
  `sudo systemctl enable --now llama-judge`.
- Test suite **121 green** (was 54). Run with `car/.venv` — `ml/eval/.venv` lacks numpy and will
  show false failures.
- Timing: cells run 53–199 min (MTP-off + 16384-token budget make them 3–5× the showdown's).
  Plan's "14-16h" estimate did not account for MTP-off halving the 27B's throughput.


---

# ADDENDUM — run complete (2026-08-03 15:00)

## Final matrix (all five models, fixed instrumentation)

|  | armA | k3+guard | k6+guard | k6 precision | E2 gate | E1v2 armB@3 |
|---|---|---|---|---|---|---|
| **27B dense** | 9/9 | 40/3 | **47/2** | 0.940 | FAIL | **92.5% PASS** |
| **gpt-oss-120b** | 7/3 | 42/2 | **48/0** | **0.980** | **PASS** | 78.9% FAIL |
| 35B-A3B | 10/**14** | 41/3 | 47/3 | 0.922 | FAIL | 83.7%* |
| 80B-Thinking | 9/4 | 39/2 | 43/1 | 0.878 | FAIL | 72.8%* |
| Mistral Small 4 | 7/10 | 29/1 | 34/2 | 0.944 | FAIL | 44.9%* |

\* not re-run (finalists only, per Syed 2026-08-01)

## What the run added beyond the plan

- **H4 (new):** top_k 6 beats top_k 3 in **all five models on every axis** — coverage rises AND
  precision holds, which is unusual. The k3-for-values half of the serving config is unsupported.
- **H3 confirmed decisively:** closed-book is not weak, it is *dangerous* — 3-14 confident
  fabrications per model. Asking any of these to recall a calibration value invites an invented one.
- **Two more harness defects found mid-run** (U+202F thousands separators; engine codes like
  `EJ20` parsed as values) — both found by scrutinising the cell that PASSED, both even-handed in
  effect, neither changed a gate verdict. A **stopping rule** was then adopted: no further
  scorer/guard change during the run.
- **Guard fixes are retroactive.** The guard is post-hoc, `original_value` is preserved (A8), and
  retrieval is deterministic — so `rundown.reguarded()` re-derives them EXACTLY offline, asserting
  per row that re-retrieved doc ids match. Saved ~3.5h of re-runs.
- **Calibrated offload profiles are NOT invariant to retrieval changes.** The 35B k6 cell crashed
  the SERVER (CUDA OOM in `cudaGraphInstantiate`) three times because the snippet fix enlarged k6
  prompts past the profile's VRAM headroom. Fixed by pushing tail experts to CPU (NOT to the
  convicted 3090). That cell's t/s is flagged non-comparable. **Nothing in the pipeline checks
  for this** — worth a preflight assertion later.
- Driver now captures harness stdout to `bench-harness.log` (a failure with no evidence is not
  diagnosable); `ledger.requeue()` clears the previous attempt's completion fields.

## System state at close
- Driver **drained and stopped**; all 17 units `done`. GPUs idle (1 MiB, ~100W).
- Test suite **129 green** (was 54 at session start). Run under `car/.venv`.
- Deferred to v3 (documented, NOT patched — stopping rule): a trailing period after spaced
  thousands (`"...is 30 000."`) defeats the thousands-join. **Measured: 0 of 690 rows affected**,
  so no verdict in this run depends on it.
