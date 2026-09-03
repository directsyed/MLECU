# FastECU: SH7058 K-Line kernel upload rejected on MY2005 Subaru (ECU `3B12504206`)

> ## ✅ RESOLVED 2026-08-16; it was NOT a FastECU/format bug.
>
> The read succeeded once the **Subaru green test-mode connectors** were joined (they enable the
> ECU's read/write mode). The `dataFormatIdentifier` sweep (0x00–0x04) had confirmed the byte was
> irrelevant, the ECU understood every request and refused with a bare `generalReject`, a
> **permission** refusal, not a format one. In FastECU's flow, `RequestDownload` (SID 0x34) is the
> kernel-upload-to-RAM step (`flash_ecu_subaru_denso_sh705x_kline.cpp::send_sid_34_request_upload`);
> comms were clean (a well-formed request, a well-formed NRC), so the block was semantic. Full story
> + validated dump: `car/ecu/rom read/PROVENANCE.md`.
>
> **If filed upstream at all, reframe:** not "FastECU builds a wrong SID 0x34" but "MY2005 SH7058
> requires the diagnostic/test-mode connectors joined to enter read/write mode; with them joined the
> stock `sub_ecu_denso_sh7058` request works unchanged." Kept below as the investigation record.

**Status:** RESOLVED (see banner), the format-mismatch hypothesis was falsified. Investigation record
follows; originally drafted to file upstream at <https://github.com/miikasyvanen/FastECU/issues>.

## Summary

On a **2005 USDM Subaru Forester XT (4EAT)**, ECU ID **`3B12504206`**, FastECU `0.1.0-beta.5`
completes the full security handshake and enters programming session, then the ECU **rejects
`RequestDownload` (SID 0x34) with NRC 0x10 (generalReject)**. Reproducible on every profile that
reaches that stage. EcuFlash 1.44 fails *earlier* (at seed/key) on the same car and cable, so
neither tool can complete a read.

## Environment

| | |
|---|---|
| Vehicle | 2005 USDM Forester XT, 4EAT, drive-by-wire |
| ECU ID | `3B12504206` (= `A2WC411D`; AT build of cal rev 42. SH7058, `sti05`) |
| Interface | Washinglee Openport 2.0 clone, FW `1.17.4877`, J2534 DLL `1.01.4341` |
| FastECU | `0.1.0-beta.5`, profile `sub_ecu_denso_sh7058` |
| Capture | Custom transparent J2534 pass-through shim (`car/ecu/j2534-shim/`) |

## Byte-level trace (via J2534 shim, every byte on the wire)

```
TX  80 10 F0 01 BF 40                          SSM2 init
RX  80 F0 10 39 FF A2 10 11 3B 12 50 42 06 ...  ECU ID 3B12504206            OK
TX  80 10 F0 01 81 02                          StartCommunication
RX  80 F0 10 03 C1 EF 8F C2                                                  OK
TX  80 10 F0 02 83 00 05                       AccessTimingParameters
RX  80 F0 10 07 C3 00 00 FF 00 FF 00 48                                      OK
TX  80 10 F0 02 27 01 AA                       SecurityAccess requestSeed
RX  80 F0 10 06 67 01 A1 5B AD 3F D6           seed = A1 5B AD 3F            OK
TX  80 10 F0 06 27 02 01 B1 1E A4 23           SecurityAccess sendKey
RX  80 F0 10 03 67 02 34 20                    KEY ACCEPTED                  OK
TX  80 10 F0 03 10 85 02 1A                    StartDiagnosticSession 0x85
RX  80 F0 10 02 50 85 57                       programming session granted   OK
TX  80 10 F0 08 34 FF 30 00 04 00 17 AC B2     RequestDownload
RX  80 F0 10 03 7F 34 10 46                    *** 7F 34 10 = generalReject ***
```

**Security access and programming session both succeed.** The ECU is not locked, and the interface
is demonstrably healthy; it delivers a well-formed, checksummed request and receives a well-formed
negative response naming the rejected service.

## What has been ruled out

**The kernel load address is CORRECT; this is not a config typo.** `config/protocols.cfg` sets
`sub_ecu_denso_sh7058` → `kernel_addr = 0xFFFF3000`. Disassembly-free verification: scanning
`kernels/ssmk_kline_sh7058.bin` (6056 B) for big-endian words in `0xFFFFxxxx` shows references
clustered at **`0xFFFF3000` (x32), `0xFFFF4000` (x45), `0xFFFF5000` (x15)**: exactly the span a
6056-byte image loaded at `0xFFFF3000` would occupy plus its working area. The same test on
`ssmk_kline_sh7055.bin` (6660 B, `kernel_addr = 0xFFFF6004`) clusters at `0xFFFF6000/7000/8000`,
confirming the method. **Both kernels are built for their configured addresses.**

**The transmitted address is correct per protocol.** `send_sid_34_request_upload()` truncates to 24
bits (`addr>>16`, `>>8`, `&0xFF`), so `0xFFFF3000` → `FF 30 00`. That matches the observed bytes and
matches how the working SH7055 path behaves.

**Other eliminations:** ECU not locked (key accepted); cable not at fault (clean NRC returned);
battery/voltage not implicated (handshake completes); all six EcuFlash K-line seed/key algorithms
tried; ECU hard reset (30 min) made no difference; `sh7055_02`, `sh7055_04` and `sh7058` profiles
all tried.

## Hypotheses (unresolved)

1. **MY2005 is outside FastECU's coverage.** The profile is described as *"2006-2007 K-Line
   (SH7058/1MB)"*. EcuFlash's `read_sti05.xml` covers **2005-2007** on the same `SH7058`/`sti05`
   combination, so MY2005 is exactly the gap. A MY05 bootloader may accept a different
   `RequestDownload` form than MY06-07.
2. **`dataFormatIdentifier` mismatch.** `send_sid_34_request_upload()` hardcodes `0x04` as the 5th
   byte. If the MY05 bootloader expects a different value (e.g. `0x00`), generalReject is a
   plausible response. **Untested, needs a source rebuild.**
3. **An additional precondition** (erase, tester-present, or a different session sub-mode) required
   by MY05 before download is accepted.

## Suggested next step for a maintainer

Confirm whether MY2005 SH7058 K-Line is intended to be supported by `sub_ecu_denso_sh7058`, and if
so whether `dataFormatIdentifier = 0x04` is correct for that bootloader generation. A build exposing
that byte as a config field would make it testable without recompiling.

## Reproduction assets in this repo

- `car/logging/j2534_shim.log`: the full capture above
- `car/ecu/j2534-shim/`: the pass-through shim used to obtain it (Rust, GPL-compatible, read-only)
- `car/ecu/defs/README.md`: derivation of the ECU ID → `A2WC411D` / SH7058 / `sti05` identification
