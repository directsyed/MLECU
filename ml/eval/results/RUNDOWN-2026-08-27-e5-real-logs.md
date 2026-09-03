# E5: blind diagnosis from real car logs (Qwen3.6-27B-Q8_0)

*Claude review pass, per the HARD RULE in `ml/CLAUDE.md`. 2026-08-27.*

**The first time this project has put real engine data in front of the local model.** Every prior
LLM call, E1, E2, E4, was built from the MVEM simulator. The bridge was named in two places
(`ml/eval/harness/e4.py:383`, `car/ecutune/cli.py:131`) and built in neither; it now exists as
`ml/eval/harness/e5_real_logs.py`.

## Setup

Six vacuum drives, 35,744 rows, 30,795 steady closed-loop samples. Ground truth established
independently by hand *and* by the deterministic stage: the **MAF transfer curve under-reports
airflow progressively above ~10 g/s**. The model was told nothing about it. Prompts were built
only from log-derived numbers; `ANALYSIS-2026-08-26-vacuum-drives.md` and decisions.md D22–D25
were used for scoring and never shown.

2 arms × 2 input treatments, temperature 0, **n=1 per cell**: suggestive, not established.

## Results

| input | arm | answer | correct? |
|---|---|---|---|
| summary tables | forced choice | `injector_flow_lean` | ✗ |
| summary tables | open-ended | injector flow scaling | ✗ |
| raw rows | forced choice | `injector_flow_lean` | ✗ |
| **raw rows** | **open-ended** | **MAF scaling curve** | **✓** |

**1 of 4.** No arm chose `vacuum_leak`: the confound we genuinely cannot rule out from
logs. The three failures went to a third hypothesis that the data actively refutes.

## The discriminator, and who used it

An injector-flow error is a **constant percentage** by definition: if the injectors flow 25% less
than believed, the ECU under-delivers 25% at *every* airflow, idle included. Our data:

| airflow | trim |
|---|---|
| <10 g/s | **+0.62%** (n=18,769) |
| ≥20 g/s | **+29.94%** (n=2,483) |

A 29-point spread rules out any fixed hardware parameter, from the data alone, before even
reaching the build sheet, which records the injectors as the OEM 2005 FXT ~500 cc/min units
**matched to this ROM**.

**The winning arm used exactly that argument, unprompted:**

> "A wrong injector flow rate or low fuel pressure would typically cause a relatively *constant*
> percentage trim error across the map. The fact that trim is near zero at idle/low load and
> spikes at higher load strongly isolates the error to the **MAF scaling curve or load-indexed
> base fuel table**, not a fixed hardware parameter."

**The losing open-ended arm saw the same contradiction and rationalised it away**, inventing a
mechanism to protect its hypothesis:

> "**Idle Masking:** At low airflow (0–5 g/s), trim is near 0%. This is typical because the
> absolute fuel deficit is small enough to fall within the ECU's minimum pulse width or idle fuel
> strategy deadband."

and dismissed the right answer on a generic prior rather than on the evidence in front of it:

> "*(Note: A mis-scaled MAF transfer function could produce a similar pattern, but MAF tables are
> typically sensor-part-number specific rather than displacement-specific. Injector flow rate is
> the far more likely calibration mismatch in a same-family displacement swap.)*"

Both wrong arms reported **85–90% confidence**.

## The finding that matters most

**Input format flipped the diagnosis.** Same model, same temperature, same underlying data, the
pre-digested summary tables produced the wrong answer, the raw rows produced the right one.

That is the opposite of the intuition a pipeline is built on. Aggregating evidence for the model
looks like help; here it appears to have encoded a framing. My summary led with trim-vs-airflow
but also carried trim-vs-load and trim-vs-rpm tables (all three correlate, because load and rpm
are confounded with airflow on this car), and the model given that view reasoned in terms of
"displacement swap → injector size," a strong real-world prior. Given raw rows it aggregated for
itself and found the shape.

If this holds up under repetition it is a design constraint on the diagnosis stage, not a
curiosity: **the summarisation step is not neutral.**

## Where this leaves the model in the pipeline

The architecture already anticipated this. The LLM's role is to *point*, and
`clamp_diagnosis_agreement` requires the deterministic layer's own `identify()` to name the same
table before any edit survives. Had this run driven a real proposal, three of four arms would have
been **stopped by that clamp**: they name `fuel.injector_flow`, the layer names
`sensor.maf_transfer`, the proposal aborts. The safety architecture did its job in advance.

Worth crediting: the model's *experimental design* was sound even when its diagnosis was not.
The wrong arm proposed logging injector pulse width against airflow and correctly noted that this
separates "MAF reads low" from "injector parameter wrong." The right arm proposed logging raw MAF
voltage against calculated g/s. Both are genuinely the right next measurement.

## Honest limits

- **n=1 per cell.** The input-format effect is one observation, not a measurement. Repeats at
  varied seeds are the obvious follow-up.
- The forced-choice enum (`FAULT_IDS`) was built for idle three-hold cases with seeded magnitudes
  of 0.86–0.94; ours is ≈0.74, outside anything the model has seen in this taxonomy.
- Qwen3.6 was used because every ratified number in this project is on it. Qwen3.8 is a legitimate
  second arm and has not been run here.
- Per `ml/CLAUDE.md` and the safety architecture, none of the model's numbers reached a ROM. The
  flashable candidate was produced entirely by the deterministic stage under the clamps.
