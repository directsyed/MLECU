# Idle-log parameter profile — what to select in RomRaider, and why

Companion to `CAPTURE-PROTOCOL.md` (which defines the *three pulls*). This file defines the
*channels*. Derived 2026-08-12 from the authoritative logger definition in the corpus
(`ml/data-pipeline/data/raw/SubaruDefs/RomRaider/logger/standard/logger.xml`) — **95 standard
parameters, 68 switches, 124 extended parameters.**

## ★ Finding 1 — this ECU gets ZERO extended parameters

RomRaider splits loggable channels in two:

- **Standard parameters** — fixed SSM2 addresses, **available on every SSM2 ECU**, no gating.
- **Extended parameters (`ecuparam`)** — RAM addresses that differ per calibration, so each is
  gated by an explicit list of ECU IDs.

`3B12504206` **is not in any of those lists.** All four of its siblings are:

| ECU ID | in logger def? | extended params |
|---|---|---|
| `3B12504006` | yes | — |
| `3B12504106` | yes | **57** |
| `3B12504306` | yes | — |
| `3B12584206` (MT twin) | yes | — |
| **`3B12504206` (this car)** | **NO** | **0** |

Same root cause as the ROM-defs gap in `car/ecu/defs/README.md`: one AT calibration revision was
never contributed to the community files. It costs us here too.

### What is lost, and why one of them hurts specifically

Among the 57 the nearest sibling gets: `CL/OL Fueling`, `Closed Loop Fueling Target`,
`Feedback Knock Correction`, `Knock Sum`, `IAM (4-byte)`, `Target Boost`, `Boost Error`,
`Fuel Injector #1 Latency`, `Fuel Injector #1 Pulse Width (4-byte)`, `Final Fueling Base`,
`Primary Open Loop Map Enrichment`, `Requested Torque`, `Turbo Dynamics` P and I terms.

**`CL/OL Fueling` is the problem.** `CAPTURE-PROTOCOL.md` requires closed loop to be *confirmed*
before logging, and that parameter is the direct confirmation — and it is exactly one we cannot
read. **Workaround: infer closed loop from `A/F Correction #1` actively moving.** In open-loop
warmup enrichment the correction sits frozen (typically 0.00); once closed loop engages it wanders
continuously. A frozen correction means the pull is invalid regardless of what else looks right.

`Fuel Injector #1 Latency` is also painful — latency is one of the three unknowns
`identify.py` fits — but the estimator recovers it from the three pulls rather than reading it, so
this is a cross-check we lose, not a capability.

### Can we just add our ECU ID to the definition?

**Tempting, and risky enough to refuse for now.** Extended params are *RAM addresses*, and RAM
layout is a property of the calibration. Adjacent revisions often share it — but "often" is not
"provably". Grafting sibling addresses onto this ECU would read **plausible-looking values from
possibly-wrong memory**, and plausible-but-wrong is the worst failure mode for a project whose
deterministic layer consumes these numbers to decide which table to move.

If it is ever attempted it must be **empirically validated** channel by channel (does `IAM` read
1.00 on a healthy engine? does `CL/OL Fueling` flip at the expected moment? does
`Fuel Injector #1 Pulse Width` agree with the standard `P21`?) — not assumed from adjacency.
**Do not do this before the ROM read is solved**, since the ROM is what would settle RAM layout.

## ★ Finding 2 — bandwidth is the real constraint

The SSM2 protocol block declares `baud="4800"`. That is **480 bytes/sec, total, shared by every
channel.** Each sample costs roughly `14 + 4.4 × (number of parameters)` bytes:

| params | approx. sample rate |
|---|---|
| 10 | ~8 Hz |
| 15 | ~6 Hz |
| **20** | **~4.7 Hz** |
| 25 | ~3.9 Hz |
| 30 | ~3.3 Hz |

Approximate — read the actual rate RomRaider displays and trust that. **Switches are cheap**
(bit-packed, several share one address byte); parameters are not.

"Log everything" is therefore self-defeating: all 95 standard params would land near ~1 Hz, and
`GridSpec.min_samples = 20` per cell would need pulls several minutes long, during which "steady
state" stops being true. **Target ~20 parameters.**

## The profile

### REQUIRED — the capture protocol cannot run without these (9)

