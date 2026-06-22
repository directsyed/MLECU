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
**2005 Subaru Forester XT, JDM EJ20X swap** (docs saying "2004" are WRONG).
- EJ20X 2.0L JDM; **factory drive-by-wire** (FXT was DBW from 2004 — "cable throttle" notes are WRONG).
- VF48 turbo, 04–08 STI top-mount IC, catless, aftermarket downpipe (unconnected O2 bung).
- Exhaust AVCS deleted, oil ports blocked, **cam timing mechanically retarded at the gears** (by hand, NOT flashed).
- **ROM presumed bone stock.** **ECU is 32-bit** (05–06 DBW family; flashes reliably; RomRaider logging needs no green-connector jumper).
- **The car idles, and idles poorly; never driven by Syed.** This is the starting problem.

## Working theory for the bad idle
Vacuum/boost leak until proven otherwise (no tune fixes a leak; a leak poisons every log). Then
**global scalars, not map cells:** injector scaling/latency, low-range MAF calibration, EJ20X-vs-EJ255
throttle-body airflow. Idle visits ~one map cell — fix the *global scalars* via closed-loop trims and
the whole map shifts sane. **93 octane only, always** (JDM EJ20X assumes 100 RON; octane is the margin).

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
