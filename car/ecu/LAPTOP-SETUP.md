# Laptop setup — RomRaider / ECUFlash / Openport for the 2005 FXT (A2WC411D)

The garage laptop's job: **log** the car (SSM2 over K-line) and **read/flash** the ECU
(Openport + ECUFlash). This guide is written against THIS car's verified facts — 32-bit USDM
2005 Forester XT ECU, internal id family **A2WC411D** (between the community-defined A2WC410D
and A2WC412D), 4EAT. Do every step in order; the "validate before trust" steps are not optional.

> **Standing safety doctrine (car/CLAUDE.md, principles.md §8):** the stock ROM is SACRED —
> read + archive in ≥3 places before ANY write. Battery charger on the car, laptop on AC,
> hours of stable logging before the first flash. 32-bit Subaru ECUs flash reliably and have
> recovery paths; discipline makes brick risk negligible.

---

## 0. What you have / need
- **Openport 2.0 (Rev-E clone) — ACQUIRED.** Flashes + logs (J2534). Validate it (§4) before trust.
- **KKL "VAG-COM 409.1 USB" cable — GENUINE FTDI FT232RL only.** Reject CH340/PL2303 and any
  ELM327/OBDLink (protocol interpreters cannot speak raw SSM2). ~$20. Independent read path +
  logging fallback. *Confirm you have this; if not, order the FTDI one.*
- Windows laptop (ECUFlash/RomRaider are Windows-first; RomRaider is Java, runs anywhere, but
  ECUFlash is the flash tool and is Windows). AC power. A USB-A port or a known-good hub.

## 1. Software install
1. **ECUFlash** (openecu / tactrix distribution) — the flash + ROM-read tool.
2. **RomRaider** (romraider.com) — the logger + table editor (Java; install a JRE if prompted).
3. **Tactrix Openport 2.0 drivers** — from tactrix.com; the clone uses the same J2534 driver.
   After install, Windows Device Manager should show the Openport under Ports or a Tactrix node.
4. **FreeSSM** (optional but recommended) — dead-simple SSM2 sanity tool for the KKL path; reads
   the ECU ID and live params with zero configuration. Great first-contact test.
5. **FTDI VCP driver** for the KKL cable (ftdichip.com) — only if Windows doesn't auto-install it.

## 2. Definitions — point the tools at OUR verified defs
The repo already holds the full SubaruDefs tree used to decode this exact ROM:
`ml/data-pipeline/data/raw/SubaruDefs/` (ECUFlash/ + RomRaider/). Copy or point at:
- **ECUFlash defs:** `.../SubaruDefs/ECUFlash/subaru metric/` (and `subaru standard/`). In
  ECUFlash → Options → set the definition folder here.
- **RomRaider editor defs:** `.../SubaruDefs/RomRaider/ecu/` → RomRaider → Settings → Definitions.
- **RomRaider logger defs:** `.../SubaruDefs/RomRaider/logger/` → the `logger.xml` → Settings →
  Logger Definition. This is what maps SSM2 addresses to named channels.
> These are the SAME defs `ecutune/romread` reconciles against, so the laptop and the T630
> speak the identical table vocabulary — no drift between what you edit and what our tools read.

## 3. First contact — READ THE ECU ID (no flashing yet)
Two independent paths; do BOTH and compare (this is §4's validation, done as first contact).
1. **KKL + FreeSSM:** cable to OBD-II + laptop, key ON engine OFF, FreeSSM → Engine → it prints
   the ECU ID. Expect a **3B12504206-family** id. Note it exactly.
2. **Openport + RomRaider Logger:** Logger → select the Openport → connect. Bottom of the window
   shows CAL ID / ECU ID. Note it.
- **They must match.** Matching ids across two independent cables/tools = both are talking to the
  ECU honestly, and confirms our A2WC411D assumption. Mismatch = stop, diagnose (wrong def,
  flaky clone, cable chip) before trusting anything.

## 4. Validate the Openport clone BEFORE trusting it to flash
The clone reads fine for logging (§3). Before it earns flash trust:
1. **Read the ROM with ECUFlash** (read-only): ECUFlash → Read → save as `.bin` AND `.srf`.
2. **Cross-check the read:** if the KKL path can also produce a read (or via a second Openport
   read), confirm identical ROM ID and, ideally, identical bytes. A clone that reads a *stable,
   repeatable, ID-correct* image is trustworthy for the read; flash trust is only exercised much
   later (Phase C), still with the sacred-backup ritual first.

## 5. THE FIRST ROM READ — archive + verify (the sacred step)
1. Battery charger on the car, laptop on AC.
2. ECUFlash → Read → save. You now hold the car's actual factory calibration.
3. **Archive in ≥3 places, immediately, before anything else touches it:**
   - `car/ecu/rom-archive/<date>-firstread-<ecuid>.bin` (+ `.srf`)
   - `data-backups/` (the DB-snapshot folder; belt-and-suspenders)
   - **Off-machine** — a USB stick or cloud. The original ROM is irreplaceable.
4. **Verify with our own tooling** (from the repo, `car/` venv):
   ```
   cd ~/Shared/"Computing Projects"/MLECU/car
   .venv/bin/python -m ecutune.cli --rom-report /path/to/firstread.bin
   ```
   - `--rom-report` decodes the semantic tables and prints the internal id — expect **A2WC411D**.
     (`ecutune.cli` = our offline tuning-layer CLI; `--rom-report` = read+cross-validate+print.)
5. **Is it really stock? — the diff that answers it:**
   ```
   .venv/bin/python -m ecutune.cli --rom-diff /path/to/firstread.bin \
       ../ml/data-pipeline/data/raw/roms/romraider/3B12504206_A2WC411D.bin
   ```
   - `--rom-diff A B` = table-level + byte-level comparison of your read against the harvested
     stock ROM. **"IDENTICAL"** = confirmed bone-stock, every assumption downstream holds.
     Any table differences = a prior owner tuned it; the report names exactly which tables and
     cells changed (mapped to semantic names) — that becomes the real starting point, and it's
     far better to know now than to discover it mid-tune. Exit code 2 means "they differ" (so
     it's scriptable).

## 6. Logging setup (once wideband is installed)
- RomRaider Logger, Openport (or KKL) connected, the logger def loaded (§2).
- Log the idle channel set (from car/CLAUDE.md): RPM, MAF g/s, AF correction, AF learning,
  injector duty/pulsewidth, timing, knock/fine-knock, coolant, IAT, battery voltage, wideband
  AFR (the AEM analog input — wire per corpus doc 5774's rear-O2-tap pattern; TGV Left/Right or
  rear-O2 wire → AEM 0-5V, scaled in the logger def).
- Save logs as CSV → they feed `ecutune`'s logparse directly (same format the sim emits).

## 7. What NOT to do (hard rules, principles.md)
- No flash until: stock ROM archived (×3), battery charger on, hours of stable logging done.
- 93 octane only, always.
- Don't chase the injectors — OEM FXT side-feeds are matched to this ROM (a verified prior).
- Rule out a vacuum/boost leak (smoke test) BEFORE trusting any idle trim conclusion.
- Never trust a single read; never skip the archive; never flash on a hunch.
