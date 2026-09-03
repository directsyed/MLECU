# Driving-capture protocol: what the VE/timing build needs from a real DRIVEN log

**Status: written 2026-08-16, after the ROM read + the healthy idle diagnosis. Companion to
`CAPTURE-PROTOCOL.md` (idle three-hold). Not yet executed on the car.**

## Why this is different from the idle capture

The three-hold idle capture answers a **fuel** question at ~one operating point (leak vs MAF vs
injector). VE and timing are **maps**: the ROM's 2.5 L (EJ255) volumetric-efficiency and ignition
calibration indexed by load × rpm, running on a 2.0 L (EJ20X) at higher compression. The mismatch is
invisible at idle (idle visits ~one cell, and closed loop hides it) and appears **under load, in
open loop**. So this capture is a **coverage sweep**, not a steady hold: drive so the log VISITS many
load/rpm cells with enough steady samples in each, and the binner (`logparse.binning`) fills a
load×rpm grid the VE build corrects cell by cell.

**VE correction, precisely (D19):** per cell, `VE_correction = measured_AFR / target_AFR`. Both come
from the log, `wideband_afr` (measured) and, once the extended params are validated,
`Closed Loop Fueling Target` (target). Until that channel is validated, target is read from the ROM's
`fuel.target_afr_primary` map at the cell's load/rpm. **Timing is retreat-only**: the layer may pull
timing where `Feedback Knock` shows knock; adding timing is a human decision.

## ⚠ Before load tuning: the boost line (the one hard rule)

Syed's sequencing (2026-08-16): tune enough to drive well, defer the smoke test. That is fine for
**idle and vacuum/cruise**: a small leak there is a trim offset, harmless. It is **NOT** fine under
**boost**: an unmetered-air (boost) leak runs the engine lean under positive pressure, and lean +
9.5:1 CR + catless + 93 oct is the detonation path that holes pistons.

- **This capture stays OUT of boost, manifold pressure below atmospheric the whole time.**
- Watch `wideband_afr` continuously. If AFR trends lean as load rises, or ANY knock retard /
  `Feedback Knock` appears, **lift**: that is itself the boost-leak / VE-lean signature, seen before
  it costs a piston. Note it and stop.
- Boost/WOT tuning **no longer waits** for the smoke test; that rule was circular (the shop is a
  highway drive away). See decisions.md D21 (2026-08-26). A base tune covering boost comes FIRST;
  the smoke test then validates it. A leak still invalidates *final* boost VE numbers.

## Channels to log

Start from the idle profile (`IDLE-LOG-PROFILE.md`); it already carries the load-relevant standard
params: `P200 Engine Load (g/rev)` → `load` (the map's x-axis), `P25 Manifold Relative Pressure`,
`P7 MAP`, `P48 Intake VVT Advance`, `P201 Injector Duty`, `P10 Ignition Total Timing`,
`P58 A/F Sensor #1` (factory wideband, second opinion) + the AEM.

**Add the recovered extended params once validated** (`car/ecu/defs/EXTENDED-PARAMS-RECOVERY.md` -
splice the fragment, then Syed's validation log). The ones that matter for this build:
`Closed Loop Fueling Target` (the VE denominator, logged directly), `Feedback Knock Correction`
(the timing-retreat trigger), `Fine Learning Knock Correction`, `IAM` (knock-learning health, below
1.00 means the ECU already pulled timing, a red flag), `Fuel Injector #1 Pulse Width`, `Target Boost`
/ `Boost Error` (for later boost work). **Do not trust any recovered channel until it passes live
validation** (IAM ≈ 1.00 healthy, CL/OL flips, injector PW ≈ P21).

If the extended params are not yet validated, run this capture on the idle profile anyway, `load`,
`wideband_afr`, `rpm`, `timing_total`, `knock_retard` are enough to start VE from the ROM's target
map; the extended channels make it richer, not possible-vs-impossible.

## The drive

- **Fully warmed, closed loop confirmed** (`A/F Correction #1` moving) before you start.
- **Coverage:** cover the low-to-mid load/rpm range in **vacuum**: steady cruise at several speeds
  and gears, plus gentle part-throttle (still below atmospheric MAP). Aim to visit many distinct
  (load, rpm) cells: roughly **1500–3500 rpm**, light-to-moderate load. Hold each condition steady a
  few seconds so cells accumulate ≥ `min_samples` (20) steady samples after the transient filter.
- **One continuous file is fine**: the binner separates cells; you do not need one-file-per-cell as
  the idle holds did. Name it for the session (`drive-vacuum-<date>.csv`).
- **Duration ~15–30 min** of logging. Longer fills more cells; there is no penalty for coverage.
- **Ground-loop remedy** (`CAPTURE-PROTOCOL.md`): DB9 pin 5 omitted / USB isolator. Acceptance test
  before you roll: **ECU params AND `wideband_afr` updating simultaneously**, and the green
  test-mode connectors **disconnected** (they are for reading, not driving).

## What the layer does with it (and what it does NOT do yet)

- The bridge/binner turn the drive into a load×rpm grid of `measured_AFR` and `trim`. **The VE/timing
  proposers do not exist yet** (D19, gated on exactly this data); this capture is the **raw material
  Claude builds them from**, not something the layer auto-tunes today.
- When they exist, the loop is the same as idle: bin → **the layer proposes** (clamped: `ve_rate_limit
  ±3%`, `knock_auto_abort`, timing retreat-only) → **Syed reviews the change report** → flash → re-log
  → verify. **Claude builds and verifies; the pipeline tunes; Syed approves.** And the **write path to
  the car is still unproven** (only read is), so the first flash is its own careful milestone.

## Honest limits

- A single vacuum drive cannot exercise the boost VE/timing cells; those need the smoke test first,
  then a controlled boost pull. This capture deliberately covers only the safe half of the map.
- The measured-AFR/target-AFR VE method assumes the wideband is trustworthy; it is (AEM vs factory
  A/F sensor agreed to 0.02 AFR, 2026-08-13), and that the MAF is reading correctly at these cells,
  which the idle capture supports but did not prove across the load range. Treat the first VE pass as
  a hypothesis to verify by re-log, not a final map.
