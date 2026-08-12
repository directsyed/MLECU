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

### ADDENDUM 2026-08-11 (2) — pin 3 = −5.74 V: level-class hypothesis ALSO eliminated

Measured **−5.74 V DC, consistent**, on DB9 pin 3 → pin 5, adapter powered by USB with nothing
else attached. Only a real RS-232 transceiver produces a negative idle rail; a bare FT232R TXD pin
would have sat at +3.3/+5 V. **The adapter is the correct electrical class.**

Consequence — the polarity chain now checks out end to end. An RS-232 receiver thresholds around
+1.4 V and inverts, so the AEM's 0 V idle reads as mark and its +5 V burst reads as space/start
bit. Nothing in the level or polarity story explains the silence.

**Two of three original suspects are now dead** (cheap chipset; TTL-vs-RS-232 class). Remaining,
ranked:

1. **Absolute pin identification on the female shell** (the mirrored-numbering caveat above).
   Promoted to leading suspect by elimination. Note the pin-3 measurement has now *independently
   confirmed the numbering on the adapter's male connector*, so the adapter end can be trusted as
   a reference for any further test.
2. **Unproven read method.** `ReadExisting()` has never been demonstrated to work on this setup at
   all. "No data" and "my read code doesn't do what I think" are not yet distinguished.
3. **Marginal mark level (secondary, keep on the list).** The AEM drives 0 V for mark, which is
   inside RS-232's undefined dead zone (spec wants −3 to −15 V); +5 V for space is in spec. Real
   MAX232-class receivers threshold near +1.4 V so 0 V is read as mark reliably in practice, but a
   receiver with an unusual threshold or failsafe biasing could refuse it.
   **Ironic fallback if this proves to be the cause:** a *TTL* adapter with RXD inverted in
   FT_PROG reads a 0/5 V idle-low signal natively and cleanly, and would be the more robust
   receiver for this gauge than the compliant RS-232 one.

**Discriminating test (queued): LOOPBACK.** Jumper DB9 pin 2 to pin 3 on the adapter's male
connector (safe — TX into RX is what a null modem does), then write and read in PowerShell. This
bisects the whole problem: it exercises the adapter, driver, COM port, baud settings *and the read
code* in one shot, with the car and gauge entirely out of the picture.

- **Echo returns** → the entire PC side is proven good, including the read method. The fault is
  then necessarily in the harness wiring or the gauge output, and suspect 1 becomes the target.
- **Echo silent** → the fault is PC-side (driver/port/code) and the harness was never implicated.

### ADDENDUM 2026-08-11 (3) — LOOPBACK PASSES: the entire PC side is proven good

Pin 2↔3 jumper on the adapter, write-then-read in PowerShell: **echo returned.** Adapter, FTDI
driver, COM port, 9600 8N1 settings and the read method are all confirmed working end to end.

**Suspect 2 (unproven read method) is eliminated.** With the chipset, the level class, the port
config and the read code all cleared, **the fault is necessarily downstream of the adapter** — the
hand-crimped DB9 shell, the harness wiring, or the gauge output itself.

**Instrument gotcha worth keeping.** The first loopback attempt appeared to produce no output at
all. Cause: `ReadExisting()` returning an empty string prints as *literally nothing* in PowerShell,
so "test failed" and "command produced no output" are visually identical. Any serial test on this
project must print an explicit byte COUNT (`$p.BytesToRead`, captured *before* `ReadExisting()`
drains the buffer) and bracket the text (`"[$s]"`) so an empty result renders visibly as `[]`.
A silent negative result is not a result.

### Next test — BYPASS THE CRIMPED SHELL

Leading suspect is now the hand-crimped female DB9, whose absolute pin identification has never
been established independently (the continuity check was self-consistent with the assumption used
when wiring). The adapter's male connector *is* now a trusted numbering reference, courtesy of the
−5.74 V reading on pin 3.

