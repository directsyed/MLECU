# Forester XT: Build Sheet (single source of truth for THIS car)

Use these exact specs when searching forums/corpus for reference numbers and when seeding the sim.
The more precisely this build is pinned, the better the tune. Vehicle facts mirrored in `CLAUDE.md`;
the sim seeds from these in `ecutune/simulation/mismatch.py`.

## Chassis / ECU
- **2005 Subaru Forester XT (SG9), USDM.** Transmission: **4EAT** (selects the ROM variant → pull the 4EAT stock ROM / read his ECU).
- **ECU: USDM 2005 FXT, 32-bit DBW.** Stock ROM presumed. **ROM ID: not yet captured** (read it with the Openport, read-only, safe).

## Engine: JDM EJ20X (2.0 L)
- Bore×stroke **92 × 75 mm**, DOHC, **CR ~9.5:1** (vs the EJ255 2.5 L / **~8.4:1** the ROM is calibrated for).
- **Intake AVCS: operational** (ECU-controlled). **Exhaust AVCS: deleted** (oil ports blocked, cam fixed at the gear).

## Fuel / intake: all OEM 2005 FXT (plug-in with the FXT harness)
- **Intake manifold: OEM 2005 FXT (EJ255).**
- **Injectors: OEM 2005 FXT side-feed, ~500 cc/min, MATCHED to the stock ROM** (scaling & latency already correct; do NOT chase them). ~500 cc side-feed ≈ good for ~250–280 crank hp on gasoline near 80% duty, adequate for a stock-ish EJ20X, near its limit for big power.
- **TGVs: DELETED** (tumble valves removed; TGV position sensors → expect codes; low-rpm airflow/tumble changed).
- MAF: OEM FXT housing assumed, **confirm**. Wideband: **AEM 30-0300 target, not acquired.**

## Turbo / exhaust
- **Turbo: VF48.** Intercooler: **04–08 STI top-mount.**
- **Fully catless 3″:** 3″ single-pipe cat-back → catless 3″ bellmouth downpipe → catless **04–21 STI up-pipe**. No cats anywhere.
- **No EGT/cat-temp sensor on the up-pipe → expect a code.** Rear O2 with no cat → expect a P0420-class code. Unconnected front O2 bung remains.

## Fuel grade
- **93 octane, always** (EJ20X assumes 100 RON; octane is the safety margin at 9.5:1 CR).

## Expected DTCs (consequences of the build, not faults, the tune must handle/suppress)
- Cat-monitor / rear-O2 (no cats).
- EGT / cat-temp sensor absent (catless up-pipe).
- TGV position / function (deleted).
- Exhaust AVCS (deleted), commanded vs no response.

## Tuning implications (why the idle is bad, see CLAUDE.md working theory)
- **Do NOT pre-prioritize.** Everything is a candidate on a fresh swap; the data (ROM + logs) decides
  what and how much. The sim keeps ALL fuel levers live (neutral split), not just one.
- **Injectors are NOMINALLY matched** (OEM FXT on the FXT ROM), a useful prior, so injector scaling is
  *probably* close, but the lever stays active (latency varies with voltage/fuel pressure, and idle-only
  data can't separate injector vs MAF error anyway).
- Candidates: MAF-cal (intake mods), injector scaling/latency, 2.0-on-2.5 VE/load, idle-airflow target,
  exhaust-AVCS/TGV overlap & stability, timing too advanced for 9.5:1 on 93 oct, vacuum leak (rule out first).

## Open items to confirm
- ~~Transmission~~ **4EAT (confirmed).** · MAF housing (OEM FXT?), confirm. · Actual ROM ID, read it (Openport, read-only, safe).
