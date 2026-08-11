# Context Handoff: 2005 Subaru Forester XT — ECU Tuning Toolchain Setup

**Date of session:** 2026-08-08 / 2026-08-09
**Purpose:** Transfer full context on two parallel, currently-unresolved hardware/software problems.

---

## 0. TL;DR — Current State

Two open problems, both partially diagnosed:

| # | Problem | Status |
|---|---------|--------|
| **A** | EcuFlash cannot read ROM from ECU — fails at seed/key exchange | **BLOCKED.** Two hypotheses remain: (1) previously-locked/tuned ECU, (2) clone cable lacks K-line reflash-mode support |
| **B** | AEM 30-0300 wideband serial output not reaching PC over RS-232/DB9 | **BLOCKED.** Wiring fully verified good. USB-to-serial adapter is prime suspect (chipset unknown) |

**Working:** RomRaider logger connects and streams live SSM2 data flawlessly (RPM, coolant temp, battery voltage). Entire toolchain is installed and launching.

---

## 1. Vehicle

- **2005 Subaru Forester XT (USDM)**
- **Drive-by-wire confirmed** — user physically verified no throttle cable at throttle body. This matters; it rules out the 16-bit K-line ECU theory.
- **ECU ID (read via SSM2): `3B12504206`**
- Expected memory model: **SH7058** (32-bit)
- Expected flash method: **sti05**
- User states never tuned "to my knowledge" — but car is used, so unverified.
- No green test-mode connectors needed (those are pre-2005 / non-DBW).

Owner also has a 2004 WRX wagon (not involved in this session).

---

## 2. Hardware Inventory

### OBD Interface
- **Washinglee clone Tactrix Openport 2.0**
- Serial number: `TAhJALxt`
- Device firmware: `1.17.4877` (unchanged throughout — no firmware flash occurred)
- Vendor-supplied J2534 DLL: `1.01.4341` (Aug 8 2014)
- Official Tactrix J2534 DLL: `1.02.4870` (Feb 3 2017) — loaded when running extracted official EcuFlash
- **User made an explicit decision: use the vendor's drivers only, per vendor instruction. Do not override this.**

### Wideband
- **AEM 30-0300 X-Series UEGO gauge**
- Blue wire = Serial/RS-232 output, **pin 5 of Connector A** (10-pin Power/IO harness)
- Gauge displays live, fast-updating AFR — confirmed healthy
- Wired: blue → DB9 female pin 2; ground → DB9 pin 5
- USB-to-serial adapter on **COM5**, 9600 8N1. **Chipset unknown — needs identification.**

### Crimping
- Contacts are **stamped open-barrel** D-sub contacts (NOT machined closed-barrel)
- Tool: **IWISS SN-28B**
- Crimps eventually verified good by continuity test (see §6)

---

## 3. Software Environment