Test: with the gauge powered, connect the AEM blue wire directly to the adapter's **pin 2** and the
AEM black to **pin 5** using jumper leads clipped to the male pins — the crimped shell removed from
the circuit entirely. Then listen (no write) for ~5 s.

- **Data arrives** → the crimped DB9 shell is miswired. Rebuild it against the molded numbers.
- **Still nothing** → the shell is exonerated and the remaining candidates are the gauge output
  itself and suspect 3 (marginal 0 V mark level, whose fallback fix is the FT_PROG-inverted TTL
  adapter noted above).

### ADDENDUM 2026-08-11 (4) — ⚠ COM5 NO LONGER ENUMERATES; adapter status UNKNOWN

**The bypass test was never actually performed.** Two faults, in sequence:

1. The USB adapter was unplugged for the earlier "empty `$n`" run — which fully explains that blank
   (`BytesToRead` on an unopened port leaves the variable unset) and closes that mystery.
2. With USB reconnected, the port is now **gone**:
   `ERROR: Exception calling "Open" with "0" argument(s): "The port 'COM5' does not exist."`
   Device Manager no longer lists COM5 at all.

**This is a different class of failure from everything preceding it.** All prior symptoms were
"port exists, no data." This is "no port" — the FT232R is not enumerating on USB, which is
*upstream* of the adapter/driver/wiring layers already cleared.

**Onset correlates with clipping bare wires onto the D-sub pins with the shell bypassed.** Two
plausible mechanisms, both consequences of that test method:
- DB9 pins are on 0.1" centres; bare wire or a clip bridges neighbours trivially, and one
  neighbour (pin 3) sits at −5.74 V.
- **AEM Connector A is the POWER/IO harness and carries 12 V.** 12 V onto a D-sub pin or the
  adapter shell will destroy an FT232R.

**Not yet written off.** Windows reassigns COM numbers, and a healthy adapter that re-enumerated as
e.g. COM7 produces this exact error message.

**Diagnostic queued:** re-seat into a different USB port, then
`Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "*VID_0403*" } | Format-List
FriendlyName, Status, Class, InstanceId` — note the `-Class Ports` filter is deliberately dropped,
since a failed device leaves that class and would be hidden by it.
- `Status : OK` + a new COM number → healthy, retarget the script.
- `Status : Error` → enumerating, driver won't attach; usually recoverable.
- **no output** → not responding on USB; adapter likely dead.

**Method lesson for the rebuild.** Do not clip bare leads onto live D-sub pins next to a 12 V
harness. Break out to the two signals with an insulated pigtail, or verify the intended pin pair in
isolation with the gauge unpowered, before energising anything.

**If a replacement is needed the spec is now precisely known:** a true RS-232 adapter with a real
transceiver (negative idle rail on TX), which is what the −5.74 V reading proved the dead one was.

### ADDENDUM 2026-08-11 (5) — re-seat failed; damage mechanism re-weighted

Different USB port, no chime, no COM port. (Chime alone is weak evidence — system sounds may be
off; the `Get-PnpDevice` output is what counts.) Whether the gauge was powered during clipping is
**unknown and not retroactively determinable.**

**Re-weighting of the two damage mechanisms, and it matters:**

- **Pin bridging — now considered UNLIKELY to be fatal.** EIA-232 requires a compliant driver to
  survive a short to any other conductor in the cable, and real transceivers are current-limited
  accordingly. Bridging pin 3 (−5.74 V) to a neighbour should be survivable.
- **12 V contact from Connector A — the only plausible fatal path,** and it requires the gauge to
  have been powered.

**Consequence:** if the gauge was unpowered, no mechanism in evidence should have destroyed the
adapter, which raises the prior on a **laptop-side** fault (USB port, driver state) over a dead
chip. Do not buy a replacement until Step 6 discriminates.

**Diagnostic queued (Step 6): try the adapter on a DIFFERENT COMPUTER.** Enumeration happens below
the driver layer, so a machine that has never had FTDI drivers will still show something if the
chip is alive. Widened filter:

