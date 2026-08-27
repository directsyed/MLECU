# CHANGE REPORT — maf_transfer

- ROM: `3B12504206_2026-08-16_16h51m01s.bin`
- proposal: `maf-0`  provenance: **algorithm:maf_transfer**
- edits proposed: 14 -> surviving clamps: 14
- bytes changed: 47 in 14 range(s)
- checksum records repaired: [0]
- max storage quantisation error: 1.834e-06

> sensor.maf_transfer: def A2WC410D @0xCB75C (float, MassAirflow(g/s)1)

## sensor.maf_transfer  (Mass Airflow (g/s))

| cell | before | after | change |
|---|---|---|---|
| 0,7 | 3.11 | 3.012 | -3.2% |
| 0,14 | 7.41 | 7.532 | +1.6% |
| 0,15 | 8.67 | 9.124 | +5.2% |
| 0,16 | 10.07 | 10.7 | +6.3% |
| 0,17 | 11.61 | 12.57 | +8.2% |
| 0,18 | 13.3 | 14.5 | +9.0% |
| 0,19 | 15.13 | 17.16 | +13.4% |
| 0,20 | 17.25 | 20.24 | +17.4% |
| 0,21 | 19.68 | 23.6 | +19.9% |
| 0,22 | 22.38 | 26.97 | +20.5% |
| 0,23 | 25.4 | 30.75 | +21.1% |
| 0,24 | 28.77 | 35.12 | +22.1% |
| 0,25 | 32.36 | 39.62 | +22.4% |
| 0,26 | 38.22 | 44.83 | +17.3% |

_14 cells changed, 34 left at stock._

## Clamps that fired

| clamp | cell | requested | allowed | action |
|---|---|---|---|---|
| sensor_calibration | 0,26 | 45.38 | 44.83 | monotonicity_limited |

## Evidence

- airflow bin 10.07 g/s: trim +9.0% -> applied +6.3% (damping 0.7)
- airflow bin 11.61 g/s: trim +11.8% -> applied +8.2% (damping 0.7)
- airflow bin 13.30 g/s: trim +12.9% -> applied +9.0% (damping 0.7)
- airflow bin 15.13 g/s: trim +19.1% -> applied +13.4% (damping 0.7)
- airflow bin 17.25 g/s: trim +24.8% -> applied +17.4% (damping 0.7)
- airflow bin 19.68 g/s: trim +28.4% -> applied +19.9% (damping 0.7)
- airflow bin 22.38 g/s: trim +29.3% -> applied +20.5% (damping 0.7)
- airflow bin 25.40 g/s: trim +30.1% -> applied +21.1% (damping 0.7)
- airflow bin 28.77 g/s: trim +31.5% -> applied +22.1% (damping 0.7)
- airflow bin 3.11 g/s: trim -4.5% -> applied -3.2% (damping 0.7)
- airflow bin 32.36 g/s: trim +32.1% -> applied +22.4% (damping 0.7)
- airflow bin 38.22 g/s: trim +26.8% -> applied +18.7% (damping 0.7)
- airflow bin 7.41 g/s: trim +2.3% -> applied +1.6% (damping 0.7)
- airflow bin 8.67 g/s: trim +7.5% -> applied +5.2% (damping 0.7)

---
**Nothing has been flashed.** This file is a candidate image; flashing stays a human act in ECUFlash, against the checklist (battery charger, AC power, stock ROM archived in three places).