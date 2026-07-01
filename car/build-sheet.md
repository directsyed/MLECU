# Forester XT — Build Sheet (single source of truth for THIS car)

Use these exact specs when searching forums/corpus for reference numbers and when seeding the sim.
The more precisely this build is pinned, the better the tune. Vehicle facts mirrored in `CLAUDE.md`;
the sim seeds from these in `ecutune/simulation/mismatch.py`.

## Chassis / ECU
- **2005 Subaru Forester XT (SG9), USDM.** Transmission: **TBD — 4EAT vs 5MT (confirm; it selects the ROM variant).**
- **ECU: USDM 2005 FXT, 32-bit DBW.** Stock ROM presumed. **ROM ID: not yet captured** (read it with the Openport — read-only, safe).

## Engine — JDM EJ20X (2.0 L)
- Bore×stroke **92 × 75 mm**, DOHC, **CR ~9.5:1** (vs the EJ255 2.5 L / **~8.4:1** the ROM is calibrated for).
- **Intake AVCS: operational** (ECU-controlled). **Exhaust AVCS: deleted** (oil ports blocked, cam fixed at the gear).

## Fuel / intake — all OEM 2005 FXT (plug-in with the FXT harness)
- **Intake manifold: OEM 2005 FXT (EJ255).**
- **Injectors: OEM 2005 FXT side-feed, ~500 cc/min — MATCHED to the stock ROM** (scaling & latency already correct; do NOT chase them). ~500 cc side-feed ≈ good for ~250–280 crank hp on gasoline near 80% duty — adequate for a stock-ish EJ20X, near its limit for big power.
- **TGVs: DELETED** (tumble valves removed; TGV position sensors → expect codes; low-rpm airflow/tumble changed).
- MAF: OEM FXT housing assumed — **confirm**. Wideband: **AEM 30-0300 target, not acquired.**

## Turbo / exhaust
- **Turbo: VF48.** Intercooler: **04–08 STI top-mount.**
- **Fully catless 3″:** 3″ single-pipe cat-back → catless 3″ bellmouth downpipe → catless **04–21 STI up-pipe**. No cats anywhere.
- **No EGT/cat-temp sensor on the up-pipe → expect a code.** Rear O2 with no cat → expect a P0420-class code. Unconnected front O2 bung remains.

## Fuel grade
- **93 octane, always** (EJ20X assumes 100 RON; octane is the safety margin at 9.5:1 CR).

## Expected DTCs (consequences of the build, not faults — the tune must handle/suppress)
- Cat-monitor / rear-O2 (no cats).
- EGT / cat-temp sensor absent (catless up-pipe).
- TGV position / function (deleted).
- Exhaust AVCS (deleted) — commanded vs no response.

## Tuning implications (why the idle is bad — see CLAUDE.md working theory)
- **Injector scalars are CORRECT (matched) — do not chase them.** The sim locks them.
- Real issues: 2.0 L-on-2.5 L airflow/VE/load model; idle-airflow target; exhaust-AVCS/TGV overlap &
  stability; timing too advanced for 9.5:1 on 93 oct; MAF-cal residual (the one the idle algorithm
  corrects); possible vacuum leak (rule out first).

## Open items to confirm
- Transmission (4EAT/5MT) → ROM variant. · MAF housing (OEM FXT?). · Actual ROM ID (read it).
