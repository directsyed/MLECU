# car/ — The ECU Project Domain (most isolated)

Loaded when working on the car. **The safety architecture leads this file and is non-negotiable.**

## ⚠ THE SAFETY ARCHITECTURE (HARD CONSTRAINT — never design away)
The fine-tuned **LLM reasons and proposes** calibration changes. It **NEVER writes ECU values
directly.** **All ECU value changes are executed by deterministic, hard-clamped, human-reviewed
algorithms** (`algorithms/` + `safety/`). You may improve *how* the clamps are implemented; you may
**not** remove the LLM-proposes / deterministic-executes separation. The clamps are **testable code,
not prose** (`safety/`): max **±3% VE/iteration**, **per-row timing ceilings**, **knock auto-abort**,
**fuel-before-timing**, **steady-state-before-transients**. Rationale: a wrong fuel/timing value
destroys an engine — deterministic clamps give provable bounds; the LLM gives flexible diagnosis.

## The test vehicle (ground truth — FACTS, do not contradict)
**2005 Subaru Forester XT, JDM EJ20X swap** (docs saying "2004" are WRONG). Full build sheet: `car/build-sheet.md`.
- **EJ20X 2.0 L JDM** (92×75 mm, **CR ~9.5:1**) dropped into a car whose ECU/ROM is calibrated for the **EJ255 2.5 L (~8.4:1)**. High CR + smaller displacement is the core reason it needs a re-tune.
- **Intake: the ENTIRE OEM 2005 FXT (EJ255) intake manifold + injectors + wiring harness** (kept for a plug-in swap on the FXT ECU). **Injectors = OEM 2005 FXT side-feed, ~500 cc/min → MATCHED to the stock ROM** (injector scaling & latency are already correct). **TGVs deleted** (tumble valves removed → idle airflow/tumble changed; TGV sensors → codes).
- **Factory drive-by-wire** (FXT was DBW from 2004 — "cable throttle" notes are WRONG).
- **VF48 turbo, 04–08 STI top-mount IC.** **Fully catless 3″ exhaust:** 3″ single-pipe cat-back → catless 3″ bellmouth downpipe → catless 04–21 STI up-pipe. **No cats anywhere; no EGT/cat-temp sensor on the up-pipe → expect a code** (plus rear-O2 / cat-monitor codes). Unconnected O2 bung remains.
- **Intake AVCS operational** (ECU-controlled); **exhaust AVCS deleted**, oil ports blocked, exhaust cam mechanically fixed at the gear (NOT flashed).
- **ROM presumed bone stock (USDM 2005 FXT ECU).** **ECU is 32-bit** (05–06 DBW family; flashes reliably; RomRaider logging needs no green-connector jumper). ROM ID not yet captured.
- **The car idles, and idles poorly; never driven by Syed.** This is the starting problem.

## Working theory for the bad idle (updated — injectors are matched, so it is NOT fuel scaling)
Vacuum/boost leak until proven otherwise (no tune fixes a leak; a leak poisons every log). **Injectors
+ manifold + ECU are matched OEM FXT, so injector scalars are correct — the idle problem is engine-side:**
1. **Airflow/VE + load model** — the ROM's 2.5 L VE/load calibration on a 2.0 L engine mis-indexes
   load-based maps and idle-airflow targets.
2. **Exhaust-AVCS delete + TGV delete** — change valve overlap and low-rpm airflow/stability the ROM
   doesn't expect (and both throw codes).
3. **Timing** — the ROM's timing for an 8.4:1 EJ255 is too advanced for the 9.5:1 EJ20X on 93 oct
   (knock / rough idle).
4. **MAF calibration** — the modified intake tract shifts the MAF feedforward; the closed loop absorbs
   it as a standing trim, and *that residual* is the one thing the current idle algorithm corrects
   (bakes into MAF scaling). With matched injectors the idle fuel error is a pure MAF error.

Idle visits ~one map cell — fix the airflow/MAF globals via closed-loop trims and the map shifts sane.
**93 octane only, always** (EJ20X assumes 100 RON; octane is the margin at the higher CR).

## Subdirs
- `ecu/` — flash tooling (KKL/FTDI for logging; Openport 2.0 or a proven Rev-E clone for flashing), ROM defs, 32-bit facts, flash discipline (**stock ROM read + archived in multiple places before ANY write — the original ROM is sacred**).
- `logging/` — SSM2-over-K-line capture, telemetry schema. **DORMANT: wideband not yet acquired → no logging yet.**
- `dataset/` — Subaru-first 70/30 corpus; **archived tuning iterations (trims → change → result) are literally training examples** in the form the model needs.
- `algorithms/` — the deterministic tuning layer: bin-to-cell, bounded corrections.
- `safety/` — the hard clamps; the write-path guard (**see the safety constraint above**).
- `simulation/` — log-replay harness, mean-value engine model (MVEM), rusEFI software-in-the-loop.

## Status (June 22, 2026) — DORMANT, hardware-blocked
**Wideband** (the ground-truth instrument — nothing proceeds without it) **not acquired.** KKL/Openport
status unconfirmed; ROM ID not yet captured. The car domain stays dormant until the wideband + logging
cable arrive; the ML data-pipeline work proceeds first.

## Carried-forward design question
Stay RomRaider/ECUFlash (OEM ECU) long-term, or plan a standalone (rusEFI) swap later? Shapes the
deterministic write-layer interface. Resolve as the architecture matures (was a ~month-3 decision).
