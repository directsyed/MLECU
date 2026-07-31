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
- **KKL cable — NOT USED (Syed 2026-07-31: does not have one, judged unnecessary).** The
  identity cross-check it enabled is replaced by the read-stability check in §4.2, which is
  the stronger of the two anyway (it proves the clone reads deterministically, not merely
  that two tools agree on an id).
- **USB-to-serial adapter** for the wideband's BLUE serial-out wire — see §6.
- Windows laptop (ECUFlash/RomRaider are Windows-first; RomRaider is Java, runs anywhere, but
  ECUFlash is the flash tool and is Windows). AC power. A USB-A port or a known-good hub.

## 1. Software install
1. **ECUFlash** (openecu / tactrix distribution) — the flash + ROM-read tool.
2. **RomRaider** (romraider.com) — the logger + table editor (Java; install a JRE if prompted).
3. **Tactrix Openport 2.0 drivers** — from tactrix.com; the clone uses the same J2534 driver.
   After install, Windows Device Manager should show the Openport under Ports or a Tactrix node.

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
Openport + RomRaider Logger: Logger -> select the Openport -> connect. The bottom of the window
shows CAL ID / ECU ID. Expect a **3B12504206-family** id; note it exactly. This confirms the
A2WC411D assumption the whole toolchain is built on.
(The former KKL cross-check is dropped — see §0. Trust now rests on §4.2's read-stability
proof, which catches the failure that actually matters: a clone that corrupts what it reads.)

## 4. Validate the Openport clone BEFORE trusting it to flash
Only one cable is in play, so trust rests entirely on the clone proving itself:
1. **Read-stability check (Openport against itself) — THE trust test:** read the ROM TWICE
   with ECUFlash,
   save both, then on the T630:
   ```
   .venv/bin/python -m ecutune.cli --rom-diff read1.bin read2.bin
   ```
   `IDENTICAL` = the clone reads deterministically; that image is trustworthy. Any difference
   between two back-to-back reads = the clone is corrupting data — stop, do not trust it, and
   nothing gets flashed with it ever.
2. Flash trust is exercised much later (Phase C), still behind the sacred-backup ritual.

> ⚠ **EXPECT "Unknown ROM Image" in ECUFlash — and do NOT "fix" it.** If this ECU is the
> A2WC411D revision (likely: same family as the harvested ROM), ECUFlash will show *Unknown
> ROM Image* because **no community definition exists for 411D** — we proved this ourselves
> decoding the harvested copy. **The read is still complete and valid.** The forum thread for
> this exact situation (corpus doc 1036) "solved" it by flashing the A2WC412D sibling over the
> ECU — **we do NOT do that**: it's an unnecessary write of a different revision purely to make
> a GUI happy. Our `romread` tooling decodes 411D via sibling-def reconciliation; the editor
> can open it with the 410D def when editing day comes. Save the read, archive it, move on.

> ⚠ **RomRaider Logger may not recognize the ECU ID either.** The community logger defs cover
> `3B12504006/106/306` but not `...206` (verified in our SubaruDefs checkout). If the Logger
> refuses the ECU: open `RomRaider/logger/logger.xml`, find the `3B12504106` entry, duplicate
> it with your actual ECU ID (the SSM2 addresses are identical within the family — same
> reconciliation logic our romread uses). Keep the edited copy in the repo so it's versioned.

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

## 6. Wideband bring-up + the first idle log

**Spec (AEM X-Series manual, corpus doc 1069 p11 — quoted, not recalled):** BLUE WIRE = serial
out; "the format is simply the value followed by a carriage return and line feed, e.g.
`14.7\r\n`"; **9600 baud, 8 data bits, no parity, 1 stop bit**. Critically: *"the currently
selected display mode (lambda or AFR) will dictate what is output via serial."*

### 6.1 Set the gauge to AFR mode (do this first)
The serial stream is a bare number with no unit tag. RomRaider's AEM plugin labels whatever
arrives as AFR — so if the gauge is in **lambda** mode it streams `1.00` and the log records
"AFR 1.00", which is silently wrong. **Set the gauge to AFR.** It also matches the rest of the
toolchain (sim, scorer, corpus all speak AFR).

### 6.2 Prove the serial link BEFORE involving RomRaider
Terminal program (PuTTY / Tera Term), the adapter's COM port, **9600 8N1**. Engine off, key on.
You should see a number streaming per line. If you see nothing, or mojibake, the problem is the
data path (wrong COM port, wrong baud, or an RS-232-vs-TTL level mismatch on the blue wire) —
diagnose it HERE, where there is exactly one variable, not inside the logger.

### 6.3 Wire it into RomRaider Logger
RomRaider's external-sensor plugins are configured by `plugins.properties` in the RomRaider
settings folder (it is created on first Logger run and lists every detected plugin key). Set
the AEM plugin's port to your adapter's COM port, restart the Logger, and the wideband appears
as a selectable channel alongside the SSM2 ones.

### 6.4 Functional verification — three tests, in order
1. **Free air / key-on:** sensor heats (~30 s), then reads pegged lean. Proves the sensor lives.
2. **Warm closed-loop idle:** the ECU targets stoich, so the wideband should sit near **14.7**.
   This is the real test — an independent sensor agreeing with the ECU's own control target.
   Persistent deviation means a wiring/scaling problem, not a fuelling discovery.
3. **Snap throttle then decel:** must swing rich then lean and RETURN. A reading that never
   moves is a stuck/dead channel; catching that now prevents a whole tuning session built on
   a flat line.

### 6.5 The log itself
Channels (car/CLAUDE.md idle set): RPM, MAF g/s, AF correction, AF learning, injector duty +
pulsewidth, timing advance, knock + fine knock, coolant, IAT, battery voltage, wideband AFR.
Save as **CSV** -> feeds `ecutune`'s logparse directly (same format the sim emits).
Drop logs in `car/dataset/` and the ROM in `car/ecu/rom-archive/` — both are watched, and a
drop hard-preempts the benchmark pipeline so car work takes priority.

## 7. What NOT to do (hard rules, principles.md)
- No flash until: stock ROM archived (×3), battery charger on, hours of stable logging done.
- 93 octane only, always.
- Don't chase the injectors — OEM FXT side-feeds are matched to this ROM (a verified prior).
- Rule out a vacuum/boost leak (smoke test) BEFORE trusting any idle trim conclusion.
- Never trust a single read; never skip the archive; never flash on a hunch.
