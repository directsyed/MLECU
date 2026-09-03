# Handoff, 2026-08-31: ceiling rebuilt from a reference tune, MAF extrapolated, interface dead

DELTA since `2026-08-30-timing-stage-built-candidate-waiting.md`. Read that first. Nothing has
been flashed. A reviewed candidate is waiting and the hardware to write it is broken.

## 1. The blocker

**The J2534 interface is dead.** The Washinglee Openport 2.0 clone lost both supply paths at the
instant a flash was started: no USB enumeration, no LEDs from OBD pin 16. The ECU was never
touched (0% progress through a dead interface means nothing was transmitted, and the car runs).

Measurements so far: car OBD pin 16 to pin 4 reads 12.7 V, so the car side is healthy. The
device's own pin 16 to pin 4 reads 11 kOhm, so the input is not shorted. Since USB and vehicle
power enter on different pins through different front ends and both fail, the suspect is what
they share: the internal regulator and the rail it feeds.

A replacement Mini-B cable is on order. If that does not revive it, the next test is to open the
case, power from the car, and measure across the regulator (12 V in, 0 V out confirms it).

Full record and diagnosis order: `car/ecu/INTERFACE-FAILURE-2026-08-31.md`. Two of my hypotheses
were withdrawn there; the reasoning trail is kept deliberately.

**Purchase plan: two of the same Washinglee clone.** A genuine Openport 2.0 is out of production
and sells for thousands, so "buy genuine" is not actionable. Same model because this one is
proven against this ECU with FastECU's `sub_ecu_denso_sh7058` profile. Two because several writes
remain and they are consumables.

## 2. What is waiting to be flashed

`car/ecu/rom write/CANDIDATE_B_maf-plus-timing_2026-08-30.bin`. Audited GO. Built by chaining:

    POSTFLASH3 --tune-maf --extrapolate-maf--> candidate A --tune-timing--> candidate B

Each step audited against its own base, which keeps the "exactly one semantic table changed"
rule intact with no loosening. Cross-checked with `--rom-diff POSTFLASH3 B`: 10 tables identical,
2 differing, exactly as intended. Flash only B; A is an intermediate.

## 3. The reference ROM changed the timing ceiling

Syed supplied a tuned ROM from a RomRaider thread: the same EJ20X into an EJ255-based ECU, same
VF48, same catless exhaust (`AZ1E401A`, an 08 WRX). Quarantined under
`car/ecu/reference-roms-DO-NOT-FLASH/`, read-only, informing a ratified config number and nothing
else.

It proved the old ceiling wrong in both directions. At 2400-3200 rpm:

| load | his tuned | our stock | old ceiling |
|---|---|---|---|
| 0.55 | 43.8 | 45.0 | 30, far too tight |
| 0.85 | 38.0 | 40.1 | 22, far too tight |
| 1.60 | 8.9 | 15.2 | 22, too loose |
| 2.20 | 2.3 | 6.0 | 22, badly too loose |

Replaced by a 2-D `timing_ceiling_map` (6 rpm bands by 9 load bands). It had to become 2-D
because the constraint is not separable: 40 deg at 1200 rpm and 1.3 g/rev is lugging under load,
the worst cell in the map, while the same value at 4400 rpm is ordinary. Derivation is mechanical
and reproducible, not hand-drawn: min(reference over the rpm band) minus 3 deg, floored at 5,
load under 0.55 left at the ratified 45.

`max_timing_retard` went 20 to 30 because it must clear the deepest cut the ceiling itself
demands (27.141 deg) or the two limits deadlock. A test pins that relationship rather than either
number.

## 4. Undriven cells reach the ceiling in one pass

Syed's ruling. The rate limit exists so a step can be observed on the next drive, and a cell with
zero samples has nothing to observe. Verified from per-cell sample counts the CLI measures from
the log, never claimed by the proposal, and bounded so it can only land a cell exactly on its
ceiling. Effect: cells left above their ceiling after one pass went from 151 to 6, remaining
passes from 4 to 1.

## 5. The MAF curve is extrapolated above 68 g/s

`--extrapolate-maf`, opt-in. The measured error plateaus at roughly +32% across 42-59 g/s on
hundreds of samples, so the plateau is held flat above the measured span at **+30.54%**, derived
from breakpoints 26/27/28 against a maximum ever measured of +37.5%.

The rule against extrapolating was written when the data was vacuum-only and the top of the curve
looked non-monotonic. Three flashes later the premise inverted. Above 68 g/s the curve was still
stock, which is not a neutral "no opinion" but a known 30% under-read; closed-loop trims hide it
and open loop does not; and this car has never been in power open loop, so the first
full-throttle pull would have been the first exposure with no safety net. Commanded 12.5 AFR
would have arrived as roughly 18.

`clamp_sensor_calibration` gained a verified exemption to its evidence rule: a human must enable
it, the cell must sit above every evidenced breakpoint, and the result cannot exceed the largest
correction actually measured on this car.

## 6. D35, two IAM gates nobody had noticed

| table | value | consequence |
|---|---|---|
| `Boost Control Disable (IAM)` | 0.20 / 0.65 | boost control disabled below 0.20, re-enabled at 0.65 |
| `Primary Open Loop Fuel Map Switch (IAM)` | 0.35 | below this the ECU runs the Failsafe fuel map |

IAM has been at 0.000 to 0.125 throughout, so **the car has been driving with boost control
disabled**, on wastegate spring pressure. That is very likely why +6.53 psi is the most ever
recorded, and it means every boost figure in this project so far was taken with the controller
switched off.

Recovery is a compound hazard the driver does not initiate: the re-enable threshold (0.65) sits
above the initial IAM (0.50), so a successful timing fix can cross 0.20, 0.35 and 0.65 in one
drive. More air and a leaner target, together, on the ECU's schedule.

## 7. Housekeeping

`rom read/` and `rom write/` now hold only what is live (the stock ROM, what is on the car, and
the candidate awaiting review). Everything else moved to `superseded/`. READMEs in both folders
carry the conventions, including the chained-build rule.

Em dashes removed from 269 tracked files (3,312 of them) with grammar-aware substitution.
`context/bootstrap-source/`, `ml/eval/data/` and third-party XML were deliberately left alone
because altering them would falsify a record rather than tidy prose.

Tests: **200 passing**, up from 188.

## 8. NEXT

1. Revive or replace the interface. Nothing else can proceed.
2. Flash candidate B.
3. **Drive exactly as before.** Same roads, same style. D30 failed to be evaluable because the
   driving got harder between drives, and repeating that would waste this one. Watch for the car
   feeling stronger on its own, which would be boost control returning at IAM 0.20 rather than
   anything the driver did.
4. Read IAM. Recovery off 0.000 is the single clearest signal the timing map worked. If IAM stays
   at zero, timing was not the whole story and the smoke test and fuel-pressure test move to the
   top.
5. Then a highway drive at partial throttle, staying in closed loop, to measure the 68 to 150 g/s
   region and replace the extrapolated plateau with real data.
6. One timing pass still outstanding: 6 cells sit above their ceiling, worst by 2.65 deg.

Still open and unchanged: the smoke test, the fuel-pressure test, and an off-machine third copy
of the stock ROM.
