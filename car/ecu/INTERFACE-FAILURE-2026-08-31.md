# J2534 interface died at flash start — 2026-08-31

**Status: OPEN.** The ECU is fine. The interface is not.

## What happened

Syed connected the Washinglee Openport 2.0 clone (serial `TAhJALxt`, FW `1.17.4877`), loaded
`CANDIDATE_B_maf-plus-timing_2026-08-30.bin` in FastECU and started the flash.

- Windows reported **"USB device has malfunctioned"** the instant the flash began
- progress stuck at **0%**
- **the interface's LEDs were not lit at all**
- FastECU force-closed, green connectors removed, **car started and runs normally**
- after a reboot with driver-signature enforcement disabled: **no LEDs on the OBD port, and the
  PC no longer enumerates the device at all**

## The ECU was never touched

Stuck at 0% with a dead interface means nothing was transmitted. The D28 hazard — an erase that
is sent unconditionally, leaving a page erased and unprogrammed — requires the tool to reach a
programming session and send the erase. That cannot happen through an interface with no power.
Confirmed empirically: the car runs.

**This failed at the single luckiest moment available.** The same failure 40% into a write would
have left a half-erased ECU and a car that does not start.

## Most likely cause: a ground loop through the OBD port

The pre-flash checklist said **"battery charger on, laptop on AC"** (`docs/ROADMAP.md`, and the
footer of every change report). That puts **two mains-earthed devices** — the laptop PSU and the
battery charger — bonded together through the OBD connector's ground pin, with the interface in
the middle.

A J2534 clone has **no galvanic isolation**, minimal TVS/ESD protection and a cheap regulator on
pin 16 (+12 V from the car). Any potential difference between the two earths flows through the
interface's ground, and the moment of highest stress is exactly when the tool switches into
programming mode and the current draw changes — which is when this died.

This is a well-known failure mode for OBD interfaces generally and clones specifically. It is not
proof, but it is the hypothesis that fits the timing, the symptom, and our own procedure.

**Checklist corrected 2026-08-31: the laptop runs on its OWN BATTERY, fully charged.** The
battery maintainer on the car stays (it prevents a voltage sag mid-write) — it is the only thing
that should be on mains. A Subaru ROM write takes a few minutes; a charged laptop will not die in
that window, and the ground loop is the larger risk.

## Contributing factor: it is a clone

`Washinglee Openport 2.0 clone` is recorded in `ROM-READ-BLOCKER.md` and
`FASTECU-SH7058-KLINE-BUG.md` as the interface for every read and all three flashes. Clones of
this design omit isolation and protection that the genuine Tactrix unit has. It also already has
a known defect on this car: **EcuFlash's SecurityAccess is rejected on it even with the green
connectors joined** (retested 2026-08-29), which is why FastECU is the only usable tool.

## Diagnosis order before replacing anything

1. **Check the car's OBD / cigarette-lighter fuse.** If the interface shorted on its way out it
   may have taken the fuse with it — and a dead OBD port also produces "no LEDs", which would
   mislead the diagnosis. This must be checked before any replacement is plugged in.
2. Different USB cable, different port, no hub.
3. Device Manager with hidden devices shown — does anything appear/disappear on plug-in?
4. Heat or smell at the connector shell.

**No LEDs when connected to the OBD port is close to conclusive on its own**: pin 16 supplies
+12 V independently of USB, so a device that does not light there has lost its power section —
unless the fuse in step 1 is blown.

## Recommendation

Replace with a **genuine Tactrix Openport 2.0**, not another clone. The argument is not brand
loyalty, it is exposure: several more writes are scheduled (timing pass 2, MAF iteration 4 on
real high-airflow data, and whatever those reveal). A clone dying mid-write costs a bricked ECU,
a tow and a replacement + reflash. That dwarfs the price difference, and this incident is the
demonstration rather than a hypothetical.
