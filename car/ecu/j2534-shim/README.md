# J2534 logging shim (`op20log.dll`)

A transparent pass-through DLL that sits between EcuFlash and the genuine Tactrix driver
(`op20pt32.dll`), forwards every J2534 call unchanged, and **logs the exact bytes exchanged with
the ECU** — including the reflash-mode `Requesting Seed` / `Sending Key` handshake we cannot see
from EcuFlash's own task log.

**Why it exists:** to settle cable-vs-ECU on the read failure (see `../ROM-READ-BLOCKER.md`). If the
**seed** the cable returns is all-`00`, all-`FF`, or identical on every attempt → the clone cable is
not completing a real exchange (**cable fault**). If the seed looks like proper data that changes
per session and the ECU still refuses the key → the fault is ECU-side.

**Safety:** it only reads and copies pointers through to the real DLL. It never modifies traffic and
never issues a write to the ECU. The genuine vendor DLL stays exactly where it is and does all real
work — this respects the vendor-drivers-only decision. Reverting = delete one registry key.

---

## Step 1 — get the code onto the Windows laptop

Either clone from GitHub:
```bash
git clone https://github.com/directsyed/MLECU.git
```
`git clone` — download a full copy of the repository. Then `cd MLECU\car\ecu\j2534-shim`.

…or, since the server's shared drive is mapped on the laptop, just open a terminal in this folder
directly on the shared drive. (A local clone builds faster and avoids network-drive quirks — prefer
it.)

## Step 2 — build the DLL (no Visual Studio needed)

You already have `cargo`. Use the **self-contained GNU toolchain** — rustup ships it with its own
bundled linker, so nothing else to install:

```bash
rustup toolchain install stable-i686-pc-windows-gnu
```
`rustup toolchain install` — download a Rust toolchain. `stable-i686-pc-windows-gnu` — the stable
compiler for 32-bit (`i686`) Windows using the GNU/MinGW linker. 32-bit because EcuFlash is a 32-bit
app; GNU because rustup bundles that linker, so no Visual Studio Build Tools are required.

```bash
cargo +stable-i686-pc-windows-gnu build --release
```
`cargo build` — compile the project. `+stable-i686-pc-windows-gnu` — use that toolchain for this one
command (its default target is 32-bit Windows GNU, so no `--target` needed). `--release` — optimized
build.

Output: **`target\i686-pc-windows-gnu\release\op20log.dll`**

## Step 3 — put the DLL where the registry file expects it

```bash
mkdir C:\Openport-shim
copy target\i686-pc-windows-gnu\release\op20log.dll C:\Openport-shim\
```
`mkdir` — make the folder. `copy` — copy the built DLL into it. (`register-shim.reg` points at
`C:\Openport-shim\op20log.dll`; change that path in the .reg if you prefer another location.)

## Step 4 — register the shim as a second J2534 device

Double-click **`register-shim.reg`** (in this folder) and accept the UAC / "are you sure" prompts,
or from an **elevated** terminal:
```bash
reg import register-shim.reg
```
`reg import` — merge a `.reg` file into the registry. This adds one new device,
**"OpenPort 2.0 (LOG SHIM)"**, next to your real Tactrix entry. The real one is untouched, so
RomRaider is unaffected. The shim's capability flags are copied verbatim from your real entry.

## Step 5 — choose where the log is written

```bash
setx TACTRIX_SHIM_LOG "C:\Openport-shim\j2534_shim.log"
```
`setx` — set a **persistent** environment variable (unlike `set`, which lasts only for the current
window). Programs launched *after* this — including EcuFlash — will inherit it. The shim reads it to
decide where to write. (If unset it defaults to `%TEMP%\j2534_shim.log`. `TACTRIX_SHIM_REAL`
defaults to `C:\WINDOWS\SysWOW64\op20pt32.dll`, which matches your real device, so leave it alone.)

## Step 6 — capture

1. Fresh key cycle, charger on the battery (the earlier session degraded from repeated attempts +
   sag — start clean).
2. **Close and reopen** EcuFlash so it picks up the new env var, then in its interface/device
   selection choose **OpenPort 2.0 (LOG SHIM)** instead of the plain Tactrix device.
3. Attempt the read **once**. Let it hit the seed/key wall and stop — don't hammer it.
4. Close EcuFlash and send me **`C:\Openport-shim\j2534_shim.log`**.

## What "good" looks like

- `C:\Openport-shim\j2534_shim.log` exists, and its **first line** reads:
  `==== shim init: real DLL 'C:\WINDOWS\SysWOW64\op20pt32.dll' loaded=true ; log='…' ====`
  That confirms the shim loaded the real driver and is logging.
- **EcuFlash behaves identically to before** — same task-log sequence, and the read still fails at
  the same seed/key wall. That is expected and correct: the shim is transparent, so it does not fix
  the read, it *records* it. We want the failure, captured byte-for-byte.
- The log fills with `PassThruConnect` (protocol/baud), `PassThruStartMsgFilter`, and many
  `TX`/`RX` lines with hex payloads. The decisive ones bracket the seed request: the `RX` right
  after it is the **seed**; the `TX` after that is the **key**; any `RX` following the key is an
  explicit reject vs nothing (timeout).
- If instead EcuFlash errors that it can't load the device or find `PassThruOpen`, the exports came
  out decorated — run `dumpbin /exports C:\Openport-shim\op20log.dll` (or `objdump -p`) and send me
  what the export names look like.

## Reverting

Delete the registry key (double-click `unregister-shim.reg`, or
`reg delete "HKLM\SOFTWARE\WOW6432Node\PassThruSupport.04.04\Tactrix OpenPort 2.0 (LOG SHIM)" /f`).
No system file, driver, or vendor entry was modified.
