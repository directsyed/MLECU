# car/logging/

Live ECU telemetry capture (SSM2-over-K-line), the capture protocols, and every log the car
has produced. Parsing/binning lives in `../ecutune/logparse/`.

**Status:** live capture **ACTIVE**. Wideband (AEM UEGO) installed; ROM read solved 2026-08-16;
the recovered extended parameters are installed and validated (see `../ecu/defs/`).

## Layout

| path | what |
|---|---|
| `CAPTURE-PROTOCOL.md` | the three-hold stationary idle procedure |
| `DRIVING-CAPTURE-PROTOCOL.md` | the vacuum coverage-sweep spec (no boost) |
| `IDLE-LOG-PROFILE.md` | which channels to select, and why |
| `idle/` | stationary captures — idle, warm-up, stored-learning |
| `drive/` | on-road captures + their analysis notes |
| `diagnostics/` | toolchain traces (J2534 shim), not vehicle telemetry |

## Naming

`<type>-<YYYYMMDD>[-<NN>]-<descriptor>.csv` — sorts chronologically, self-describing.
`NN` is the sequence within a single session. Keep it; the analysis notes reference files by name.

## Current inventory

### idle/
| file | what |
|---|---|
| `idle-20260811-warm-hold.csv` | fully warm hold, ECT 183–189 °F. Source of the 2026-08-11 MAF datum. |
| `idle-20260813-warmup-partial.csv` | partial warm-up, ECT 100→135 °F. Healthy fast-idle decay, but does not reach stable warm. |
| `idle-20260816-01-warm.csv` | three-hold capture, hold 1 — warm idle |
| `idle-20260816-02-fast.csv` | three-hold capture, hold 2 — fast idle (~2× airflow) |
| `idle-20260816-03-loaded.csv` | three-hold capture, hold 3 — electrically loaded |
| `idle-20260819-cold-to-warm.csv` | **extended-param validation run.** Pre-crank → ECT 102→194 °F, 15.6 min, 9.62 Hz. Validated CL/OL, CL Fueling Target, IAM, Engine Load, Injector PW. |
| `idle-20260825-stored-learning.csv` | stored A/F learning cells A–D. Validated the `0xFF26xx` RAM region. |

### drive/
| file | what |
|---|---|
| `drive-20260826-01-vacuum-residential.csv` | 5.3 min. **Wideband unreliable after ~120 s** (USB knocked); ECU channels fine. |
| `drive-20260826-02-vacuum-residential.csv` | 12.0 min, clean |
| `drive-20260826-03-vacuum-road.csv` | 17.9 min, clean, first real-road capture |
| `ANALYSIS-2026-08-26-vacuum-drives.md` | trim-vs-load surface, 31 knock onsets, coverage grid |

## Hard rules carried from the protocols

- **No boost** on any vacuum capture — `Manifold Absolute Pressure` stays below ~100 kPa. It is
  the only boost gauge on this car.
- **~24 parameters is the practical SSM2 ceiling** on this ECU. Exceeding it produces
  `readMsg error: timeout expired waiting for N more bytes`, where N ≈ addresses + 6.
- Green test-mode connectors **disconnected** for anything that moves.
- DB9 pin 5 omitted (ground-loop remedy).