```powershell
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "*VID_0403*" -or $_.Status -ne "OK" } | Format-List FriendlyName, Status, Class, InstanceId
```

The `-or $_.Status -ne "OK"` clause is **load-bearing**: a chip with damaged USB signalling often
still enumerates but fails its descriptor request, and Windows lists that as *"Unknown USB Device
(Device Descriptor Request Failed)"* carrying **no vendor ID** — invisible to a `VID_0403` filter.
Partially-alive and wholly-absent are different diagnoses; the narrow filter conflates them.

- `VID_0403` + `Status : OK` on the other machine → adapter healthy, fault is laptop-side.
- `Unknown USB Device` / `Status : Error` appearing only on plug-in → chip alive, USB interface damaged.
- nothing changes on plug/unplug → drawing nothing, dead.

Independent secondary check: put any other USB device in the laptop port that was in use, to
establish whether that port survived.

### ADDENDUM 2026-08-11 (6) — RESOLVED: adapter was never damaged; a reboot restored it

**Laptop restart → the adapter enumerates again.** The cause was Windows USB/driver enumeration
state, not physical damage. **No hardware was harmed and no replacement is needed.**

This vindicates the Addendum-(5) re-weighting: the first-principles argument (EIA-232 requires
drivers to survive a short to any other conductor, so pin bridging should not be fatal; only 12 V
contact was a plausible kill path) correctly predicted the adapter was alive, and holding the
purchase was right. **Lesson: on a USB-serial device that vanishes, reboot before concluding
damage.** Enumeration state is sticky and a re-seat into another port does not clear it.

Watch for COM renumbering after the reboot — `"The port 'COM5' does not exist"` now means a
renumber, not a dead device. Read the new number from the `FriendlyName` field of the
`Get-PnpDevice` output and substitute.

### Bypass test — SAFE PROCEDURE (supersedes the bare-clip method)

The gauge **must be powered and displaying AFR** during the test; it is silent otherwise. But make
every connection cold:

1. Gauge unpowered (key off), USB adapter unplugged from the laptop.
2. Connect **black → pin 5 FIRST**, then **blue → pin 2**. Ground before signal, so the common
   reference exists before the signal wire does and the signal has no reason to seek a return path
   through the electronics.
3. Visually confirm nothing bridges to a neighbouring pin.
4. Plug in USB. 5. Power the gauge, let AFR settle. 6. Run the listen command.

**Use insulated female Dupont jumpers over the male D-sub pins, not bare alligator clips** — they
are insulated to the contact and remove the bridging risk on 0.1" centres.

**Run the laptop on BATTERY, not mains.** Tying laptop ground to car ground via pin 5 is normal
(the Openport already does this through the OBD port), but adding a mains earth invites a ground
loop, and this signal is already at marginal RS-232 mark levels.

---

## ★ PROBLEM B SOLVED — 2026-08-11: the crimped DB9 shell was the fault

**Bypass test result:**

```
bytes waiting : 301
text received : [99.9\r\n 99.9\r\n ... ]   (~50 samples in 5 s)
```

**The serial link works.** ~50 samples over 5 s = the gauge's ~10 Hz rate, and the `99.9\r\n`
framing is the AEM ASCII protocol decoding cleanly at 9600 8N1. With the hand-crimped female DB9
removed from the circuit and the gauge wired straight to adapter pins 2/5, data flows.

**Root cause: the hand-crimped DB9 shell.** Its absolute pin identification was never
independently established — the original continuity check was self-consistent with the mirrored
numbering assumed while wiring, so it confirmed blue reached *a* pin repeatably, not that the pin
was 2. See the mirrored-numbering caveat in Addendum (1).

**Elimination sequence that got here, for the record:** cheap-chipset (killed by VID_0403 genuine
FTDI) → TTL-vs-RS-232 level class (killed by −5.74 V on pin 3) → read method / PC side (killed by
the pin 2↔3 loopback echo) → adapter damage (killed by a reboot) → **crimped shell (confirmed by
bypass).** Every original §6 hypothesis was wrong; the fault was in the connector Syed built.

