# 2026-08-05 — DETERMINISTIC-LAYER HARDENING: the loop can disagree with the model now

**READ FIRST. Supersedes 2026-08-03-bench-integrity-execution.md.** The full plan
(`~/.claude/plans/create-a-plan-to-snazzy-shore.md`) was approved and executed. Parts 1–4 and 6
shipped; Part 5 was **rejected by its own acceptance test** and reverted.

## START HERE

1. **Nothing is running.** GPUs idle, driver inactive, ledger fully terminal.
2. **The incumbent now passes all four ratified E4 bars.** gpt-oss passes the two *safety* bars
   and fails the two *capability* bars.
3. **Four things want Syed's attention** — §5.

## §1 — What was actually wrong (and it was not the model)

At one operating point the observable is scalar and the state is 3-dimensional:
`trim = f(latency, flow, maf)`. Any of the three nulls the trim, so the LLM's diagnosis was not
advice — it was **the missing constraint that made the problem solvable**, and the layer had no
basis on which to disagree.

**The layer saw strictly less than the model.** The E1v2 prompt has always shown three probe
points; `propose_idle_correction` got **one number**. Fast-idle and low-voltage were computed for
the prompt and thrown away. `mvem.py` documented in its own comments exactly why those points
discriminate — the design was there, unused.

## §2 — What shipped

- **`car/ecutune/algorithms/identify.py`** — inverts MVEM. Per-hypothesis single-parameter fit
  via bounded golden-section, numpy only. Two new refusals: *not identifiable*, and *no single
  fault fits* → escalate.
- **`clamp_diagnosis_agreement`** (GATE, second in the pipeline) — the layer's own verdict must
  agree on WHICH TABLE moves, or the proposal aborts. Inert without an estimate; never
  manufactures a second opinion it does not have.
- **`safety/report.py`** — the disagreement report Syed asked for: the model's diagnosis, exact
  prompt, retrieved excerpts and doc ids, per-iteration history; AND the layer's full hypothesis
  ranking with residuals, fitted magnitude, margin, and the probe points it fitted. It shouts
  when the caller supplies no LLM context rather than letting a refusal look one-sided.
- **`clamp_belief_envelope`** (MODIFIER) — bounds each belief's DISTANCE from the stock ROM.
  `clamp_ve_rate_limit` was a *velocity* bound only; 12 iterations compounded to 43%.
- **Stability N=3**, per-knob integrator, escalate-and-exit, `collateral_beliefs_moved`, LLM
  provenance on `Proposal`.
- **`car/logging/CAPTURE-PROTOCOL.md`** — the three-pull real-car procedure.

## §3 — Results

**Estimator, no LLM and no GPU**, 7 faults × 20 seeds through the real log→bin path with noise:
**138 correct / 2 safe refusals / ZERO confidently wrong.** Replayed against all 8 real masking
events from 2026-08-04: **8/8 prevented.**

**E4 re-run against the SAME ratified bars:**

| bar | 27B before → after | gpt-oss before → after |
|---|---|---|
| diagnosis_accuracy ≥ 90% | 88.9% → **100% PASS** | 88.9% → 77.8% FAIL |
| masking leak/healthy = 0 | 2 → **0 PASS** | 2 → **0 PASS** |
| clamp violations = 0 | 0 pass | 0 pass |
| convergence ≥ 13/15 | 15/15 → 13/15 pass | 15/15 → 11/15 FAIL |
| collateral beliefs | 9 episodes → **0** | → **0** |

**THE FINDING WORTH KEEPING — the two defences catch different failures:**

```
27B     : blocked_by_stability = 52,  refused_by_crosscheck = 0
gpt-oss : blocked_by_stability = 54,  refused_by_crosscheck = 8
```

The 27B's errors are isolated **slips** — stability caught every one and the gate never fired.
gpt-oss **thrashes**: 8 of its edits were stable enough to survive N=3 and still wrong, so the
estimator had to veto them. Neither mechanism alone sufficed for gpt-oss. Invisible in the
headline scores.

## §4 — Four bugs found by running it, not reading it

1. Estimator baseline used OEM constants as "truth" → every hypothesis fitted a two-fault world.
2. **MAF and injector-flow errors are exactly degenerate in trim space** (scale `maf_b` by r,
   divide `flow_b` by r → identical pulse width). Only the *reported airflow* separates them;
   scoring trims alone gave 15/21.
3. The identifiability margin compared *hypotheses* rather than *actions*.
4. The gate cried `knob_mismatch` **even when both sides agreed**, because the proposer always
   emits three edits with unselected weights zeroed. Caught only because oracle convergence
   collapsed to 0/5 — which is precisely why the plan demanded re-measuring convergence.

## §5 — NEEDS SYED

1. **Convergence is exactly at the bar (13/15) with no headroom.** `STABILITY_N=2` would likely
   restore it for the 27B (counterfactual 4/4 at N=2) but gpt-oss demonstrably needs N=3, so a
   per-model N is a *serving* decision, not a measurement one.
2. **Belief-envelope percentages** in `SafetyCfg` (flow ±25%, latency ±30%, MAF ±20%) are
   starting points flagged in-code as his to ratify, not measurements.
3. **The E2 fabrication gate is still failed by every model** and the blind spot is now
   understood as a consequence of the guard's contract, not a defect. Two paths, both deferred:
   make the model return the supporting SENTENCE verbatim (deterministic, a schema change), or a
   semantic check (which makes the clamp only as trustworthy as a model).
4. **Qwen 3.8 27B** when it lands — seed-file edit, 6–8h battery. DeepSeek V4 Flash analysed and
   **not recommended**: it fits (162 GB UD-Q8_K_XL across 42 GB VRAM + RAM) but runs ~4–8 t/s
   against a 10 t/s floor, ~35h for one battery.

## §6 — Disclosed confound

In the E4 re-runs the estimator's probe pulls shared the loop's rng, so enabling the cross-check
advanced the noise stream and trim histories diverged for reasons unrelated to any fix. **Masking
2→0 and collateral 9→0 are large effects with identified mechanisms and are robust.** The
`diagnosis_accuracy` movements are **not** pure capability deltas. Fixed afterwards (separate
seed-derived stream), so future comparisons are clean; not re-run because it costs ~6h GPU and
changes no bar verdict.

## §7 — System state

- GPUs idle (1 MiB, locks intact), driver inactive, ledger terminal, ECC 0/0/0/0.
- Suites: **136 eval + 90 car green** (session start: 54 + 74).
- `llama-judge` still disabled from the pipeline — unchanged for several sessions now.
- `ml/eval/guard_retrotest.py` kept: the bar any future guard attempt must clear, and what
  stopped a plausible-sounding safety change from shipping.
