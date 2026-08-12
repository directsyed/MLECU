# Idle-log parameter profile — what to select in RomRaider, and why

Companion to `CAPTURE-PROTOCOL.md` (which defines the *three holds*). This file defines the
*channels*. Derived 2026-08-12 from the authoritative logger definition in the corpus
(`ml/data-pipeline/data/raw/SubaruDefs/RomRaider/logger/standard/logger.xml`) — **95 standard
parameters, 68 switches, 124 extended parameters.**

## ★ Finding 1 — this ECU gets ZERO extended parameters

RomRaider splits loggable channels in two:

- **Standard parameters** — fixed SSM2 addresses, but **gated by the ECU's own capability
  bitmap**: 91 of the 95 carry an `ecubyteindex`/`ecubit` pair, and RomRaider hides any parameter
  whose bit the ECU does not advertise during SSM2 init. *(Corrected 2026-08-12 — an earlier
  version of this file wrongly said standard params were available on every SSM2 ECU with no
  gating. **What RomRaider lists is what this ECU actually supports**; treat the tables below as
  "select if present.")*
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
continuously. A frozen correction means the hold is invalid regardless of what else looks right.

`Fuel Injector #1 Latency` is also painful — latency is one of the three unknowns
`identify.py` fits — but the estimator recovers it from the three holds rather than reading it, so
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

## ★ Finding 2 — bandwidth: MEASURED, and far better than modelled

**Superseded by real data 2026-08-11.** An earlier version of this file modelled SSM2 throughput as
`14 + 4.4 x params` bytes per sample against the protocol's declared `baud="4800"`, predicting
**~4.7 Hz for 20 parameters**.

**The first real log measured 14.49 Hz with 21 parameters + 3 switches** — roughly **3x** the
prediction. The model was wrong because it assumed a request/response round trip per sample. SSM2
supports a **continuous read** mode in which the address list is sent once and the ECU streams
responses, which removes the per-sample request overhead entirely.

**Use measurement, not the model.** ~14.5 Hz at 21 parameters is the observed baseline on this car.
Bandwidth is real but far less binding than feared: a 60 s hold yields ~870 samples against
`GridSpec.min_samples = 20`. There is headroom to add channels if a future question needs them.

## The profile

### REQUIRED — the capture protocol cannot run without these (9)

| RomRaider parameter | canonical role | note |
|---|---|---|
| P8 Engine Speed | `rpm` | |
| P12 Mass Airflow | `maf_gs` | |
| P3 A/F Correction #1 | `af_correction` | **also the closed-loop indicator** — see Finding 1 |
| P4 A/F Learning #1 | `af_learning` | |
| P17 Battery Voltage | `battery_v` | **hold 3 is worthless without it** |
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
| P24 Atmospheric Pressure | normalises holds taken on different days/weather |
| P7 Manifold Absolute Pressure | absolute reference alongside P25 |

### SWITCHES — near-free, take them (4)

| switch | why |
|---|---|
| S5 Idle Switch | confirms the ECU agrees it is at idle |
| S17 Electrical Load Signal | confirms **hold 3** is actually loading the system |
| S9 Air Conditioning Switch | AC cycling perturbs idle; lets you discard affected samples |
| S12 Front O2 Rich Signal | closed-loop activity corroboration |

**Total ≈ 20 parameters + 4 switches → roughly 4–5 Hz.**

## Not offered by this ECU — confirmed 2026-08-12, with substitutes

Four of the above are **absent from Syed's RomRaider parameter list**. That is the capability
bitmap doing its job, not a configuration error — the ECU did not advertise them.

| missing | why | substitute |
|---|---|---|
| **P90 IAM** | `ecubyteindex=55, ecubit=0` | **P29 Learned Ignition Timing** (`ecubyteindex=11`) — the closest available read on what the ECU has learned about timing |
| **P91 Fine Learning Knock Correction** | `ecubyteindex=55, ecubit=0` — **the same bit as P90**, which is why both vanished together | as above; `P23 Knock Correction Advance` still covers the safety question ("is it knocking *now*") |
| **S12 Front O2 Rich Signal** | This car's front sensor is a **wideband A/F sensor**, not a narrowband O2 — the rich/lean switch has nothing to key off | **P58 A/F Sensor #1 (AFR)**, already in the list, plus `A/F Correction #1` movement as the closed-loop tell |
| **S17 Electrical Load Signal** | not advertised | **P46 Alternator Duty** (`ecubyteindex=13`) — arguably better, showing the charging system working harder. And `battery_v` is the measurement hold 3 actually depends on; S17 was only corroboration |

**Update — the substitutes are unavailable too.** `P29 Learned Ignition Timing` (byte 11) and
`P46 Alternator Duty` (byte 13) are **also absent** from this ECU's list. **This car's capability
bitmap is sparse above byte 10.** Confirmed present and streaming: `rpm`, `coolant`,
`battery_v` — bytes 8–10. Do **not** keep hunting further substitutes; every channel in this
group was "useful, not required" or corroboration for something measured directly.

**Net effect is still: nothing required is lost.** P90/P91/P29/P46 were all in the
"useful, not required" tier of `CAPTURE-PROTOCOL.md`; S12 and S17 were corroboration for
measurements taken directly (`P58` + `A/F Correction` movement, and `battery_v` respectively).

**Where the required nine live:** capability bytes **8, 9 and 10** — the block this ECU
demonstrably supports. That is why the required set survives a sparse bitmap intact.

**P200 and P201 are safe regardless.** Exactly 4 of the 95 standard parameters carry no capability
bit, and they are the `P200`–`P203` block — RomRaider *derives* these (load from MAF and rpm,
injector duty from pulse width and rpm) rather than reading them from the ECU, so no capability bit
gates them. `load` and `injector_duty` are therefore available even on a sparse ECU.

**Rule going forward: select what is listed, skip what is not, do not chase substitutes.** Only a
missing *required* channel is worth stopping for.

The P90/P91 pairing is worth remembering: parameters sharing a capability bit appear and disappear
together, so "two related channels both missing" usually means one bit, not two faults.

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

- **60 s of steady data per hold.** At ~4.7 Hz that is ~280 raw samples against
  `GridSpec.min_samples = 20`, leaving generous margin after the transient filter discards
  samples. If the observed rate is below 3 Hz, either trim parameters or extend to 90 s.
- **Warm up fully first** — coolant at operating temperature *and* `A/F Correction #1` visibly
  moving. Neither alone is sufficient.
- **One file per hold**, named for the condition (`hold1-warm-idle.csv`, `hold2-fast-idle.csv`,
  `hold3-loaded-idle.csv`). Separate files keep each `Observation` unambiguous.
- Budget ~20–30 min for the session; the logging itself is only ~3 min of it.

**Before any of it:** Stage 0 smoke/leak test, and the ground-loop remedy from
`CAPTURE-PROTOCOL.md` (DB9 pin 5 omitted, signal wire only). Acceptance test before you start:
**ECU parameters and `wideband_afr` updating simultaneously.**
