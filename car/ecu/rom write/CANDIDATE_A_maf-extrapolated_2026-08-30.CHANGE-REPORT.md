# CHANGE REPORT — maf_transfer

- ROM: `POSTFLASH3_3B12504206_maf_2026-08-30.bin`
- proposal: `maf-0`  provenance: **algorithm:maf_transfer**
- edits proposed: 30 -> surviving clamps: 30
- bytes changed: 94 in 30 range(s)
- checksum records repaired: [0]
- max storage quantisation error: 1.111e-05

> sensor.maf_transfer: def A2WC410D @0xCB75C (float, MassAirflow(g/s)1, rounding=nearest)

## sensor.maf_transfer  (Mass Airflow (g/s))

| cell | before | after | change |
|---|---|---|---|
| 0,8 | 3.395 | 3.321 | -2.2% |
| 0,9 | 3.788 | 3.847 | +1.6% |
| 0,10 | 4.176 | 4.102 | -1.8% |
| 0,12 | 5.113 | 5.203 | +1.8% |
| 0,17 | 13.46 | 13.81 | +2.6% |
| 0,18 | 15.76 | 16.09 | +2.1% |
| 0,19 | 18.83 | 19.19 | +1.9% |
| 0,20 | 22.4 | 22.85 | +2.0% |
| 0,21 | 26.27 | 26.66 | +1.5% |
| 0,26 | 48.41 | 49.64 | +2.5% |
| 0,28 | 59.31 | 62.39 | +5.2% |
| 0,29 | 68.28 | 78.19 | +14.5% |
| 0,30 | 68.28 | 89.13 | +30.5% |
| 0,31 | 77.34 | 101 | +30.5% |
| 0,32 | 87.17 | 113.8 | +30.5% |
| 0,33 | 97.84 | 127.7 | +30.5% |
| 0,34 | 109.4 | 142.8 | +30.5% |
| 0,35 | 122 | 159.2 | +30.5% |
| 0,36 | 135.4 | 176.8 | +30.5% |
| 0,37 | 150.1 | 195.9 | +30.5% |
| 0,38 | 166.1 | 216.9 | +30.5% |
| 0,39 | 184.2 | 240.5 | +30.5% |
| 0,40 | 203.4 | 265.6 | +30.5% |
| 0,41 | 223.1 | 291.3 | +30.5% |
| 0,42 | 243.3 | 317.6 | +30.5% |
| 0,43 | 257.1 | 335.6 | +30.5% |
| 0,44 | 272.1 | 355.2 | +30.5% |
| 0,45 | 280.1 | 365.6 | +30.5% |
| 0,46 | 288.2 | 376.2 | +30.5% |
| 0,47 | 296.5 | 387 | +30.5% |

_30 cells changed, 18 left at stock._

## Clamps that fired

| clamp | cell | requested | allowed | action |
|---|---|---|---|---|
| sensor_calibration | 0,29 | 78.19 | 78.19 | extrapolation_allowed |
| sensor_calibration | 0,30 | 89.13 | 89.13 | extrapolation_allowed |
| sensor_calibration | 0,31 | 101 | 101 | extrapolation_allowed |
| sensor_calibration | 0,32 | 113.8 | 113.8 | extrapolation_allowed |
| sensor_calibration | 0,33 | 127.7 | 127.7 | extrapolation_allowed |
| sensor_calibration | 0,34 | 142.8 | 142.8 | extrapolation_allowed |
| sensor_calibration | 0,35 | 159.2 | 159.2 | extrapolation_allowed |
| sensor_calibration | 0,36 | 176.8 | 176.8 | extrapolation_allowed |
| sensor_calibration | 0,37 | 195.9 | 195.9 | extrapolation_allowed |
| sensor_calibration | 0,38 | 216.9 | 216.9 | extrapolation_allowed |
| sensor_calibration | 0,39 | 240.5 | 240.5 | extrapolation_allowed |
| sensor_calibration | 0,40 | 265.6 | 265.6 | extrapolation_allowed |
| sensor_calibration | 0,41 | 291.3 | 291.3 | extrapolation_allowed |
| sensor_calibration | 0,42 | 317.6 | 317.6 | extrapolation_allowed |
| sensor_calibration | 0,43 | 335.6 | 335.6 | extrapolation_allowed |
| sensor_calibration | 0,44 | 355.2 | 355.2 | extrapolation_allowed |
| sensor_calibration | 0,45 | 365.6 | 365.6 | extrapolation_allowed |
| sensor_calibration | 0,46 | 376.2 | 376.2 | extrapolation_allowed |
| sensor_calibration | 0,47 | 387 | 387 | extrapolation_allowed |