### `99.9` is EXPECTED here — not a fault

Real gasoline AFR spans ~8–20. **99.9 is an out-of-range sentinel.** With the engine off the
sensor sits in ambient air, reads infinitely lean, and pegs. This result *confirms* a healthy
gauge; it simply is not measuring combustion yet.

### Remaining steps before RomRaider

1. **Engine running, sensor at temperature, re-run the same one-liner.** Expect values near ~14.7
   at warm closed-loop idle. **Cross-check the serial value against the gauge face** — if the face
   shows a sensible AFR while the stream still reads 99.9, that is a *different* fault (format or
   scaling) and must be resolved before proceeding.
2. **Confirm the wideband sensor is actually installed in the exhaust bung.** The build notes
   record an unconnected O2 bung; a sensor in free air reads 99.9 indefinitely regardless of
   runtime.
3. **Only then RomRaider** — plugin port settings apply at startup only, and the AEM parameter
   must be ticked in the **External** tab, not merely configured in Settings. Going to RomRaider
   before step 1 stacks an unverified stream under an unverified plugin config: two unknowns at
   once, which is precisely the trap that cost this session.
4. **Rebuild the DB9 shell** against the molded pin numbers before `CAPTURE-PROTOCOL.md`. Dupont
   jumpers are adequate for a stationary test, **not** for the real three-pull capture.

---

## ⚠ 2026-08-11 — LOGGER FROZEN after the reboot (open)

**Symptom:** RomRaider displays the ECU ID and a green "reading" indicator, but **every field is
frozen** — ECU parameters *and* the AFR field, which now shows a real value instead of nothing.
Logging worked ~30 min earlier.

**Do not trust the green dot or the displayed ECU ID.** RomRaider will show a cached ECU ID and a
stale connected state while comms are dead; a stalled logger thread holds every field at its last
value, which is exactly this symptom.

### H1 (leading) — the driver-signature bypass did not survive the reboot

**The laptop was restarted to recover the FTDI adapter** (Addendum 6). §7 of this document records
that the `openport.sys` bypass **must be repeated on every boot** — a normal restart re-enables
enforcement and the driver stops loading (Code 39). That reboot is the largest change between
"logging fine" and "frozen", and it was performed for an unrelated reason, which is exactly how
this class of regression sneaks in.

*Check:* `Get-PnpDevice -PresentOnly | Where-Object { $_.Status -ne "OK" } | Format-List
FriendlyName, Status, Class, InstanceId` → Openport with `Status : Error` = Code 39 confirmed.
*Fix:* Shift+Restart → Troubleshoot → Advanced options → Startup Settings → Restart → **7**.

### H2 — the AEM external plugin is blocking the logger thread

RomRaider polls external datasources on the same thread as ECU parameters. A **blocking serial
read** — which is what occurs if the gauge stops transmitting mid-session (ignition off, gauge
unpowered) — stalls that thread and freezes *every* field at once, ECU parameters included. Also
fits the symptom exactly, and explains why the AFR field holds a real-looking value: it was read
successfully once, then the thread stalled.

*Test:* relaunch with the AEM parameter **unticked** on the External tab. ECU logging returning =
H2 confirmed.

### Cold-start logging procedure (canonical — follow in order)

1. Driver-signature bypass active (**after every reboot**).
2. Openport enumerates clean, no Code 39.
3. **Close every PowerShell window** — they hold COM5 exclusively and the AEM plugin cannot open a
   port another process owns.
4. **Gauge powered and streaming BEFORE RomRaider launches** — the plugin opens the port and reads
   its settings only at startup.
5. Ignition on; engine running if a real AFR is wanted rather than the 99.9 sentinel.
6. Launch the 32-bit `.bat` (§4).
7. Logger tab → tick ECU parameters.
8. **External tab → tick the AEM parameter.** Configuring it in Settings alone does nothing.
9. Confirm values are moving before relying on anything.

