# ROM read blocked at seed/key — technical statement

> ## ✅ RESOLVED 2026-08-16 — SUPERSEDED. The ECU was NOT locked. Read succeeded.
>
> The whole conclusion below (H1: "married/EcuTek-locked ECU, software read path effectively
> exhausted") **was wrong.** The stock ROM was read on 2026-08-16 and is **byte-identical to a
> harvested known-stock reference** (sha256 `11fe1536…`), so the ECU is genuinely un-tuned and was
> never locked. Full story + validation: **`car/ecu/rom read/PROVENANCE.md`** (commit `f27aad8`).
>
> **What actually fixed it:** joining the Subaru **green test-mode connectors** (two single-pin
> greens under the driver column) enabled read/write mode. This document's line 63 —
> *"Green test-mode connectors | Not applicable to a 2005 DBW car"* — **was the exact error.** That
> elimination was reasoning, never a test; the real fix came from corpus doc 5793 (an 05 Forester
> that read only with the test connector), surfaced by the 2026-08-16 community-doc review.
> Note: this doc is about **EcuFlash** failing at *seed/key*; the successful read was **FastECU**
> (its seed/key was solved separately) failing at *RequestDownload* until the connectors were
> joined. EcuFlash was never retried with the connectors; whether they also fix its key step is
> untested and now moot.
>
> **The body below is kept verbatim as the honest failure history** (and a lesson: an elimination
> by argument is not an elimination by experiment). Do not act on its conclusions.

---

**Status: RESOLVED (see banner). Historical below.** Written to be posted
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
| EcuFlash version | Identical failure on `1.44.4347` and `1.44.4870`. **Also failed on an older build before Syed moved newer as a troubleshooting step** — the newer build was the *reaction* to this failure, not a cause. "Try an older build" is therefore already eliminated. |
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

---

## ★ BUDGET-CONSTRAINED PATH (2026-08-12) — no purchases

Syed cannot fund an AccessPort, a replacement ECU, or a standalone just to run a test. Everything
below costs **zero money**. Ordered by information-per-effort.

### F1. Does EcuFlash even know this ECU? (free, do first)

**Possible root cause nobody has checked.** EcuFlash `1.44.4870` logs `Sending Key [1]...` — an
**indexed** key, implying a key *table* rather than one universal algorithm. Our ECU ID
`3B12504206` / `A2WC411D` is missing from the community ROM defs precisely because that AT
calibration revision was never contributed. **If it is likewise absent from EcuFlash's own
`rommetadata`, EcuFlash may be selecting a default or wrong key** — which would produce exactly
"seed accepted, key refused" with a perfectly healthy ECU and a perfectly healthy cable.

```powershell
Get-ChildItem "C:\Program Files (x86)\OpenECU\EcuFlash\rommetadata" -Recurse -Include *.xml | Select-String -Pattern "3B12504206", "A2WC411" | Format-List Path, LineNumber, Line
```

If nothing matches but sibling IDs (`3B12504106` / `A2WC410D`) do, that is a strong lead and the
fix may be **free** — supply metadata for the missing variant.

### F1b. Metadata result + the A2WC411D file (done 2026-08-12)

EcuFlash's `rommetadata` contains `A2WC411I.xml` — the **MT twin** — but **not** `A2WC411D` (our
AT build). Same gap as everywhere. Built the missing file: **`car/ecu/defs/ecuflash/A2WC411D.xml`**.

Construction mirrors upstream's *own* pattern: the MT twin `A2WC411I.xml` is a stub that
`<include>`s `A2WC410I` — i.e. upstream itself asserts rev-41↔42 table-layout identity on the MT
side. Our file does the same on the AT side (`<include>A2WC410D</include>`), with identity fields
from the logger-def family table (see `defs/README.md`).

