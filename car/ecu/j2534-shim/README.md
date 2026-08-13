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
work — this respects the vendor-drivers-only decision. Reverting = remove the EcuFlash registration
line. Nothing is overwritten.

---

## 1. Build (produces a 32-bit DLL — EcuFlash is a 32-bit app)

You already have `cargo`. Two one-time prerequisites:

```bash
rustup target add i686-pc-windows-msvc
```
`rustup` — the Rust toolchain manager. `target add` — installs support for compiling to a platform
other than your machine's default. `i686-pc-windows-msvc` — 32-bit (`i686`) Windows using the MSVC
linker. **The MSVC linker comes from "Visual Studio Build Tools" with the "Desktop development with
C++" workload** — if `cargo build` later errors with `link.exe not found`, that's the missing piece
(free from Microsoft). If you'd rather not install VS Build Tools, use the GNU toolchain instead:
`rustup target add i686-pc-windows-gnu` and add `--target i686-pc-windows-gnu` below (needs the
`i686` MinGW, which rustup can fetch).

Then, from this folder:

```bash
cargo build --release --target i686-pc-windows-msvc
```
`cargo build` — compile the project. `--release` — optimized build (also strips debug-assert
overhead). `--target i686-pc-windows-msvc` — build the 32-bit Windows DLL rather than a binary for
your host.

Output: `target\i686-pc-windows-msvc\release\op20log.dll`

**Verify the exports are undecorated** (this is the one thing most likely to go wrong):
```bash
dumpbin /exports target\i686-pc-windows-msvc\release\op20log.dll
```
`dumpbin` — an MSVC tool that inspects a binary. `/exports` — list exported functions. You want to
see `PassThruOpen`, `PassThruConnect`, … as **plain names**. If they appear as `_PassThruOpen@8`
(decorated), EcuFlash won't bind them — tell me and I'll adjust `exports.def`.

## 2. Point the shim at the real driver and a log file

Set two environment variables **in the same shell you launch EcuFlash from**, or system-wide:

```bash
set TACTRIX_SHIM_REAL=C:\WINDOWS\SysWOW64\op20pt32.dll
set TACTRIX_SHIM_LOG=C:\Users\Syed\Desktop\j2534_shim.log
```
`set NAME=value` — defines an environment variable for this shell session. `TACTRIX_SHIM_REAL` — the
genuine DLL the shim forwards to (this is the exact path your EcuFlash task log already prints:
`C:\WINDOWS\SysWOW64\op20pt32.dll`). `TACTRIX_SHIM_LOG` — where to write the capture; Desktop is a
guaranteed-writable spot. Both have defaults (SysWOW64 DLL, `%TEMP%\j2534_shim.log`) if unset, but
setting them explicitly removes all doubt.

## 3. Register the shim with EcuFlash

EcuFlash chooses its J2534 library from `customize\j2534Libraries.properties` (your task log prints
`J2534 Library names loaded from file: ./customize/j2534Libraries.properties`). **The exact line
format differs between EcuFlash builds, so before I give you the precise line, paste me the current
contents of:**

```
C:\Program Files (x86)\OpenECU\EcuFlash\customize\j2534Libraries.properties
```

It is a tiny text file. I'll hand you back the one line to add pointing at `op20log.dll`, and the
EcuFlash device-menu entry to pick. (Adding a line is fully reversible — delete it to revert.)

## 4. Capture

1. Fresh key cycle and a charger on the battery (the earlier session degraded from repeated
   attempts + sag — start clean).
2. Launch EcuFlash from the shell where the env vars are set; select the **shim** device.
3. Confirm the log file appears and its first line reads `==== shim init: real DLL '…' loaded=true`.
4. Attempt the read **once** (do not hammer it). Let it reach the seed/key wall and stop.
5. Close EcuFlash and **send me `j2534_shim.log`.**

## 5. What I'll read from it

The decisive lines are the `TX`/`RX` hex dumps bracketing the seed request. Concretely:
- the **RX** message right after the seed request — the seed bytes themselves;
- the **TX** message EcuFlash then sends — the computed key;
- any **RX** after the key — an explicit reject code vs nothing at all (which resolves the
  NAK-vs-timeout ambiguity the 662 ms task-log gap left open).

## Reverting

Delete the line you added to `j2534Libraries.properties` (and optionally delete `op20log.dll`).
No system file, driver, or registry entry was modified.