**Standing lesson:** any reboot silently disarms the Openport. Make step 1 the first check for
*every* "logging stopped working" report from now on.

### Correction 2026-08-11 — H1 ELIMINATED by Syed; timing REINFORCES H2

Syed confirms he **did** launch with the signature-enforcement bypass active. **H1 is dead.**

He also reports the freeze **began BEFORE the AFR serial fix.** This does *not* exonerate the
plugin — it fits H2 better. If the AEM parameter was ticked on the External tab, every logger start
had the plugin opening COM5 and waiting on a port that was first silent and later **absent
entirely** (Addendum 4). A blocking read against a dead port stalls the logger thread, and that
would begin failing the moment the port vanished — i.e. before the fix, exactly as observed.

### Next: STOP INFERRING, READ THE STACK TRACE

The §4 launcher runs `java.exe` (not `javaw.exe`) and ends in `pause`, **so a console window is
open behind RomRaider** and any exception on the logger thread has already printed there with a
full trace. This has not been looked at once this session.

**Do not restart the logger before reading it — restarting clears the evidence.**

| what the console shows | reading |
|---|---|
| `SerialPort` / `gnu.io` / `RXTX` / `javax.comm` exception, or anything naming COM5 | AEM plugin stalled the thread — **H2 confirmed** |
| `J2534` / `op20pt32` / `openport` exception | ECU side dropped despite the driver loading |
| repeated timeout/checksum warnings, no exception | comms alive, ECU not answering → physical/electrical |
| nothing at all | no code failed → freeze is upstream of software; electrical leads |

### H3 (new) — battery sag

Extended key-on, engine off, with a **wideband sensor heater drawing 1–2 A continuously**. This
battery has form: recorded at 11.2 V earlier in the build before recharging (§5). A sag toward
~11 V makes the ECU unreliable on the K-line well before anything else looks wrong, and would
produce a **silent stall with no Java exception** — which is precisely why the console must be read
first: exceptions present = software; exceptions absent + sagging battery = found it.

*Check:* battery voltage at the terminals while the fault is present.

### Console read 2026-08-11 — H2 ELIMINATED; the stall is at ECU init, with NO exception

```
19:58:07,x   INFO [Thread-4]      - Plugin loaded: PLX SM-AFR / Tech Edge / TXS / Zeitronix ...
19:58:07,698 INFO [Thread-4]      - loaded protocol SSM: 245 parameters, 172 switches, def v370
19:58:07,921 INFO [Query Manager] - J2534 Library names loaded from ./customize/j2534Libraries.properties
19:58:08,538 INFO [Query Manager] - Trying new J2534/ISO9141 connection: Tactrix Inc. - OpenPort 2.0
                                    <nothing further>
```
Logger UI stuck on **"sending ecu init" for ~5 minutes.**

- The `Plugin loaded:` lines are **noise** — RomRaider registers all bundled external datasources
  at startup regardless of use. **H2 (AEM plugin) is ELIMINATED:** the stall occurs at K-line init,
  upstream of any external datasource.
- **No exception, no stack trace.** Nothing crashed. RomRaider is *blocked waiting* on a device
  that is not answering. Per the Addendum-(5) table, "no exception" points below the software layer.

### H4 (new, leading) — a hung JVM still owns the J2534 device

**Closing the RomRaider window does not terminate the JVM when the logger thread is stuck.** A
surviving `java.exe` retains the Openport, and every subsequent launch blocks at exactly this line.
This reproduces the entire observed pattern: first session logs fine → stalls → window closed →
JVM survives holding the device → all later launches hang at ECU init.

```powershell
Get-Process java, javaw -ErrorAction SilentlyContinue | Format-List Id, ProcessName, StartTime
Stop-Process -Name java, javaw -Force -ErrorAction SilentlyContinue
```
(`-ErrorAction SilentlyContinue` suppresses the error raised when one name matches nothing.
`StartTime` is the tell — multiple entries at different times = leftovers.)