| RomRaider parameter | canonical role | note |
|---|---|---|
| P8 Engine Speed | `rpm` | |
| P12 Mass Airflow | `maf_gs` | |
| P3 A/F Correction #1 | `af_correction` | **also the closed-loop indicator** — see Finding 1 |
| P4 A/F Learning #1 | `af_learning` | |
| P17 Battery Voltage | `battery_v` | **pull 3 is worthless without it** |
| P13 Throttle Opening Angle | `tps` | drives the transient filter |
| P2 Coolant Temperature | `coolant` | proves full operating temperature |
| P23 Knock Correction Advance | `knock_retard` | |
| **AEM UEGO AFR** — *External tab* | `wideband_afr` | not SSM2; costs no K-line bandwidth |

### STRONGLY RECOMMENDED (7)

| RomRaider parameter | role | why |
|---|---|---|
| P200 Engine Load (Calculated) `g/rev` | `load` | the axis the ROM indexes maps by — central to a 2.0 L running a 2.5 L calibration |
| P201 Injector Duty Cycle | `injector_duty` | |
| P10 Ignition Total Timing | `timing_total` | |
| P11 Intake Air Temperature | `iat` | air-density correction |
| P91 Fine Learning Knock Correction | `fine_knock_learn` | maps correctly only after the 2026-08-12 schema fix |
| P90 IAM | *(none)* | knock-learning health. Below 1.00 means the ECU has already learned knock — a red flag before any tuning |
| P58 A/F Sensor #1 (AFR) | *(none, deliberately)* | **the factory wideband** front sensor. Free second opinion against the AEM; the schema refuses to alias it to `wideband_afr` so the trusted instrument stays unambiguous |

### DIAGNOSTIC FOR THIS BUILD (4)

| RomRaider parameter | why |
|---|---|
| P25 Manifold Relative Pressure | idle vacuum — the most direct evidence for Stage 0's leak question |
| P48 Intake VVT Advance Angle Right | intake AVCS is live on this car and moves VE |
| P24 Atmospheric Pressure | normalises pulls taken on different days/weather |
| P7 Manifold Absolute Pressure | absolute reference alongside P25 |

### SWITCHES — near-free, take them (4)

| switch | why |
|---|---|
| S5 Idle Switch | confirms the ECU agrees it is at idle |
| S17 Electrical Load Signal | confirms **pull 3** is actually loading the system |
| S9 Air Conditioning Switch | AC cycling perturbs idle; lets you discard affected samples |
| S12 Front O2 Rich Signal | closed-loop activity corroboration |

**Total ≈ 20 parameters + 4 switches → roughly 4–5 Hz.**

## ⚠ Do NOT select these — they collide with required channels

Real v370 parameter names that map onto a role they have no business holding. The parser now
defensively ignores all of them (`schema.py::_IGNORE`, 2026-08-12), but selecting them still
wastes bandwidth:

| do not select | would have overwritten |
|---|---|
| Mass Airflow **Sensor Voltage** | `maf_gs` (volts over g/s) |
| Throttle **Sensor Voltage** | `tps` (volts over %) |
| Rear O2 **Heater Voltage** | `battery_v` |
| A/F **Adjustment Voltage** | `battery_v` |
| Differential Pressure **Sensor Voltage** | `battery_v` |
| Primary / Secondary **Wastegate Duty Cycle** | `injector_duty` — boost duty read as fuelling |

**One more, unresolved:** `P21 Fuel Injector #1 Pulse Width (ms)` and `P201 Injector Duty Cycle (%)`
both map to `injector_duty` with different units. **Select only one — P201.** A dedicated
`injector_pw` role would be a schema change; noted, not made.

## Duration and session shape

- **60 s of steady hold per pull.** At ~4.7 Hz that is ~280 raw samples against
  `GridSpec.min_samples = 20`, leaving generous margin after the transient filter discards
  samples. If the observed rate is below 3 Hz, either trim parameters or extend to 90 s.
- **Warm up fully first** — coolant at operating temperature *and* `A/F Correction #1` visibly
  moving. Neither alone is sufficient.
- **One file per pull**, named for the condition (`pull1-warm-idle.csv`, `pull2-fast-idle.csv`,
  `pull3-loaded-idle.csv`). Separate files keep each `Observation` unambiguous.
- Budget ~20–30 min for the session; the logging itself is only ~3 min of it.

**Before any of it:** Stage 0 smoke/leak test, and the ground-loop remedy from
`CAPTURE-PROTOCOL.md` (DB9 pin 5 omitted, signal wire only). Acceptance test before you start:
**ECU parameters and `wideband_afr` updating simultaneously.**