## Evidence

- airflow bin 109.43 g/s: EXTRAPOLATED at the measured plateau +30.5% (from breakpoints [26, 27, 28], no samples of its own)
- airflow bin 121.97 g/s: EXTRAPOLATED at the measured plateau +30.5% (from breakpoints [26, 27, 28], no samples of its own)
- airflow bin 13.46 g/s: trim +3.7% -> applied +2.6% (damping 0.7)
- airflow bin 135.42 g/s: EXTRAPOLATED at the measured plateau +30.5% (from breakpoints [26, 27, 28], no samples of its own)
- airflow bin 15.76 g/s: trim +3.0% -> applied +2.1% (damping 0.7)
- airflow bin 150.09 g/s: EXTRAPOLATED at the measured plateau +30.5% (from breakpoints [26, 27, 28], no samples of its own)
- airflow bin 166.14 g/s: EXTRAPOLATED at the measured plateau +30.5% (from breakpoints [26, 27, 28], no samples of its own)
- airflow bin 18.83 g/s: trim +2.7% -> applied +1.9% (damping 0.7)
- airflow bin 184.21 g/s: EXTRAPOLATED at the measured plateau +30.5% (from breakpoints [26, 27, 28], no samples of its own)
- airflow bin 203.44 g/s: EXTRAPOLATED at the measured plateau +30.5% (from breakpoints [26, 27, 28], no samples of its own)
- airflow bin 22.40 g/s: trim +2.8% -> applied +2.0% (damping 0.7)
- airflow bin 223.14 g/s: EXTRAPOLATED at the measured plateau +30.5% (from breakpoints [26, 27, 28], no samples of its own)
- airflow bin 243.32 g/s: EXTRAPOLATED at the measured plateau +30.5% (from breakpoints [26, 27, 28], no samples of its own)
- airflow bin 257.10 g/s: EXTRAPOLATED at the measured plateau +30.5% (from breakpoints [26, 27, 28], no samples of its own)
- airflow bin 26.27 g/s: trim +2.1% -> applied +1.5% (damping 0.7)
- airflow bin 272.11 g/s: EXTRAPOLATED at the measured plateau +30.5% (from breakpoints [26, 27, 28], no samples of its own)
- airflow bin 280.06 g/s: EXTRAPOLATED at the measured plateau +30.5% (from breakpoints [26, 27, 28], no samples of its own)
- airflow bin 288.18 g/s: EXTRAPOLATED at the measured plateau +30.5% (from breakpoints [26, 27, 28], no samples of its own)
- airflow bin 296.47 g/s: EXTRAPOLATED at the measured plateau +30.5% (from breakpoints [26, 27, 28], no samples of its own)
- airflow bin 3.39 g/s: trim -3.1% -> applied -2.2% (damping 0.7)
- airflow bin 3.79 g/s: trim +2.2% -> applied +1.6% (damping 0.7)
- airflow bin 4.18 g/s: trim -2.5% -> applied -1.8% (damping 0.7)
- airflow bin 48.41 g/s: trim +3.6% -> applied +2.5% (damping 0.7)
- airflow bin 5.11 g/s: trim +2.5% -> applied +1.8% (damping 0.7)
- _(+6 more)_

---
**Nothing has been flashed.** This file is a candidate image; flashing stays a human act, against the checklist (battery charger, AC power, green test-mode connectors joined, stock ROM archived in three places).

Tool: **FastECU** (stock upstream build, profile `sub_ecu_denso_sh7058`). EcuFlash cannot be used on this ECU -- its SecurityAccess key is rejected even with the green connectors joined, retested 2026-08-29. See ecu/ROM-READ-BLOCKER.md.