# ROM read blocked at seed/key — technical statement

**Status: OPEN. Not on the critical path** — see "Why this is parked" below. Written to be posted
verbatim to the RomRaider forum, and to stop the next agent re-testing what is already eliminated.

## Vehicle and hardware

| | |
|---|---|
| Vehicle | 2005 USDM Subaru Forester XT, **4EAT automatic**, drive-by-wire (physically confirmed at the throttle body) |
| Engine | JDM EJ20X swap (irrelevant to the ECU security handshake, listed for completeness) |
| ECU ID (SSM2) | **`3B12504206`** |
| Identified as | **`A2WC411D`** — the AT build of calibration revision 42. Its MT twin `3B12584206` / `A2WC411I` is in the 2012 defs; the AT entry was never contributed. SH7058, `sti05`. Proof: `car/ecu/defs/README.md` |
| Cable | **Washinglee Openport 2.0 clone**, serial `TAhJALxt` |
| Cable firmware | `1.17.4877` — **unchanged across every attempt; no firmware flash has ever occurred** |
| J2534 DLL | vendor **`1.01.4341`** (Aug 2014). Official `1.02.4870` also tried — identical failure |
| EcuFlash | `1.44.4347` (vendor, installed) and `1.44.4870` (official, portable) — identical failure |

## The failure

Reproducible on every attempt, both EcuFlash versions, both DLLs, `sti04` and `sti05`:

```
[20:50:56.895] kernel get version
[20:50:57.418] VIN read not supported
[20:50:57.943] SSM2 init
[20:50:58.086] SSM2 ECU ID is 3B12504206
[20:50:58.166] Requesting Seed...
[20:50:58.213] Sending Key...              <- 47 ms after the seed request
[20:50:58.875] interface close             <- 662 ms after the key
```

Then a GUI dialog: *"An error has occurred, see log for details."*

**Nothing is ever written. The ECU is not modified. Retrying is safe.**

## ★ The reading that matters — the ECU RETURNS A SEED

EcuFlash cannot compute and send a key without having received a seed, and it sent one **47 ms**
after the request. **The ECU therefore answered a reflash-mode security-access request over
K-line.** That is not SSM2 logging traffic; it is the security handshake itself.

**This substantially weakens the clone-cable hypothesis.** If the Washinglee's partial K-line
implementation could not enter reflash mode, the failure would land at or before the seed request —
not after a clean seed exchange. Whatever is failing happens at *key validation*, one step deeper
than the cable's alleged limitation.

Note also the **662 ms** gap between key and close. That looks like a *timeout waiting for a
response* rather than an immediate explicit rejection, so "the key was refused" and "the key was
never answered" are not yet distinguished.

## Eliminated — do not re-test

| Suspect | How eliminated |
|---|---|
| Cable / driver / wiring | RomRaider streams live SSM2 data perfectly (RPM, ECT, battery V) |
| J2534 DLL registration | EcuFlash reads device firmware + serial on every attempt |
| EcuFlash version | Identical failure on `1.44.4347` and `1.44.4870` |
| J2534 DLL version | Identical failure on `1.01.4341` and `1.02.4870` |
| Flash method | `sti04` and `sti05` both tried — same point of failure |
| 16-bit vs 32-bit ECU | DBW physically confirmed → 32-bit SH7058 is correct |
| Java bitness | Irrelevant — EcuFlash is a native app |
| Green test-mode connectors | Not applicable to a 2005 DBW car |
| Engine running | Confirmed engine OFF, key ON |
| **Battery voltage** | **Charger pack fitted for the 2026-08-11 retry — no change** |
| **Ground loop** | **Serial adapter unplugged for the retry** (a ground loop between the AEM wideband and the Openport was independently proven to break K-line comms — see `car/logging/CAPTURE-PROTOCOL.md`) |
| **ECU is foreign to the car** | **Refuted** — `3B12504206` is the correct 05 USDM FXT AT part (`car/ecu/defs/README.md`) |
| Clone cable can't do reflash K-line | **Weakened** — the ECU returned a seed (above) |

## Remaining hypotheses

**H1 (leading) — the ECU's security has been altered.** A COBB AccessPort "marriage" or an EcuTek
flash changes the seed/key relationship so third-party tools cannot unlock. Produces exactly this
signature: identify fine, seed fine, key refused. **A stock-looking ECU ID does not refute this** —
tuning suites commonly preserve the factory calibration ID. Car was bought used; history unknown.

**H2 (weakened) — the clone's K-line implementation fails at key validation specifically.** Still
possible if the seed exchange tolerates sloppier timing than the key response window does.