**ORDER MATTERS: kill the JVMs BEFORE unplugging the Openport.** Yanking the cable while a process
still holds the device is how the driver is left in a bad state — very plausibly what produced the
vanishing-COM-port episode in Addendum (4). Kill → unplug → wait → replug → relaunch.

**H3 (battery sag) remains live and is checked in the same trip:** engine off, key on, wideband
heater at 1–2 A, on a battery previously recorded at 11.2 V. Below ~11.5 V, charge it rather than
chase software — a sagging battery produces precisely this signature (ECU stops answering init,
no exception, RomRaider waits indefinitely).

### 2026-08-11 late — USB/DRIVER STACK WEDGED (diagnosed)

**Symptom:** no ports active; **unplugged devices do not disappear from Device Manager**; no
connect/disconnect chime in either direction.

**Cause: a kernel-mode driver holding an uncompleted I/O request.** Windows cannot tear down a
device object while a driver still references it, so the device node survives physical removal and
the enumeration path stalls for new arrivals too.

**Causal chain, stated plainly:** the J2534 driver was blocked inside the ECU-init call (hence
"sending ecu init" with no exception) → the owning JVM was force-killed on my advice →
**`Stop-Process` cannot cancel a request already stuck in a driver.** The process died; the pending
IRP did not; the device object was left permanently referenced. **Unplug/replug cannot fix this** —
the fault is not in the connection, and pending IRPs cannot be cleared from userspace.

**My error to record:** recommending the process kill was right for a hung JVM, but I should have
flagged that a driver blocked at that level would very likely need a **reboot** afterwards rather
than a replug. The replug advice was wasted effort and further disturbed the stack.

**Fix — Shift+Restart → Troubleshoot → Advanced options → Startup Settings → Restart → 7.**
This does both jobs in one pass: clears the wedged driver stack *and* re-arms the
signature-enforcement bypass `openport.sys` needs, avoiding a Code 39 on return.

**⚠ DO NOT USE "Shut down."** Windows 11 Fast Startup (hiberboot) hibernates the kernel session
instead of tearing it down, so shutdown-then-power-on can **preserve the wedged driver state**.
Only "Restart" is a genuine full reboot. This is a standing gotcha for this laptop.

**H3 STILL UNMEASURED and still the leading root cause** of the original ECU-init hang. Hours of
key-on, engine off, wideband heater at 1–2 A, battery with prior history at 11.2 V. Every
downstream symptom — init timeout with no exception, driver wedging while blocked on a device that
never answered — is consistent with an ECU that stopped responding due to voltage sag. **Measure
before any further software debugging.**

### 2026-08-11 20:15 — clean reboot, charger on battery, SAME HANG. H3 and H4 both eliminated.

Restarted in the correct (bypass) mode; cables replugged, chimes heard, Device Manager solid; a
**charger pack was put on the battery**. Identical failure. Logger UI: "sending ecu init", forever.

```
20:15:00,433 loaded protocol SSM: 245 parameters, 172 switches, def v370
20:15:00,604 J2534 Library names loaded from ./customize/j2534Libraries.properties
20:15:01,106 Trying PREVIOUS J2534/ISO9141 connection: C:\WINDOWS\SysWOW64\op20pt32.dll
             <hang>
```

- **H4 (hung JVM) eliminated** — clean boot, no stale process could exist.
- **H3 (battery sag) eliminated** — charger pack fitted, no change.
- The Phidget `ExceptionInInitializerError` is **benign** (optional library absent) and predates the
  fault; it is not related.
- **Enumeration is NOT the problem.** The cable is seen; the hang is at the *protocol* layer.
  Replugging the Openport therefore cannot help and should not be repeated.
- Note `Trying **PREVIOUS**` (a cached library path from `settings.xml`) vs `Trying **NEW**`
  (device name) at 19:58 — different code path, library choice is being reused rather than
  re-enumerated.

### The change-set framing — only THREE things changed since logging worked

