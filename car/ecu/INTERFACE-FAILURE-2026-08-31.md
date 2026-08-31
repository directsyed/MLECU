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

## ⚠ FIRST HYPOTHESIS WITHDRAWN (2026-08-31, same day)

I proposed a ground loop. **Syed's actual setup rules it out:** the laptop was on its own
battery with no charger connected, and nothing was in the 12 V accessory outlet. Only a battery
pack was on the car. A ground loop needs two mains-referenced paths to circulate between; with
the laptop floating there is no return path through the USB ground, so no loop can form.

Recorded rather than deleted, in the same spirit as D30: the reasoning was sound for the setup
I assumed and wrong about the setup that existed. **The checklist change it prompted stands on
its own merits** — laptop on battery is still correct practice and costs nothing — but it is no
longer an explanation of THIS failure, and it should not be cited as one.

### Revised hypotheses, in order

1. **A transient on the 12 V rail from the battery pack.** Now the leading candidate, because it
   is the only mains- or supply-side variable that was actually present. Cheap chargers and
   maintainers — especially anything with a pulse/desulfation mode — can put spikes well above
   14 V on the battery terminals. Pin 16 of the OBD connector feeds the interface's regulator
   directly, and a clone has no TVS clamp in front of it. **Open question for Syed: what kind of
   pack — a mains-powered maintainer/charger, or a portable lithium jump pack?** A maintainer in
   desulfation mode is a very different risk from a passive lithium pack.
2. **The clone simply failed.** Random hardware mortality on an unprotected board, exposed by the
   one operation that stresses it: the mode switch into programming changes current draw and
   holds the bus hard. Hours of logging never stressed it that way.
3. **ESD during handling**, plugging into the OBD port.

Note the failure is on the **power section specifically**: the device does not enumerate on USB
(which powers it independently of the car) AND does not light on the OBD port (which supplies
+12 V independently of USB). Losing both supply paths at once points at the regulator/input
stage rather than at the FTDI or the PIC.

## Superseded: the ground-loop reasoning

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

1. **Measure the OBD port with a multimeter: pin 16 (+12 V) to pin 4 or 5 (ground).** Should read
   battery voltage, ~12.4 V. This settles the car side definitively in one minute and is far
   better than reasoning about fuses. A blown OBD fuse **sets no DTC** — nothing monitors that
   circuit; the connector's power exists for the scan tool, not for the ECU — so "no code" is not
   evidence the port is healthy.
2. **Try the interface on a different PC.** Rules out the laptop's USB stack and drivers in one
   step. Highest-value test after the multimeter.
3. **Watch Device Manager on plug-in** (View → Show hidden devices), and listen for the connect
   chime. "Unknown Device" or a USB\VID_0000 entry means the USB PHY is alive and it is a
   firmware/driver problem. **Literally nothing** means the device is not powering up at all.
4. Inspect the captive USB cable at the strain relief; check the connector shell for heat or
   smell.

**The tool is dead independently of the car.** Pin 16 supplies +12 V and USB supplies 5 V by
separate paths, and it responds to neither. A blown OBD fuse would explain the missing LEDs on
the car but cannot explain the missing USB enumeration. Step 1 therefore is not about diagnosing
the interface — it is about not plugging a new one into a faulty circuit.

## Measurements taken 2026-08-31, and two corrections to my reasoning

| measurement | result | meaning |
|---|---|---|
| CAR's OBD pin 16 → pin 4, DC volts | **12.7 V** | car side is healthy. Port live, fuse intact, wiring fine. A replacement can be plugged in safely. |
| DEVICE's OBD plug pin 16 → pin 4, Ω | **11 kΩ** | **NOT shorted.** The input stage is intact — this rules out the failure I thought most likely, and rules out the mode that would have taken the car's fuse. |

**CORRECTION 1 — "no LEDs on the OBD port" may prove nothing.** I treated it as near-conclusive.
The genuine Openport 2.0 can run from vehicle power for standalone SD logging, but **many clones
omit that and are USB-powered only**. If this clone is USB-powered, then no LEDs when connected
to the car alone is NORMAL behaviour, not evidence of death. The real evidence is the USB side:
it no longer enumerates on any PC.

**CORRECTION 2 — a genuine Openport 2.0 is not a practical replacement.** It has been out of
production for years and now sells for thousands. The earlier recommendation to "buy genuine" was
written without checking that, and it is not actionable. See the revised recommendation.

## Metering the INTERFACE itself

A meter can prove the interface is dead; it cannot prove it is alive. A shorted input is
conclusive; the absence of a short is not, because an open regulator and a dead microcontroller
both measure the same as a healthy board. Run these anyway — the shorted case is the most likely
one and it is the one that also endangers the next tool.

**Disconnect from BOTH the car and the PC first.** Resistance readings on a powered circuit are
meaningless and can damage the meter.

| measure | mode | healthy | failed |
|---|---|---|---|
| OBD pin 16 → pin 4 or 5 | Ω, then diode, **both polarities** | high (tens of kΩ+), or a diode drop one way and high the other | **near 0 Ω either way = input stage shorted** |
| USB plug: the two OUTER contacts (VBUS ↔ GND) | Ω | high; may drift upward as input caps charge | **near 0 Ω = shorted VBUS**, which is exactly what makes Windows report "USB device has malfunctioned" and shut the port down |
| OBD pin 4 → pin 5 | continuity | usually continuous (grounds bonded internally) | informational only |
| OBD pin 4/5 → USB connector shell | continuity | usually continuous | an open here means a broken ground in the captive cable |

**A short from pin 16 to ground is the signature to look for.** It explains the instant USB
complaint, the total absence of LEDs, and it is the failure mode that blows the car's OBD fuse on
its way out — so finding it also tells you to check that fuse before plugging anything else in.

Not measurable with a meter: the FTDI USB bridge, the PIC, and the K-line transceiver. Their
state cannot be inferred from resistance, so "no short found" ends the meter's usefulness and the
next step is a different PC.

## Recommendation (revised 2026-08-31)

A genuine Openport 2.0 is out of production and priced in the thousands, so "buy genuine" is not
an option. The realistic plan:

**Buy TWO of the exact same clone** — Washinglee Openport 2.0, the same model and seller. Two
reasons for the same model rather than a different one: this specific unit is *proven* against
this ECU with FastECU's `sub_ecu_denso_sh7058` profile, and clone firmware varies enough between
vendors that an unknown one may fail in an entirely new way on a car that is already awkward
(EcuFlash's SecurityAccess is rejected here regardless of cable). Two reasons for buying two:
they are cheap, and the project has several writes left. **Treat these as consumables, not
instruments.**

Keep the dead one. If it turns out to be a broken solder joint at the captive cable — a common
and very repairable failure — it becomes a **logging-only spare**. It logged for hours without
complaint and died the instant it was asked to write, so it never touches a flash again.
