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
- **ROM presumed bone stock (USDM 2005 FXT ECU, 4EAT automatic).** **ECU is 32-bit** (05–06 DBW family; RomRaider logging needs no green-connector jumper). **ECU ID read via SSM2 = `3B12504206`** (2026-08-08). **VERIFIED 2026-08-11 as the correct part for this car** — 05/USDM/Forester/XT/AT/SH7058/sti05; absent from the 2012 defs only because that one AT calibration revision was never contributed, while its MT twin `3B12584206` is present. Proof + repro script: `car/ecu/defs/README.md`. **ROM read still BLOCKED at seed/key** (unlock refused, nothing ever written); a stock-looking ID does **not** prove an untuned ROM.
- **The car idles, and idles poorly; never driven by Syed.** This is the starting problem.

## Working theory for the bad idle (everything is a candidate — the DATA sets priorities)
Vacuum/boost leak until proven otherwise (no tune fixes a leak; a leak poisons every log). Beyond that,
**do NOT pre-prioritize one subsystem** — a fresh swap is off in several places at once; we read the car
to see *what* and *how much*. Candidates, all in play:
1. **Fuel** — MAF calibration (modified intake), injector scaling & latency (OEM FXT injectors are
   *nominally* matched to the ROM — a useful prior, NOT a verified fact; latency shifts with voltage/fuel
   pressure), and VE. At a single idle point a MAF error and an injector error are indistinguishable in
   the trim, so idle-only data can't separate them — logs across voltage/load do.
2. **Airflow / load model** — the ROM's 2.5 L VE/load calibration on a 2.0 L engine mis-indexes
   load-based maps and the idle-airflow target.
3. **Cams** — exhaust-AVCS delete + TGV delete change overlap and low-rpm stability the ROM doesn't
   expect (both throw codes); intake AVCS is live and tunable.
4. **Timing** — the ROM's advance for an 8.4:1 EJ255 is too much for the 9.5:1 EJ20X on 93 oct.

The deterministic layer treats each as its own axis/stage (fuel first = idle Stage 2), each corrected by
the same propose->clamp->converge loop and prioritized by what the logs actually show. Idle visits ~one
map cell — fix the globals via closed-loop trims and the map shifts sane. **93 octane only, always**
(EJ20X assumes 100 RON; octane is the margin at the higher CR).

## Subdirs
- `ecu/` — flash tooling (KKL/FTDI for logging; Openport 2.0 or a proven Rev-E clone for flashing), ROM defs, 32-bit facts, flash discipline (**stock ROM read + archived in multiple places before ANY write — the original ROM is sacred**).
- `logging/` — SSM2-over-K-line capture, telemetry schema, `CAPTURE-PROTOCOL.md` (the 3-pull procedure). **LIVE SSM2 logging verified on the car 2026-08-08** (RomRaider via Openport clone). AEM 30-0300 wideband installed and displaying; its serial link to the PC is still down.
- `dataset/` — Subaru-first 70/30 corpus; **archived tuning iterations (trims → change → result) are literally training examples** in the form the model needs.
- `algorithms/` — the deterministic tuning layer: bin-to-cell, bounded corrections.
- `safety/` — the hard clamps; the write-path guard (**see the safety constraint above**).
- `simulation/` — log-replay harness, mean-value engine model (MVEM), rusEFI software-in-the-loop.

## Status (Aug 8, 2026) — ACTIVE: first contact made, two blockers
**Live SSM2 logging works** (RomRaider + Washinglee Openport clone: RPM, coolant, battery V streaming).
Two blockers, both diagnosed to a shortlist in `sessions/handoffs/2026-08-08-forester-first-logging-toolchain.md`:
**(A)** ECU ROM read refused at seed/key — locked/married ECU vs clone-cable K-line reflash support; CAL ID
check queued. **(B)** AEM 30-0300 wideband serial silent on COM5 — USB-serial adapter chipset is the prime
suspect. **The wideband link is the critical path:** once AFR reaches RomRaider, `logging/CAPTURE-PROTOCOL.md`
runs. The ROM read is NOT required for capture — only for the (later) write path.

## Carried-forward design question
Stay RomRaider/ECUFlash (OEM ECU) long-term, or plan a standalone (rusEFI) swap later? Shapes the
deterministic write-layer interface. Resolve as the architecture matures (was a ~month-3 decision).
