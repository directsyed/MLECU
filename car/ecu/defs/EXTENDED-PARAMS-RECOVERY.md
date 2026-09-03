# Extended-parameter recovery for `3B12504206` (A2WC411D): and the live-validation gate

## What this is

Our ECU is absent from the RomRaider logger def (the one AT calibration revision, rev 42, was never
contributed), so RomRaider offers it **zero extended parameters**: the RAM channels that VE/timing/
knock tuning needs (`Feedback Knock`, `Target Boost`, `CL/OL Fueling Target`, `IAM`, injector PW/
latency, `Engine Load`, Turbo Dynamics). Its siblings all have them.

`extended_param_recovery.py` reconciles each param's RAM address **across the `3B125` family**, the
same way `romread` reconciles table addresses across sibling defs: our ECU's address = the address
the family agrees on. Result (`recovered-3B12504206.report.json`, `…logger-fragment.xml`): **all 57
params reconcile at HIGH confidence**, ≥5 non-outlier siblings (revs 41/42-MT/43, both
transmissions) agree on each, and our rev-42 sits inside that consensus. The only dissent is the
**rev-40** members (`…04006`/`…84006`), whose RAM block is shifted a few bytes, the known outlier,
excluded from the vote.

## Why this is now allowed (it wasn't in July)

`IDLE-LOG-PROFILE.md` refused to graft sibling RAM addresses: *"'often' is not 'provably'"* and *"do
not before the ROM read is solved."* Both blockers are gone (2026-08-16): the ROM is read, and the
family demonstrably shares one RAM layout. Per Syed's standing directive, we optimize past that
pre-data refusal.

## The honest caveat: this is a strong prior, NOT proof

- The addresses are **SSM2 runtime RAM addresses**, not ROM offsets, so there is **no clean ROM
  cross-check** (the ROM holds the code that writes these RAM locations, but the SSM2↔SH7058-RAM
  addressing convention makes a binary scan unreliable). The evidence is family agreement.
- The rev-40 outlier **proves RAM layout CAN shift between revisions.** Unanimous rev-41→43 agreement
  makes it very likely our rev-42 matches (it is sandwiched), but "very likely" is not "measured."
- **Therefore every recovered channel is UNVALIDATED until it reads sane on the live engine.** A
  plausible-but-wrong RAM read is the worst failure mode for a layer that consumes these numbers.

## The live-validation gate (Syed, a short session; a channel is trusted only after it passes)

Splice `recovered-3B12504206.logger-fragment.xml` into the logger def (each `<ecu id="3B12504206">`
line into its matching `<ecuparam>`; conversions are shared), restart RomRaider, select the recovered
params, and log **idle + a light rev + a brief light-load pull**. Confirm, per channel:

| channel | passes if | fails ⇒ |
|---|---|---|
| **IAM** | ≈ 1.00 on a healthy warm engine (0–1 range) | drop, wrong address reads garbage |
| **CL/OL Fueling** | reads the OL value cold, flips to the CL value (8) once warm | drop |
| **Fuel Injector #1 Pulse Width** | agrees with standard `P21` (log both; should track) | drop |
| **Feedback Knock Correction** | ~0 with no audible knock; goes negative under real knock | drop |
| **Target Boost / Boost Error** | Target ≈ the boost map; Error ≈ (target − actual) | drop |
| **Closed Loop Fueling Target** | ≈ 14.7 at idle/cruise closed loop | drop |
| **Engine Load (4-byte)** | tracks the standard `P200` load | drop |

A channel that fails validation is **dropped, not trusted.** Only validated channels are then added
as canonical roles in `car/ecutune/logparse/schema.py` (`feedback_knock`, `target_boost`,
`target_afr`, `iam`, `manifold_pressure`, `avcs`, …) so the deterministic layer and the VE build can
consume them. Until then they are candidates only.

## Reproduce
```bash
cd car/ecu/defs && python3 extended_param_recovery.py
```
Re-run any time the family def changes. `recovered-3B12504206.report.json` carries the per-param
votes + confidence for the validation step.