**Counter-evidence worth knowing:** an '04 Legacy GT owner reported this identical wall across 3
laptops, **2 genuine Openport cables**, and a healthy 12.7 V battery. So this is not always the
cable.

## The question for the forum

> Has anyone successfully read an `sti05` ECU with a Washinglee Openport 2.0 clone? And does
> *seed returned, key refused* specifically indicate a married/locked ECU, as opposed to a cable
> limitation? SSM2 logging works flawlessly on this setup; only reflash-mode entry fails.

## ★ Why this IS blocking (correcting an earlier misjudgement)

An earlier draft called this "parked, not on the critical path." **That was wrong, and Syed
correctly pushed back.**

**Read and write share the same gate.** Both require the identical seed/key unlock followed by a
kernel upload; the read is simply the *less* demanding of the two. A seed/key failure therefore
guarantees the write path is dead — you cannot flash a tune you cannot unlock the ECU to read.
And because a tune must be *written to be tested*, the whole propose → clamp → converge loop
terminates in a write. **No write path means no tuning, however good the logs are.**

The read is not a preliminary step that can wait. It is the **first observation of whether this
project's output can ever reach the car**, and it is currently failing.

### What the logs are still worth — real, but not a substitute

Capture remains worth doing in parallel, for reasons that do not depend on writing:

- **`NOMINAL_MAF_IDLE` must be measured on this engine.** `CAPTURE-PROTOCOL.md` flags the 2.50 g/s
  figure as a *sim* value, and this car has TGV and exhaust-AVCS deletes. Until it is measured, the
  estimator's MAF-vs-nominal term — the one separating a MAF error from an injector-flow error — is
  calibrated against a number never observed on this car.
- **The deterministic layer is entirely sim-bound.** MVEM is `sim-calibrated-pending`; the estimator
  is exactly as right as the model until real logs test it. Both sides of the cross-check are
  currently validated only against simulation.
- **Archived tuning iterations are literally training examples** for the fine-tune corpus.

All real. **None of it produces a tuned car.** Treat capture as parallel work, not as progress
against this blocker.

## Resolution ladder — cheapest and most decisive first

### 1. Separate H1 from H2 with a borrowed tool — do this BEFORE spending anything

The single question worth answering: **is it the ECU or the cable?** Two ways, both ~free:

- **A COBB AccessPort will state a marriage explicitly.** Plug one in; if the ECU is married to
  another AP, it says so. That is a *direct* diagnosis of H1 rather than an inference.
- **Any genuine J2534 Subaru tool** attempting a read. Success ⇒ H2 (the clone) and the fix is a
  cable. Identical failure ⇒ H1 (the ECU) and no cable purchase would have helped.

APs and genuine Openports are common among independent Subaru shops and local enthusiasts. **Do not
buy a genuine Openport (~$170–200, out of production) until this test has run** — if H1 is true it
buys nothing.

### 2. If H1 is confirmed — replacement ECU

A married/EcuTek-locked ECU generally cannot be unlocked without the tool that locked it. The
standard remedy is a known-good used ECU, and **the exact correct part is already known** from
`defs/README.md`: 2005 USDM Forester XT **automatic**, ECU ID `3B12504006` / `4106` / `4206` /
`4306` (any AT revision of the family), SH7058, `sti05`. Typically $100–200 used. Verify the seller's
ECU ID before buying, and confirm it is not itself married.

### 3. Bench boot-mode read/write — bypasses ECU security entirely

EcuFlash loads a flashing tool named **`shbootmode`** (visible in the startup log above). SH boot
mode is a **hardware mode of the Renesas SH7058 itself**, entered by pin strapping and talked to via
SCI — it addresses the chip's own bootloader and therefore **does not use the ECU application's
seed/key at all.** This is the community's recovery path for bricked and locked Subaru ECUs.

Requires removing and opening the ECU and wiring to specific pins; more involved than any OBD-port
method and unforgiving of mistakes. Research the exact SH7058 procedure properly before attempting —
it is listed here as a genuine option, not a recipe.

### 4. Standalone ECU (rusEFI) — forces an already-open decision

`car/CLAUDE.md` carries this as a standing design question: stay on the OEM ECU with
RomRaider/EcuFlash, or plan a standalone swap. A permanently unwritable OEM ECU decides it. This
reshapes the deterministic write-layer interface, so it is a real architectural fork, not a
last resort to drift into.

### 5. Forum, in parallel with all of the above

Post the statement above. Free, asynchronous, and the community has seen this exact signature.