**Install:** copy to `C:\Program Files (x86)\OpenECU\EcuFlash\rommetadata\subaru\Forester XT\`.
`A2WC410D.xml` must already be in that folder (it is the include target — it ships with EcuFlash).
On next launch the startup log's "NNN ROM metadata models scanned" count should rise by one.

**Honest expectation — this probably will NOT fix the read.** EcuFlash reads via the generic
`read_sti05.xml` template (visible in the task log), which is keyed by *memory model*, not by our
per-calibration file. The per-cal file governs **editing/checksumming a ROM image once you have
one**, and it matters the moment a read succeeds. It is *worth* having regardless. But if EcuFlash
selects its seed/key by ECU-ID lookup and falls back to a default on a miss, this file is what
would let it find the right entry — that is the one way it could bear on the read, and it is
untested. Free and reversible, so it is in place.

### F1c. J2534 call tracing — capture the actual seed and key bytes

**This is the highest-value diagnostic left.** It resolves the ambiguity the 662 ms
key→close gap left open: did the ECU **NAK the key** (→ H1, security altered) or **never answer**
(→ H2/timing/cable)? The task log cannot tell these apart; the wire trace can.

**Authoritative method (Tactrix):** the Openport DLL emits a full call trace via
`OutputDebugString` **once an application sets the IOCTL** `TX_IOCTL_SET_DLL_DEBUG_FLAGS` with flag
`TX_IOCTL_DLL_DEBUG_FLAG_J2534_CALLS` (`0x00000001`). Output is captured with SysInternals
**DebugView** (`Dbgview.exe`). Source: Tactrix KB (see session notes).

**The catch:** EcuFlash does **not** set that IOCTL, so running EcuFlash + DebugView alone **may
show nothing from the DLL.** Two paths:
1. **Zero-risk, try first:** run DebugView (as admin, "Capture Win32" on), then attempt the read in
   EcuFlash. Costs two minutes; if the DLL emits anything unprompted we get it for free.
2. **Reliable:** a tiny helper that loads `op20pt32.dll`, sets the debug IOCTL, then performs
   SSM2 init → request seed → send key, logging every call. This is a read-path-only sequence
   (**never writes**), so it is brick-safe, and it is exactly the kind of scripting to build
   in-house. **Claude to write this as a ctypes script on request** — deferred to keep the current
   step (hard-reset read + wideband fix) clean.

### F1d. HARD-RESET RESULT (2026-08-13) — did NOT clear the block. This is decisive.

Battery disconnected ~30 min, reconnected, read attempted as the first action. **Identical
failure**: SSM2 init → ECU ID `3B12504206` → Requesting Seed → Sending Key → interface close, ~640 ms
key-to-close. Two clean attempts (18:08, 18:34) both reached the wall.

**This kills the transient-lockout hypothesis.** A failed-attempt security counter is cleared by a
power cycle; this survived one. What survives a power cycle is a **persistent** state — a genuinely
altered seed/key relationship. **H1 (ECU security altered: married/EcuTek-locked) is now the strong
leader; the transient-counter idea is eliminated.**

**Correction to Syed's reading of the later attempts.** After the two clean attempts, later ones
(18:35 05-Forester, 18:36 04-Forester) showed **`SSM2 init` repeated ~10× then close** — i.e. SSM2
would no longer even establish. Syed attributed this to switching the vehicle model. It is **not**
caused by the model choice:
- **SSM2 init is protocol-level and model-independent** — it happens before any template or security
  and is identical for 05 STI vs 05 Forester (both resolve to `read_sti05`).
- The real cause is **comms degradation across a hammered session** — either battery sag (extended
  key-on/engine-off after a cold start) or an **ECU-side SSM2 lockout after repeated failed security
  attempts**, which several Subaru ECUs impose. A key cycle + rested/charged battery clears it.
- The **04-Forester attempt used `read_sti04`, which is the WRONG method for this SH7058 ECU** — its
  `readback fail` is doubly uninformative (wrong method AND degraded comms). Disregard it.

**Consequence:** hammering more reads has no diagnostic value now. The reset was the last "just
retry differently" card. Two clean attempts already delivered the verdict.

### F1c-REASSESSED (2026-08-13) — the seed/key helper is LOW value; do not build it

Earlier this file promoted an active seed/key helper as "the leading software action." **Downgraded
after reconsideration:** the sti05 seed/key is tied to the **flash method**, not the calibration —
it is the **same key for every sti05 Subaru**. EcuFlash therefore already sends the correct standard
key, and this ECU rejects it. A helper computing and sending that same standard key would reproduce
the rejection EcuFlash already gets. Its only residual value is distinguishing NAK from timeout,
which changes neither the conclusion (locked) nor the remedy. **Not worth building.** The "missing
metadata → wrong key" idea (F1) is correspondingly weak: key selection is not per-cal.

**Honest standing conclusion: the software read path is effectively exhausted.** The ECU rejects the
standard unlock and re-sending it by any tool will not change that. What remains is not more
software against the OBD security layer — it is either bypassing that layer (bench `shbootmode`) or
addressing the lock at its source (borrow the AP that married it / replacement ECU).

### F1e. DebugView (passive) — EXHAUSTED

The only line DebugView emitted during the read was an unrelated Chrome crashpad error. **Confirmed:
EcuFlash does not set the Tactrix debug IOCTL, so the passive route yields nothing.** As predicted,
the reliable path is the active helper (F1c route 2) — now promoted to the leading software action.

### F1f. Metadata count still 745 — A2WC411D not loaded

The 18:07 startup log still reads `745 ROM metadata models scanned`, not 746, so `A2WC411D.xml` was
**not** picked up (copied after this session launched, or misplaced). Restart EcuFlash and confirm
**746**. Note this almost certainly does not affect the read (reads use the memory-model-keyed
`read_sti05` template, not the per-cal file) — but if key selection is ever suspected, this must be
loaded to rule it in or out.

### F2. Physical and documentary evidence of a prior tune (free)

- **AccessPort traces:** windshield/dash mount, leftover bracket, adhesive residue, an OBD splitter
  left in the footwell, COBB or tuner-shop stickers. Owners who ran an AP usually leave marks.
- **Previous owner / service history.** One phone call can settle H1 outright.
- **DTC pattern.** This car has **TGV deletes, a fully catless exhaust, and an exhaust-AVCS
  delete** — all of which *should* set codes. Read the DTCs. Codes present ⇒ nobody suppressed
  them ⇒ consistent with a stock ROM. Codes conspicuously *absent* ⇒ someone disabled monitors in
  the ROM ⇒ the ROM is tuned. Supporting evidence, not proof, but it is free and immediate.

### F3. Attempt a read on the '04 WRX (free, ASYMMETRIC — understand before spending the time)

The defs show the '04 USDM Impreza WRX is `68HC16Y5` / `wrx04` — **16-bit**, and this clone is
*documented* to fail on 16-bit K-line.

- **Read SUCCEEDS ⇒ highly decisive.** The clone performs a full reflash-mode unlock, on the
  protocol it is supposedly worst at. H2 dies; the Forester's ECU is the problem.
- **Read FAILS ⇒ tells us almost nothing.** Confounded three ways: the clone's known 16-bit
  limitation, a possibly-married WRX (Syed notes it was modified when purchased), and H2 itself.

Worth the 20 minutes *only* because the success branch is so strong. Note a tuned ROM still reads
normally unless explicitly locked, so "the WRX was modified" does not by itself predict failure.

### F4. Borrow rather than buy (free, needs a person not a purchase)

A COBB AccessPort states a marriage **explicitly** — it is the only direct diagnosis of H1. Any
genuine J2534 tool separates cable from ECU. Both are common among independent Subaru shops and
local enthusiasts; Syed is in the trade. **Borrowing costs nothing; buying is what we are avoiding.**

### F5. If H1 is confirmed — `shbootmode` is the budget answer

**Bench boot mode needs no tool Syed does not already own.** EcuFlash loads `shbootmode` (visible
in its startup log) and drives it through the Openport. SH boot mode is a **hardware mode of the
Renesas SH7058 itself**, entered by pin strapping and addressed over SCI, so it talks to the chip's
own bootloader and **never touches the ECU application's seed/key**. Any software lock — COBB
marriage, EcuTek security — is irrelevant to it.

Cost: labour and care, not money. Requires removing and opening the ECU and wiring to specific
pins, and it is unforgiving of mistakes. **The exact SH7058 pin strapping and SCI wiring must come
from a verified source — do not work from memory or inference.**

## Can a marriage/lock be removed?

Distinguish the two, because they are not the same mechanism:

| | what it locks | removal |
|---|---|---|
| **COBB AccessPort "marriage"** | Binds the **AccessPort** to one VIN. Primarily an anti-piracy measure on the *tool*. | Unmarry via the AP that married it; COBB support can sometimes release a unit. **Generally does NOT lock the ECU against third-party reads** — so this is a weaker candidate for our signature than it first appears. |
| **EcuTek security lock** | A deliberate lock applied **to the ECU** so other tools cannot read the map — tuners use it to protect their work. | Needs EcuTek ProECU and normally the tuner who applied it. Realistically not removable without paying someone. |

**Given the failure is at key validation, an EcuTek-style ECU lock fits better than a COBB
marriage.** And the practical consequence for a budget build is the same either way: **`shbootmode`
bypasses both**, because a software lock cannot defend against the silicon's own bootloader.

## Immobilizer — VERIFY BEFORE BUYING ANY ECU

**Unresolved, and it must not be assumed.** If this car has a factory immobilizer, a replacement
ECU is **not** plug-and-play — the immobilizer and ECU must be matched and the keys re-learned,
which normally needs a dealer-level tool and can cost more than the ECU. That risk alone can
eliminate the replacement-ECU option economically.

Free checks, in order:
1. **Cluster indicator** — a key-shaped or `SECURITY` telltale that blinks with the ignition off.
2. **Antenna ring** around the ignition lock cylinder (immobilizer transponder coil).
3. Wiring diagram / fuse-box legend for an immobilizer control module.

Do not buy a used ECU until this is settled and the seller's ECU ID is confirmed to be an AT member
of the `3B1250xx06` family (see `defs/README.md`) — and that it is not itself married.