**OS:** Windows 11 (EcuFlash's old Qt build misreports as "Windows 8" — ignore)

### Java
- **32-bit JRE 1.8.0_291** at `C:\Program Files (x86)\Java\jre1.8.0_291`
- 64-bit Java remains system default. **User explicitly refused to change PATH** — only one app needs 32-bit. Respect this.

### RomRaider
- Installed at `C:\Program Files\RomRaider`
- Launched via custom .bat (see §4) because the bundled `.exe` resolves to 64-bit Java
- Definitions at `C:\Users\Syed\Documents\RomRaider Defs\ecu_defs.xml`
  - **7,825,988 bytes, timestamp 2012** — this is the old `0.8.3.1b 10-07-09` forum archive (STANDARD units)
  - Logger def: `logger_STD_EN_v370.xml`
  - `cars_def.xml` must live in the RomRaider **install** folder (no setting points to it)

### EcuFlash — two copies present
| Version | Location | Notes |
|---|---|---|
| `1.44.4347` (2013 beta) | `C:\Program Files (x86)\OpenECU\EcuFlash\` | Vendor-supplied, **installed**. Uses vendor DLL 1.01.4341 |
| `1.44.4870` (2019) | `C:\Users\Syed\Downloads\ecuflash_1444870_win\` | Official Tactrix, **extracted only, never installed**. Portable. Carries its own DLL 1.02.4870 |

**Important:** the official EcuFlash was extracted with 7-Zip (it's an NSIS installer) specifically to avoid installing Tactrix drivers. Its bundled `drivers` folder was left untouched/deleted. Only `EcuFlash.exe` is run.

---

## 4. RomRaider Launcher (working solution)

RomRaider requires 32-bit Java. Two obstacles were solved:

1. **The `-jar` flag discards CLASSPATH**, so the `i18n` folder never loaded → `Can't find bundle for base name com.romraider.ECUExec` → immediate silent exit (`main()` returns if bundle is null).
2. Bundled `RomRaider.exe` resolves Java via PATH → finds 64-bit.

**Working `.bat`:**

```bat
@echo off
set "RR=C:\Program Files\RomRaider"
set "JRE32=C:\Program Files (x86)\Java\jre1.8.0_291"
cd /d "%RR%"
"%JRE32%\bin\java.exe" -cp "%RR%\RomRaider.jar;%RR%\i18n;%RR%\lib\common\*;%RR%\lib\windows\*" com.romraider.ECUExec
pause
```

Uses `-cp` + explicit main class instead of `-jar`. `setlocal`-style scoping means **no system environment changes**. Swap `java.exe` → `javaw.exe` to suppress the console.

---

## 5. Problem A: ECU Read Failure (PRIMARY)

### Symptom

Identical failure across every configuration tried. Representative log:

```
[20:32:03.998] kernel get version
[20:32:04.520] VIN read not supported
[20:32:05.045] SSM2 init
[20:32:05.190] SSM2 ECU ID is 3B12504206
[20:32:05.270] Requesting Seed...
[20:32:05.320] Sending Key [1]...
[20:32:05.978] interface close
[20:32:05.978] interface close
```

Then GUI dialog: *"An error has occurred, see log for details."*

**Interpretation:** SSM2 handshake succeeds and the ECU identifies itself. The ECU then **refuses the security unlock** for reprogramming mode. No kernel upload is attempted. **Nothing is ever written; the ECU is not modified. Retrying is safe.**

Note: `1.44.4870` logs `Sending Key [1]...` (indexed — it tries multiple keys). It sent key #1, was refused, and did not attempt a second.

### Ruled Out (do not re-test)

| Suspect | How eliminated |
|---|---|
| Cable/driver/wiring | RomRaider logger streams live SSM2 data perfectly |
| J2534 DLL registration | EcuFlash reads device firmware + serial on every attempt |
| Java bitness | Unrelated to EcuFlash (native app) |
| EcuFlash version | Failed identically on 1.44.4347 and 1.44.4870 |
| J2534 DLL version | Failed identically on 1.01.4341 and 1.02.4870 |
| Flash method | Tried both `sti05` and `sti04` — identical failure at same point |
| 16-bit vs 32-bit ECU | DBW physically confirmed → 32-bit SH7058 correct |
| Battery voltage | Was 11.2V (drained); recharged, now **12.5V key-on = normal** |
| Green test-mode connectors | Not applicable to 2005 DBW |
| Engine running during read | Confirmed engine OFF, key ON |

### Remaining Hypotheses

**H1 — ECU previously locked (EcuTek / COBB AccessPort marriage).**
The dominant community explanation for this exact log signature. A married AccessPort or EcuTek flash locks the ECU against other tools and changes comm protocols. Produces precisely this failure mode.
*Test:* get current definitions, then read CAL ID in RomRaider logger. Non-stock cal = confirmed.

**H2 — Washinglee clone lacks K-line reflash support.**
HPA's writeup on Openport alternatives states the Washinglee supports only *some* 32-bit ECUs and will not work with older 16-bit K-Line ECUs — implying a partial K-line implementation. 2005 Subaru reflash runs over K-line. SSM2 init (easy K-line) works; reflash-mode entry (demanding K-line) fails. Failure profile fits.
*Test:* borrow/try a genuine Openport 2.0, or bench read.

**Counter-evidence worth knowing:** an '04 Legacy GT owner reported this identical wall across 3 laptops, 2 *genuine* cables, and a healthy 12.7V battery. So it is not always the cable.

### Definitions Side-Quest (informative, NOT a fix)

EcuFlash does **not** use RomRaider defs to perform a read. This was diagnostic only.

- `3B12504206` is **absent** from the 2009 defs
- But siblings **are** present: `3B12504006`, `3B12504106`, `3B12504306`, plus `3B1258xxxx` variants
- → ECU is a normal same-family variant the 2009 defs predate. Not exotic.
- This is also why RomRaider logger reports **CAL ID = unknown** — inconclusive, not suspicious

**Definition source warning:** `github.com/Merp/SubaruDefs` stable branch is **stale (last commit 2012)** — downloading it yields the same file already in place. Use the ECU definitions link in the release notes at `github.com/RomRaider/RomRaider/releases` instead. Current RomRaider release is 1.1.0 (Nov 2025) and ships with no definitions bundled.

### Next Steps for Problem A

1. Pull current definitions from RomRaider releases page → recheck CAL ID in logger. **Settles H1.**
2. If CAL ID is stock → post log to RomRaider forum naming the Washinglee, noting SSM2 logging works and only reflash entry fails. Seek anyone who has read an sti05 with that cable.
3. If H2 confirmed → genuine Openport, or bench read with ECU removed.

---

## 6. Problem B: AEM Wideband Serial (SECONDARY)

### Symptom
No data arrives on COM5. RomRaider AEM plugin shows nothing; raw PowerShell read returns empty.

**Raw read test used:**
```powershell
$p = New-Object System.IO.Ports.SerialPort COM5,9600,None,8,one
$p.Open(); Start-Sleep -Seconds 10; $p.ReadExisting(); $p.Close()
```
*(RomRaider must be fully closed first — its plugin holds COM5 exclusively and throws "Access to the port 'COM5' is denied.")*

### Verified Good
- Gauge powered, displaying live fast-updating AFR
- Blue wire confirmed = serial out, Connector A pin 5 (per AEM manual)
- Continuity: blue wire → DB9 pin 2 ✓
- Continuity: AEM black ground → DB9 pin 5 ✓
- COM5 exists and opens without error
- Baud/settings correct: 9600, 8N1

### The Pin 2 ↔ Pin 5 "Short" — RESOLVED, NOT A FAULT
Continuity between DB9 pin 2 and pin 5 initially beeped. **This disappears when Connector A is unplugged from the gauge.** The path runs *through the gauge's internal output driver to its internal ground* — expected behavior, not copper-on-copper. Do not chase this again.

### Prime Suspect
**The USB-to-serial adapter.** A documented failure with this exact gauge: a user with identical wiring (blue → RXD, correct settings) got unusable output until replacing a non-compliant adapter (DSD TECH brand named specifically). Many cheap dongles are TTL internally or don't meet RS-232 levels.

*Action:* identify chipset via Device Manager → Ports (COM & LPT) → Properties → Details → Hardware IDs. **FTDI or Prolific = safe. Unbranded = replace.**

Secondary note: some USB adapters require pin 3 connected as well for handshake, per one forum report.

### ADDENDUM 2026-08-11 — prime suspect ELIMINATED, hypothesis moved

Chipset identified via `Get-PnpDevice -Class Ports -PresentOnly`:

```
FriendlyName : USB Serial Port (COM5)
InstanceId   : FTDIBUS\VID_0403+PID_6001+A9K1P84WA\0000
```

`0403:6001` = **genuine FTDI FT232R**, with a properly programmed serial (`A9K1P84WA`) rather
than the blank/duplicated pattern typical of counterfeits. **The "cheap non-compliant adapter"
hypothesis is dead. Do not buy a replacement adapter on the strength of §6 as originally written.**

**The hypothesis that replaces it: RS-232 vs TTL signal LEVEL CLASS, not chipset.**

FT232R is a **TTL-level** part with no RS-232 transceiver of its own. True RS-232 cables (FTDI
US232R, Chipi-X) add a separate level-shifter; cheap cables solder the FT232R's bare TTL pins
directly to a DB9 shell. **Both enumerate identically** — same VID, same PID, same friendly name.
Device Manager cannot distinguish them.

That distinction is decisive here because of polarity. The 0.5 V average (Corrections Log #3)
implies the AEM line **idles LOW and pulses up**: at ~10 Hz with a short burst the line is idle
most of the time, so standard TTL (idle HIGH at 5 V) would have averaged near 5 V, not 0.5 V.
Idle-low 0→5 V is RS-232 *polarity sense* without the negative rail.

| adapter class | behaviour with an idle-low 0→5 V input | outcome |
|---|---|---|
| true RS-232 (transceiver) | thresholds ~+1.4 V and inverts: 0 V → mark/idle, +5 V → space | decodes correctly |
| bare TTL on a DB9 shell | expects idle HIGH, sees a permanently low line | continuous break → **zero valid bytes** |

The bare-TTL row reproduces the observed symptom exactly (port opens, no data).

**Discriminating test (queued):** adapter in USB, nothing else attached; DMM black on DB9 pin 5,
red on **pin 3** (the adapter's own TX output, self-driven so it idles with nothing connected).
- **−5 to −12 V** → true RS-232 → this hypothesis also dies; wiring becomes the suspect.
- **+3.3 / +5 V** → bare TTL in a DB9 shell → polarity mismatch confirmed.

**If TTL: the fix is free, not a purchase.** FT232R supports per-signal inversion in EEPROM via
FTDI's FT_PROG utility — inverting RXD makes the chip accept the AEM polarity in hardware.

**Wiring caveat that the continuity test cannot clear.** A female DB9 numbers mirror-image to a
male when viewed from the wiring/contact-insertion side. A continuity check performed under the
same mirrored assumption used when wiring is self-consistent and proves nothing absolute — it
confirms blue reaches *a* pin repeatably, not that the pin is 2. Verify against the molded numbers
in the shell. (Mirrored, the pin-2 position reads as pin 4 = DTR and pin 5 as pin 1 = DCD, which
would also produce silence.)

**Follow-up test after the above, not in parallel:** `$p.ReadExisting()` returns a decoded
*String*, so a stream of NUL bytes — precisely what a break condition delivers — renders as
visually empty. "No data" may actually be "nulls arriving." Re-test by counting `$p.BytesToRead`
and hex-dumping raw bytes rather than printing a string. Non-zero count with 0x00 bytes = signal
present but mis-framed (supports the polarity hypothesis); a true zero count = nothing arriving at
all (supports the wiring hypothesis).

**Note on baud:** wrong baud produces *garbage bytes*, not *zero bytes*. The observed symptom does
not implicate the 9600 8N1 setting.

### Measurement Gotcha (IMPORTANT — I gave bad advice here)
I told the user to expect **−5 to −12V** on the blue wire (true RS-232 idle). They measured **0.5V** and we treated it as a fault.

**This was wrong.** AEM's "RS-232" output is logic-level, idling at 0V and pulsing to 5V in short bursts at ~10Hz. A multimeter averages this to roughly 0.5V. **The 0.5V reading is consistent with a correctly functioning transmitter.** Do not interpret it as a failure.

---

## 7. Windows Driver Signature Blocking (SOLVED — but recurs every boot)

### Symptom
Cable enumerated with **Code 39**: *"Windows cannot load the device driver... An Application Control policy has blocked this file."*

### Diagnosis
CodeIntegrity event log (`Microsoft-Windows-CodeIntegrity/Operational`):
```
Event 3077: Code Integrity determined that a process (System) attempted to load
\...\drivers\openport.sys that did not meet the Authenticode signing level
requirements or violated code integrity policy
(Policy ID:{8f9cb695-5d48-48d6-a329-7202b44607e3})
```
Policy `{8f9cb695...}` = **Microsoft Windows Cross Certificates for Code Integrity Exceptions Policy.**

**Meaning:** the driver IS signed, but with a legacy cross-signing certificate Microsoft has retired. Vendor files are dated 2022. Not the vulnerable-driver blocklist.

Also checked and **ruled out**: Memory Integrity (already OFF), Smart App Control (already OFF).

### Working Workaround (per-boot, not permanent)
1. Start → power → **Shift + Restart**
2. Troubleshoot → Advanced options → **Startup Settings** → Restart
3. Press **7** — Disable driver signature enforcement

**Must be repeated on every reboot.** Driver uninstall/reinstall alone did NOT fix it; the enforcement bypass did.

*Rejected alternative:* the newer official Tactrix driver (from the extracted `ecuflash_1444870_win\drivers\openport 2.0\`, likely signed with a modern cert) would probably load without the bypass — **user declined, choosing to keep vendor drivers. Respect this.**

---

## 8. Clone Cable Brick Risk (context for future decisions)

Mechanism: `op20pt32.dll` carries the firmware image and checks the cable's firmware version, flashing a newer one on mismatch. Blacklisted clone serials get their flash erased and write-protected at this point.

**Rules being followed:**
- Never accept a firmware update prompt in EcuFlash
- Keep vendor's driver/DLL where possible
- Device firmware `1.17.4877` has remained **unchanged** through every attempt — no flash has occurred

Note: running the extracted official EcuFlash *did* load its own DLL (1.02.4870) rather than the vendor's. Firmware was unaffected, but be aware the portable copy is not DLL-neutral. One report exists of clones bricking merely from opening EcuFlash and clicking test write.

---

## 9. DB9 Crimping Reference (background — resolved)

Original problem: pins pulled out by hand.

**Root cause:** tool geometry mismatch. Contacts are **stamped open-barrel**, needing a rolling die that curls the wings inward (B-crimp). A ferrule/barrel crimper only squashes them.

**Correction to note:** I initially recommended an M22520/AFM8 4-indent tool. **That was wrong** — that's for machined closed-barrel contacts. A photo revealed open-barrel stamped contacts. Correct tools: Engineer PA-09 or IWISS SN-28B.

**SN-28B technique notes:**
- Wings must face the die's rounded "M" humps so they roll inward
- Small indent = conductor wings; larger indent = insulation wings
- D-sub contacts are longer than Dupont pins and don't self-align — verify wing pairs sit under matching humps
- Pre-pinch splayed wings before inserting
- Cheap units often release early; there's a pawl adjustment near the handle pivot

Final crimps verified good by continuity test.

---

## 10. Corrections Log (errors I made — don't repeat them)

1. **M22520/AFM8 recommendation** — wrong contact type. Contacts are open-barrel stamped.
2. **"Running extracted EcuFlash won't change the DLL"** — false. It loaded its own 1.02.4870.
3. **"RS-232 idle should read −5 to −12V"** — false for this gauge. AEM output is logic-level; 0.5V average is normal.
4. **"cars_def.xml goes alongside ecu_defs.xml"** — ambiguous and misleading. It must be in the RomRaider *install* folder specifically.
5. **Claimed the WRX/STi and FXT rows differ in memory model** — they don't; both are sti05/SH7058.

---

## 11. User Working Preferences

- **One thing at a time.** Explicitly requested this. Multiple parallel options overwhelm and slow progress.
- Direct, casual, no over-explanation.
- Experienced hands-on mechanic — comfortable with multimeters, back-probing, scan tools, wiring. Do not over-explain automotive fundamentals.
- Pushes back effectively and correctly when guidance is wrong. Take the pushback seriously.
- Makes deliberate decisions (vendor drivers only; no PATH changes) and expects them respected rather than re-litigated.
- Prefers verifying via command line; comfortable in PowerShell.

---

## 12. Immediate Next Actions

**Problem A (ECU read):**
1. Download current definitions from `github.com/RomRaider/RomRaider/releases`
2. Point Definition Manager at new `ecu_defs.xml`
3. Verify `3B12504206` now present: `Select-String -Path "<path>" -Pattern "3B12504206"`
4. Reconnect logger → read CAL ID → compare against stock USDM '05 FXT
5. If stock → escalate to RomRaider forum with full log + "Washinglee" named

**Problem B (wideband serial):**
1. Identify USB-serial adapter chipset in Device Manager
2. If not FTDI/Prolific → replace adapter, retest raw PowerShell read
3. If data arrives raw → restart RomRaider (plugin port settings only apply at startup), verify AEM parameter is ticked in the **External** tab, not just configured in Settings

**Unrelated but flagged:** if the user ever reports ~12.5V with the engine *actually running*, that indicates an alternator/charging fault. Current 12.5V reading was key-on, engine-off — normal.
