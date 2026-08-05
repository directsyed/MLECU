# Multi-point capture protocol — what the deterministic layer needs from a real log

**Status: written 2026-08-05, ahead of the wideband. Not yet executed on the car.**

## Why three pulls and not one

At a single operating point the observable is scalar and the state is three-dimensional:

```
trim = f( injector_latency , injector_flow , maf_transfer )     # 1 equation, 3 unknowns
```

Any one of the three can be moved to null the trim, so **one steady-state pull cannot tell you
which belief is wrong** — it can only tell you that *something* is. That is not a modelling
limitation, it is arithmetic, and it is why the closed loop was able to bend the wrong table in
the 2026-08-04 E4 run while the trim went obediently to zero.

Three pulls make the system identifiable, because each fault has a different *shape* across
conditions:

| fault | at ~2× airflow | at ~12 V |
|---|---|---|
| **injector flow** belief wrong | flat | flat |
| **injector latency** belief wrong | shrinks | **grows** |
| **vacuum leak** | **halves** | flat |
| **MAF transfer** belief wrong | flat — *and the logged MAF itself is off vs nominal* |

Latency and leak both shrink with airflow. **Voltage is the only thing that separates them** —
dead time is voltage-dependent, unmetered air is not. Drop the low-voltage pull and those two
collapse into each other; there is a test asserting exactly that
(`car/tests/test_identify.py::test_leak_and_latency_are_degenerate_WITHOUT_the_voltage_probe`).

## Before any of this — Stage 0

**Smoke/leak test first. Non-negotiable, and already project doctrine.** A leak poisons every
log, and no tune fixes a leak. The estimator can *detect* one (and will refuse to edit anything
when it does), but detecting it after a logging session is wasted effort — find it first.

Also settle before logging: engine at full operating temperature, closed-loop confirmed (not in
open-loop warmup enrichment), no active knock, no pending codes that force a limp strategy.

## The three pulls

Each is a **steady-state hold**, not a sweep. Target ≥20 usable samples per condition
(`GridSpec.min_samples = 20`), which at RomRaider's typical rate is a few seconds of genuinely
steady data — budget 30–60 s per pull to have margin after the transient filter discards
samples.

| # | condition | how | separates |
|---|---|---|---|
| 1 | **warm idle** | ~850 rpm, charging ~14 V, minimal electrical load | the baseline everything else is compared against |
| 2 | **fast idle** | ~1500 rpm (~2× airflow), charging ~14 V | **leak** (trim halves) from **flow/MAF** (trim flat) |
| 3 | **loaded idle** | ~850 rpm, heavy electrical load → ~12 V | **latency** (trim grows) from **leak** (trim flat) |

### Holding ~1500 rpm on a drive-by-wire car

The FXT is DBW (factory, from 2004 — cable-throttle notes elsewhere are wrong), so there is no
throttle cable to prop. In park/neutral, hold the pedal lightly for a stable ~1500 rpm. It does
not need to be exactly 1500 — it needs to be **steady** and **logged**, because the estimator
uses the *measured* airflow ratio, not an assumed one. A rock-steady 1400 is far more useful
than a wandering 1500.

### Getting the electrical load down to ~12 V

Headlights on high beam, blower on max, rear defroster, heated seats — everything at once, engine
idling. The point is to sag the charging system enough to move injector dead time measurably.
**Log `battery_v`** and use what it actually reads; 12.4 V that is *recorded* is fine, 12.0 V
that is *assumed* is useless. Do not disconnect the alternator or the battery to force this.

## Channels to log

All are already canonical roles in `car/ecutune/logparse/schema.py`, so the existing header
mapper will pick them up from a normal RomRaider export:

**Required:** `rpm`, `maf_gs`, `af_correction`, `af_learning`, `wideband_afr`, **`battery_v`**,
`tps`, `coolant`, `knock_retard`

`battery_v` is the one most likely to be left out of a logger profile by habit — **without it
pull 3 is worthless**, because it is the only channel that distinguishes a latency error from a
vacuum leak.

**Useful, not required:** `injector_duty`, `timing_total`, `iat`, `fine_knock_learn`.

## Steady-state criteria

The binner drops transient samples automatically (wall-wetting and accel enrichment poison fuel
readings). Defaults in `GridSpec`:

- `steady_rpm_tol = 100.0` — |Δrpm/sample| above this is transient
- `steady_tps_tol = 2.0` — |Δtps/sample| above this is transient
- `min_samples = 20` per cell before the cell is trusted at all

If a pull comes back low-confidence, the fix is a longer, calmer hold — not lowering the
threshold.

## One caveat specific to THIS engine

The healthy-baseline MAF figure (`NOMINAL_MAF_IDLE`, currently **2.50 g/s** in
`simulation/mvem.py`) is a *sim* value. This car has **TGVs deleted** and **exhaust AVCS
deleted**, both of which change idle airflow and stability in ways the stock calibration does not
expect. The baseline must be **established empirically on this engine** once it is known-healthy,
not inherited from the stock calibration or from the simulation.

Until that is done, the estimator's MAF-vs-nominal term — the one that separates a MAF error from
an injector-flow error — is calibrated against a number that has never been measured on this
car. Treat MAF verdicts as provisional until it is.

## What the layer does with these

`ecutune.simulation.harness.collect_observations` runs exactly this protocol in simulation and
produces the `Observation` list that `ecutune.algorithms.identify.identify()` consumes. The
real-car path is the same function fed by `logparse.parse_romraider_csv` instead of the synthetic
generator — that equivalence is the whole point of the log-replay design.

The layer then reaches its **own** verdict and `clamp_diagnosis_agreement` requires the model's
diagnosis to agree with it before anything is written. Disagreement produces a disagreement
report showing both sides, and **nothing is written**.

## Honest limits

- MVEM is `sim-calibrated-pending`. Until these logs exist and are compared against it, the
  estimator is exactly as right as the model, and both sides of the cross-check are sim-bound.
- The protocol assumes a **single** fault. Two simultaneous faults are *detected* (no single
  hypothesis fits) and escalated rather than diagnosed — which is the correct behaviour, but it
  means a car with a leak *and* a bad injector will get "escalate", not an answer.