1. **The wideband was wired into the laptop** → a *second electrical path between car and PC*.
2. A reboot → **eliminated** (clean, correct mode, driver loaded).
3. **Bare wires were poked around a 12 V harness** while clipping to D-sub pins.

Syed's own timing observation — the ECU hang began during the AFR work, *while the AFR itself was
still broken* — points at (1) or (3). Both are now the queued tests.

### H5 (leading) — ground-loop / second ground path corrupting K-line

The Openport references OBD pins 4/5. The AEM black wire grounds at the gauge's chassis point. With
both plugged into the laptop those two chassis points are **bridged through the USB grounds**,
while a wideband heater pulls 1–2 A through that ground path. K-line is a single-wire bus that
discriminates high/low against ground; shift its reference and init fails while everything still
*looks* connected.

*Test:* unplug the FTDI adapter **physically** AND untick the AEM parameter on External. Openport
alone, IGN on, relaunch.

### H6 — OBD port has lost vehicle power (blown fuse)

The Openport is **USB-powered**, so it enumerates perfectly on the laptop with **no vehicle power
at all** — and cannot drive K-line. This reproduces the symptom exactly: solid in Device Manager,
hangs forever at init. A short while clipping bare wires near 12 V is the classic cause. **The
gauge still working proves only that ITS fuse survived, not the one feeding the diagnostic port.**

*Test:* back-probe **OBD pin 16 (batt+) to pin 4 (chassis gnd)** — expect ~12 V. Dead = find a
fuse, not a software fault.

### H7 — the registered J2534 DLL was silently swapped

```powershell
Get-Item C:\WINDOWS\SysWOW64\op20pt32.dll | Format-List Name, Length, LastWriteTime, VersionInfo
```
§3 records two DLLs (vendor 1.01.4341, official Tactrix 1.02.4870) and Corrections-Log #2 records
that running the extracted official EcuFlash **did** load its own DLL. If SysWOW64 now holds
1.02.4870 against a clone cable on vendor firmware 1.17.4877, a connection hang is a known outcome
— and **Syed's explicit vendor-drivers-only decision would have been silently overridden.**

---

## ★★ H5 CONFIRMED — GROUND LOOP. Both problems now solved.

**Test result: with the serial adapter unplugged, ECU logging works PERFECTLY.** H6 (blown OBD
fuse) and H7 (swapped J2534 DLL) are **not needed and not tested** — the isolation test settled it.

**This was never a software fault.** Not the driver, not the JVM, not the DLL, not the battery, not
the plugin. Two ground paths between car and laptop, and the loop current shifted the reference the
Openport's K-line transceiver compares against. Mechanism and remedies are now written into
`car/logging/CAPTURE-PROTOCOL.md` as a hardware prerequisite — that is the durable home for it.

**Answer to "should I switch grounds?" — NO.** Relocating the AEM ground changes the *magnitude* of
the offset while leaving the loop intact; it gambles on the residual being small enough. Break the
loop instead:

1. **Free:** omit AEM ground from DB9 pin 5, run **signal wire only**. Return path goes via chassis
   and the Openport's OBD ground. RS-232 margin (~1.4 V threshold vs a 0–5 V swing) absorbs the
   residual offset. *Caveat: wideband then depends on the Openport for its ground reference.*
2. **Robust:** **USB isolator** (ADuM3160-class, ~$20–40) between laptop and adapter, or an
   opto-isolated RS-232 adapter. **Preferred before real capture sessions.**

**ACCEPTANCE TEST — do not skip:** ECU parameters **and** `wideband_afr` updating **simultaneously**.
Either stream alone now proves nothing; that was the trap this whole sequence fell into.

### Why this took so long — worth reading before the next debug session

The fault had a **misleading signature**: it presented as a software hang, in software logs, on the
software side of the system, immediately after a software change. Six hypotheses were spent on the
PC (driver bypass, AEM plugin, hung JVM, battery, wedged USB stack, DLL swap) before the
change-set framing — *what physically changed between working and not* — pointed at the wiring.
**The isolation test that solved it (remove one subsystem, retest) should have been the FIRST move
once "it worked an hour ago" was established, not the seventh.**

