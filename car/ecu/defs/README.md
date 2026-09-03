# car/ecu/defs/: RomRaider ROM definitions

## What is here

`ecu_defs.xml`: 7,825,988 bytes, file date **2012-08-20**. This is the RomRaider `0.8.3.1b
10-07-09` forum-archive definition set (**STANDARD units**), and it is the file actually in use on
the tuning laptop at `C:\Users\Syed\Documents\RomRaider Defs\ecu_defs.xml`.

**It is committed deliberately.** Upstream is effectively dead: `github.com/Merp/SubaruDefs` stable
branch last committed in 2012, the ECU-definitions link in the RomRaider releases notes resolves to
this same archive, and RomRaider 1.1.0 (Nov 2025) ships with **no definitions bundled**. Verified
again 2026-08-11; there is no newer set. Committing it preserves the exact artifact the project's
results depend on.

**Scope note:** these are *ROM table* definitions, used by the RomRaider **editor**. Logging uses a
separate file (`logger_STD_EN_v370.xml`) and does **not** depend on this one. EcuFlash does not use
it at all, an ECU read failure is never caused by a missing entry here.

## ★ The `3B12504206` question: SETTLED 2026-08-11

The car's ECU reports **`3B12504206`** over SSM2, and that ID is **absent from this file**. The
question raised was whether an unlisted ID means the ECU does not belong in the car.

**It does not. The ECU is correct for the vehicle.** Parsing all 332 ECU-ID-bearing entries shows
the `3B125*` family is exclusively **2005 USDM Forester XT**, and the gap is structural:

| rev | AT ecuid | AT xmlid | MT ecuid | MT xmlid |
|---|---|---|---|---|
| 40 | `3B12504006` | A2WC**400**D | `3B12584006` | A2WC**400**I |
| 41 | `3B12504106` | A2WC**410**D | `3B12584106` | A2WC**410**I |
| **42** | **`3B12504206`: MISSING** | *(would be A2WC411D)* | `3B12584206` | A2WC**411**I |
| 43 | `3B12504306` | A2WC**412**D | `3B12584306` | A2WC**412**I |

Two independent regularities pin it down:

1. **Digit 6 encodes transmission.** `3B1250…` = AT, `3B1258…` = MT. Every one of the seven family
   entries obeys this.
2. **Digits 7–8 encode calibration revision, and map 1:1 onto the xmlid**, with the trailing letter
   encoding transmission (`D` = AT, `I` = MT):
   `40 → A2WC400`, `41 → A2WC410`, `42 → A2WC411`, `43 → A2WC412`.

The MT column is complete (40/41/42/43). The AT column has 40/41/43 and is **missing exactly 42** -
which is the car's ID. Its manual-transmission twin, `3B12584206` → `A2WC411I`, **is present**. So
`3B12504206` is `A2WC411D`, the automatic build of a calibration this file already documents.

Every field of the surrounding family matches `car/build-sheet.md` exactly:

```
year 05 · market USDM · model Forester · submodel XT · transmission AT
memmodel SH7058 · flashmethod sti05
```

**Conclusion: a gap in a 2012 community definition file, not a foreign ECU.** One AT calibration
revision was never contributed. The absence is evidence about the *definition file's* coverage and
nothing whatsoever about the *car*.

### What this does and does not tell us

- **Does** confirm the ECU is a 2005 USDM Forester XT automatic unit, the right part, matching the
  build sheet, on the expected SH7058 / sti05 path.
- **Does NOT** prove the ROM is untuned. A COBB/EcuTek reflash commonly preserves the factory
  calibration ID, so a legitimate-looking ID is weak evidence against a prior tune, not proof.
  Hypothesis H1 (previously locked/married ECU) behind the seed/key read failure is **weakened but
  not eliminated**.
- **Does NOT** relate to the ROM read failure in any way. EcuFlash performs reads without consulting
  RomRaider definitions.

### Reproducing this

`ecuid_lookup.py` (this directory) re-derives the tables above from `ecu_defs.xml` using the
standard library only; no venv needed. It parses every `<romid>` block and reports the exact
match, the `3B125*` family, and all Forester entries across model years.

```bash
python3 car/ecu/defs/ecuid_lookup.py
```

Pass a different ID to check another ECU: `python3 car/ecu/defs/ecuid_lookup.py 3B12584206`
