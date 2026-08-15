# FastECU patch — MY2005 SH7058 K-Line `RequestDownload` sweep

One-file patch against [FastECU](https://github.com/miikasyvanen/FastECU) that makes the
`dataFormatIdentifier` byte of SID `0x34` **configurable at runtime**, plus raw TX/RX + NRC logging.

## Why

On the 2005 Forester XT (ECU `3B12504206`, SH7058, K-Line) the byte-level capture in
`car/logging/j2534_shim.log` shows the ECU **completes SecurityAccess and grants a programming
session**, then rejects `RequestDownload`:

```
27 02 01 B1 1E A4 → 67 02          key ACCEPTED
10 85 02          → 50 85          programming session granted
34 FF 30 00 04 00 17 AC → 7F 34 10 generalReject   ← the only failure
```

FastECU's `sub_ecu_denso_sh7058` profile is documented **2006-2007**; EcuFlash's `read_sti05`
covers **2005**-2007 on the same SH7058/`sti05` combination. **MY2005 sits in the coverage gap.**
The kernel address is *not* the problem — verified: `0xFFFFxxxx` references inside
`ssmk_kline_sh7058.bin` cluster at `0xFFFF3000/4000/5000`, matching its configured `0xFFFF3000`
(same test validates the SH7055 kernel against `0xFFFF6004`).

Upstream hardcodes the 5th byte and **every** `send_sid_34` in the tree uses `0x04`, so there is no
working alternative to copy — it has to be parameterised.

## Safety properties

- **Inert by default.** Env var unset ⇒ returns `0x04` ⇒ byte-identical to upstream.
- **Never crashes on bad input.** Malformed or out-of-range values fall back to `0x04`.
- **Read-path only.** Touches no write/erase code.
- **42 lines, one file.** Deliberately minimal; no config-schema plumbing through
  `protocols.cfg` → `file_actions` → `mainwindow` → `ecuCalDef`, which would be four files of
  risk for the same effect.

## Verification already done

`sid34_check.cpp` isolates the two new helpers with Qt stubbed out and compiles them with
`-Wall -Wextra`. **9/9 behaviour cases pass**, including unset⇒`0x04`, hex and decimal forms,
out-of-range, malformed, and whitespace. Run it anywhere:

```bash
g++ -std=c++11 -Wall -Wextra -o sid34_check sid34_check.cpp && ./sid34_check
```

Note this validates the *added logic*, not the Qt build — that needs the real toolchain.

## Apply

```bash
cd <your FastECU clone>
git checkout -b my2005-sh7058-sid34
git apply /path/to/0001-my2005-sh7058-sid34-format.patch
```

## Use

Build, then sweep without rebuilding — the value is read at each call:

```bash
set FASTECU_SID34_FORMAT=0x00
```

Order to try: **`0x00`** (KWP2000 "no compression, no encryption" — most likely), then `0x01`,
`0x02`, `0x03`. Unset it to reproduce the known failure as a control.

**Control test first.** With the variable unset, the run must still fail at `7F 34 10`. That proves
the patch is inert and the harness honest before any result is believed.

Each attempt now logs:

```
SID 0x34 request upload: addr=0xffff3000 len=0x17ac dataFormatIdentifier=0x0 (ENV OVERRIDE)
  TX: 80 10 F0 08 34 FF 30 00 00 00 17 AC ..
  RX: 80 F0 10 03 7F 34 10 ..
  SID 0x34 REJECTED: service=0x34 NRC=0x10
```

Success = anything other than `7F 34 ..`; a `74` positive response means the read proceeds.
Key-cycle between attempts — repeated failures make the ECU refuse SSM2 init.

## Upstream

If a value works, this plus `car/ecu/FASTECU-SH7058-KLINE-BUG.md` (byte-level trace, elimination
table) is a complete bug report. Worth filing either way — a confirmed non-working sweep is also
information the maintainer doesn't have.
