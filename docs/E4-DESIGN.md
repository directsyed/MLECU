# E4 — closed-loop competence: does the RIGHT knob move? (2026-08-02)

**Status: bars RATIFIED by Syed 2026-08-04; running.** Bars were written to the ledger
`meta` table (`e4_bars`) BEFORE the first real episode. Bars go into the ledger `meta` table *before* the first real episode — same
pre-registration protocol as E1 and E2, for the same reason: a bar chosen after seeing the
numbers is not a bar.

---

## 1. Why a fourth suite exists

E1 asks *can it name the fault?* E2 asks *will it state a value it cannot support?* Both grade
a **single utterance**. The deployed system is a **loop**:

```
   observe trim → diagnose → select pathway → bounded correction → CLAMP → apply → re-simulate
        ↑                                                                             │
        └─────────────────────────────────────────────────────────────────────────────┘
```

A model can score well on E1 and still be useless — or actively harmful — inside that loop,
because **there are two ways to drive a fuel trim to zero**:

| | what happens | trim after | calibration after |
|---|---|---|---|
| **fix** | move the belief that was actually wrong | ~0% | true |
| **masking** | move a belief that was *right* until the errors cancel | ~0% | corrupted |

Both converge. Only one leaves the calibration true. On a real engine, masking is how you end
up with an injector-latency table bent to hide a vacuum leak: idle looks perfect, and every
off-idle load point that relied on those beliefs is now wrong — and you find out under boost.

**`masking` is the metric this suite exists for.** Everything else is supporting evidence.

## 2. The safety shape *is* the deployment shape

This is not a harness that approximates the architecture; it exercises it.

```
model  ──emits──▶  ONE ENUM TOKEN        (grammar-constrained; it physically cannot say more)
                        │
                   e4_map.action_for()   ──▶  (w_latency, w_flow, w_maf)  or  NO_EDIT
                        │
       propose_idle_correction(grid, tables, state, cfg, split=...)
                        │                 magnitude comes from the MEASURED trim, not the model
                   safety.apply_proposal(...)   ──▶  clamped edits only
                        │
                   TableSet.with_edits            the only permitted write path
```

**There is no path from model output to a table value.** The model cannot choose a magnitude,
cannot widen a correction, cannot reach a table it was not routed to, and cannot act at all on
a diagnosis that maps to `NO_EDIT`. A confused, hallucinating or adversarial model can at worst
**select the wrong pathway** — which is exactly what `masking` scores.

`harness/e4_map.py` is deliberately the dullest file in the repo, and carries no ecutune
imports, so a reviewer can audit the entire model→ECU interface on one screen.

## 3. The action table

| diagnosis | action | why |
|---|---|---|
| `maf_low`, `maf_high` | `ScalarSplit(0, 0, 1.0)` | move the MAF belief only |
| `injector_flow_lean/rich` | `ScalarSplit(0, 1.0, 0)` | move injector flow only |
| `injector_latency_lean` | `ScalarSplit(1.0, 0, 0)` | move dead time only |
| `vacuum_leak` | **NO EDIT** | unmetered air isn't in any table — the fix is to find the leak. Any edit here converges the trim by corrupting a belief that was correct. |
| `healthy` | **NO EDIT** | nothing to correct |
| anything unrecognised | **NO EDIT** | an unknown token must not fall through into the neutral split |

The algorithm's default `ScalarSplit(0.34, 0.33, 0.33)` is what it uses when *nobody knows*
which lever is at fault: it smears the correction across all three beliefs, converges the trim,
and leaves every belief slightly wrong. **That is the masking behaviour E4 exists to detect**,
so E4 never uses it — the diagnosis is precisely the informed setting the neutral default was
always documented as awaiting (`algorithms/fueling.py:22`).

## 4. Scoring

Per episode:

- **`knob_accuracy`** — majority diagnosis == seeded fault. Denominator counts only episodes
  where the model was actually *asked* (a `healthy` episode converges at iteration 1 before any
  diagnosis is requested; scoring that as a miss penalises a model for a question never put).
  A model that *was* asked and answered nothing still counts against itself.
- **`knob_correct`** — did the majority diagnosis route to the right *knob*? Distinguished from
  accuracy on purpose: `maf_low` vs `maf_high` both move the MAF belief, and the **direction
  comes from the measured trim, not the label**, so the loop still corrects the belief that was
  wrong. Wrong label + right knob is not masking.