Syed's timing observation ("this started while we were fixing the AFR, while the AFR was still
broken") was the single most valuable piece of evidence in the session and was initially
under-weighted in favour of chasing stack traces.

**Fix applied and verified:** DB9 pin 5 (AEM ground) removed, signal wire only. **Both streams now
live simultaneously — AFR in RomRaider matches the gauge face.** Problem B is fully closed.

---

## Problem A retry 2026-08-11 20:50 — same wall, but the log reframes the hypotheses

Retried under known-good conditions (charger pack on the battery, serial adapter unplugged so no
ground loop, clean boot). **Identical failure.** Full technical statement, forum-ready, now lives in
**`car/ecu/ROM-READ-BLOCKER.md`** — that is the durable home; this section is the summary.

**Positives confirmed by this log:**
- `J2534 DLL Version: 1.01.4341` — the **vendor** DLL is loaded. **H7 (silent DLL swap) is dead**;
  Syed's vendor-drivers-only decision is intact.
- `Device Firmware Version: 1.17.4877` — **unchanged**. No firmware flash has occurred; the clone
  is not bricked and the §8 discipline has held.

**The reading that matters — the ECU RETURNS A SEED.** EcuFlash cannot compute a key without one,
and it sent the key 47 ms after requesting the seed. **The ECU answered a reflash-mode
security-access request over K-line** — that is the security handshake, not SSM2 logging traffic.
**This substantially weakens H2 (clone can't do reflash-mode K-line):** that failure would land at
or before the seed request, not after a clean seed exchange. The failure is at *key validation*,
one step deeper than the cable's alleged limitation.

Also note the **662 ms** gap between key and close — that reads as a *timeout awaiting a response*
rather than an immediate rejection, so "key refused" and "key never answered" are **not yet
distinguished**.

**Hypotheses now:** H1 (ECU security altered by a COBB marriage / EcuTek flash) leads; H2 weakened
but alive. **A stock-looking ECU ID does not refute H1** — tuning suites commonly preserve the
factory calibration ID.

**A WRX cross-check is NOT a useful test.** Syed's other car is an '04 USDM WRX, which the defs show
is `68HC16Y5` / `wrx04` — **16-bit**. The clone is *documented* to fail on 16-bit K-line, so a
failure there would be uninformative. Only a success would tell us anything. Do not spend a trip
on it.

### ★ STRATEGIC — CORRECTED: the ROM read IS blocking. My earlier call was wrong.

I first wrote that the read was "not on the critical path" because logging works. **Syed pushed
back and was right.** Read and write pass the **same** seed/key gate — the read is merely the less
demanding of the two — so a seed/key failure *guarantees* the write path is dead. A tune must be
written to be tested, and the propose → clamp → converge loop terminates in a write. **No write
path means no tuning, no matter how good the logs are.**

The read is not a preliminary that can wait; it is the first observation of whether this project's
output can ever reach the car, and it is failing.

**Capture is still worth running in parallel** — `NOMINAL_MAF_IDLE` must be measured on this engine
(TGV + exhaust-AVCS deletes make the 2.50 g/s sim value untrustworthy), the whole deterministic
layer is `sim-calibrated-pending` and untested against real data, and archived iterations are
training examples. **But none of that produces a tuned car.** Parallel work, not progress against
the blocker.

**Resolution ladder now lives in `car/ecu/ROM-READ-BLOCKER.md`.** Headline: **separate H1 from H2
with a BORROWED tool before spending anything** — a COBB AccessPort states a marriage explicitly,
and any genuine J2534 tool distinguishes cable from ECU. A genuine Openport (~$170–200, out of
production) buys nothing if H1 is true. Then, in order: replacement ECU (exact correct part already
known from `defs/README.md`), **bench `shbootmode`** (an SH7058 *hardware* mode that bypasses the
application seed/key entirely — EcuFlash already loads that tool), or the standalone/rusEFI fork.

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
