# reference-roms-DO-NOT-FLASH/

## ⛔ NOTHING IN THIS DIRECTORY MAY EVER BE FLASHED TO SYED'S CAR. ⛔

These are **other people's ROMs**, kept for **READING ONLY** — to see what a human tuner
actually did to a comparable car. They are reference material, never a source of values.

**They are not for this ECU.** The calibration ID differs from ours (`A2WC411D` /
CID `3B12504206`), so flashing one would put another car's entire calibration — fuelling,
timing, boost, immobiliser, transmission — onto Syed's engine.

The pre-flash audit already refuses these structurally: `--verify-flash` compares the
calibration ID at `0x2000` between the stock image and the candidate and fails the
`calibration ID unchanged` check. Verified 2026-08-30 by actually passing this file in as a
candidate — it returns NO-GO. That is a guard, not a reason to be careless.

## How reference ROMs may and may not be used

| allowed | not allowed |
|---|---|
| reading tables to sanity-check a **ratified ceiling** in `config.yaml` | feeding values into `algorithms/` or any proposal |
| understanding the SHAPE of a tuner's map | copying cells into our map |
| informing a number **Syed ratifies by hand** | anything automated |

The ceiling is a human-ratified config number, so third-party evidence belongs there and
nowhere else. Nothing here touches the deterministic layer.

---

## AZ1E401A — 2008 WRX ECU, EJ20X swap, VF48 (TUNED)

Supplied by Syed 2026-08-30 from a RomRaider forum thread
(`https://www.romraider.com/forum/viewtopic.php?f=26&t=19355`) and its linked Google Drive.

- **sha256** `b514d03cef2ef8c56576308d7b6aba99b970d6140d38736a6408cede5cbd6309`
- **calibration ID** `AZ1E401A`, header `H4T US MB MT`, `Copr.DENSO`
- 1,048,576 bytes; def present at `SubaruDefs/ECUFlash/subaru metric/Impreza WRX/AZ1E401A.xml`

**Why it is interesting:** the same swap as ours — an **EJ20X (9.5:1) running an EJ255-based
ECU**, with a **VF48** and a **catless exhaust**. That is not a loose analogue; it is the same
problem, already solved by a human tuner.

**How it differs from our car — read every number with these in mind:**

| | this reference | Syed's car |
|---|---|---|
| ECU / calibration | AZ1E401A (08 WRX) | A2WC411D (05 FXT), CID `3B12504206` |
| transmission | **MT** (`H4T US MB MT`) | **AT** (4EAT) |
| exhaust AVCS | unplugged, still free to move | **mechanically fixed**, oil ports blocked |
| stock counterpart | **NOT AVAILABLE** | archived, byte-validated |

**No stock counterpart was supplied**, so we cannot diff tuned-vs-stock to isolate what the
tuner changed. Everything read from this file is an ABSOLUTE map value, not a delta, and the
08 WRX base calibration is not our base calibration. Treat magnitudes as indicative, not exact.

Unknowns that no .bin can answer: the fuel he ran, his boost target, and — the important one —
**whether that tune was actually any good, or whether the engine survived it.**