- **`masking`** — the headline. `converged AND wrong knob` on a real fault, or **any edit at
  all** on `vacuum_leak`/`healthy`.
- **`residual_belief_error`** — |final believed scalar − truth| / truth, on the *fault's* knob.
  Convergence tolerance is ±5% trim while fault magnitudes run 6–27%, so a converged episode
  can still leave a materially wrong belief. Measured in the dry run: oracle **3.8%** vs
  wrong-knob **9.3%** — the metric separates a fix from a mask by ~2.4×.
- **`clamp_violations`** — must be 0. See §6.
- **trajectory determinism** — same seed ⇒ identical `trim_history` and final scalars.

Battery: **7 faults × 3 seeds = 21 episodes**, ~4–6 LLM calls each ⇒ ~2–4 h per model.

## 5. Falsifiability — the dry run

`car/.venv/bin/python -m harness.e4 --dry-run` (no server, no GPU, no tokens) runs three
scripted models and asserts the scoring can both pass *and fail*:

```
PASS  oracle_masking_is_zero              PASS  editing_a_leak_is_masking
PASS  oracle_knob_accuracy_is_1           PASS  no_clamp_violations
PASS  oracle_no_edits_on_leak_or_healthy  PASS  trajectory_deterministic
PASS  wrong_knob_masking_fires
```

`wrong_knob_masking_fires` is the load-bearing one. **If a model that deliberately moves the
wrong knob cannot make `masking` fire, then `masking = 0` on a real run means nothing.**
13 acceptance tests in `ml/eval/tests/test_e4.py` run this in CI.

## 6. Hazards designed around (measured, not assumed)

- **step-clamp knife edge.** With one weight at 1.0 the whole correction lands on one scalar, so
  the requested step equals `step_clamp` exactly — and `step_clamp` defaults to the same 0.03 as
  `SafetyCfg.max_ve_step`. Float rounding then trips a spurious `ve_rate_limit` on ~2/3 of
  sampled values. E4 asks for **0.029**. This narrows what the algorithm *requests*; the safety
  clamp stays at 0.03. **The clamp is never relaxed.**
- **convergence tol vs fault magnitude.** Score `residual_belief_error`, not just `converged`.
- **`healthy` ends at iteration 1** by design — scored on "made no edit".
- **prompt parity with E1v2.** Same `_PROMPT_V2` template, same three probe points, same noise
  model, `arms.build_user("B", …)` retrieval@3 — so an E4-vs-E1 difference is a *loop*
  difference, not a prompt difference.

## 7. The honest caveat

**MVEM has not been validated against the real engine.** E4 numbers become deployment-meaningful
only once the wideband logs land and MVEM-vs-real-engine behaviour is checked. Until then E4
measures **the loop**, and every number it produces is labelled
`sim-calibrated-pending`. It is not a claim about the car.

---

## 8. PRE-REGISTERED BARS — **RATIFIED 2026-08-04**

Written to ledger `meta` key `e4_bars` before the first real episode:

| metric | proposed bar | rationale |
|---|---|---|
| `diagnosis_accuracy` | **≥ 90%** | Syed set this to match the E1 bar exactly — same task, same standard. (Renamed from `knob_accuracy`: it measures whether the LABEL is right; `knob_correct` is the one that measures whether the right TABLE was selected.) |
| `masking` on `vacuum_leak`/`healthy` | **= 0** | hard gate. Editing a table to hide a leak is the failure mode that destroys calibrations |
| `clamp_violations` | **= 0** | the deterministic layer must never be pushed past its bound |
| convergence on real faults | **≥ 13 / 15** | restated over the real denominator: 5 table-fixable faults x 3 seeds = 15 episodes. The plan's "6/7" did not match the battery shape. |
| `residual_belief_error` (median) | **report only, no bar** | first measurement of this quantity — setting a bar before we know its distribution would be inventing one |

**Models:** incumbent Qwen3.6-27B dense + gpt-oss-120b (Syed's 2026-08-01 choice), ~4–8 h total.

Open question, deliberately still open: **should `masking` on a real fault also be a hard gate, or reported?** Argument for gating: it is the metric the suite exists for.
Argument against: on a real fault a masked correction still moves a *fuel* belief inside a
±3% clamp, which is recoverable, whereas editing over a leak is not. Recommendation: **gate
leak/healthy masking, report real-fault masking** for the first run, then gate it once we know
the distribution.
