# Pilot mix v2 — 20-pair review sample (C3 round 2)

## 1. (synthetic | modern_general | deep | ignition_knock)
**symptoms:** Engine knocks during VE table calibration; global spark advance map is plausibly conservative for the powerplant.

**diagnosis:** Knock is detonation responsive to timing rather than preignition, which would require thermal intervention and would not be eliminated by retard; timing retard is required to kill knock and enable calibration with a homogenous air/fuel ratio.

**change:** Retard spark timing in increments of at least 2 or 3 degrees in speed-density breakpoints in the vicinity of the active VE cell(s).

**outcome:** Detonation disappears.

## 2. (synthetic | modern_general | deep | ve_load)
**symptoms:** Persistent lean condition and unstable idle traced to an unmetered vacuum leak in the intake tract. MAF-based fueling continues to run lean despite trim limits being reached.

**diagnosis:** The causal mechanism is that MAF sensors measure only the air passing through the sensor and cannot account for additional air entering downstream. Alternatives like velocity air meters are excluded because they restrict inlet airflow and create a pressure drop at the metering door. Speed-density measurement is selected because it deduces air mass from manifold pressure, engine speed, and ambient air temperature, and automatically compensates for inlet air losses or leaks.

**change:** Switch air measurement strategy to speed-density and adjust the injection pulse width table for the current combination of engine speed and manifold pressure to reflect the corrected load model.

**outcome:** The ECU automatically compensates for the inlet air leak, stabilizing the air/fuel ratio and idle behavior without introducing the airflow restriction associated with velocity air meters.

## 3. (synthetic | modern_general | deep | fuel_type)
**symptoms:** ECU calculates an incorrect AFR value when the analog input reads 3.00V from the X-Series gauge.

**diagnosis:** ECU analog scaling formula is misconfigured relative to the gauge output.

**change:** Update ECU scaling to use the formula AFR = (2.3750 * Volts) + 7.3125.

**outcome:** ECU calculates 14.44 AFR at 3.00V, matching the value in the 0-5V Analog Output Scaling Table.

## 4. (synthetic | modern_general | deep | idle)
**symptoms:** A 2-wire PWM idle air control valve only responds to duty cycles above 76%, reaching fully open at 83%. This leaves a negligible window for closed-loop idle management. Adjusting the PWM frequency (tested near 120 Hz) produces no change in valve behavior.

**diagnosis:** The restricted low-end duty cycle response indicates inadequate flyback protection for the inductive valve coil. The forum identifies that relying solely on the ECU board's diode recirculation can be insufficient for this valve type, causing the driver to struggle with low-duty-cycle pulses.

**change:** Installed a 1N4007 flyback diode directly across the IAC valve terminals.

**outcome:** The controllable duty cycle range expanded from >76% down to 20%–80%, restoring full authority for closed-loop idle control.

## 5. (synthetic | modern_general | deep | boost)
**symptoms:** With a pure mechanical boost controller, boost engages unpredictably at partial throttle, creating a risk of stoichiometric boost and part-throttle fuel cut (PTFB) scenarios that degrade drivability and risk engine damage.

**diagnosis:** Pure MBC setups lack throttle-position-dependent mapping, causing boost to come on "when it wants to" rather than following a controlled, load-appropriate ramp.

**change:** Configured the UTEC boost map to output 500 in the 100% TPS column and ramp down to 150 in the 60% TPS column, using those values to drive the GM 3-port solenoid in interruption mode for wastegate control.

**outcome:** Manifold pressure now ramps smoothly in direct proportion to throttle input, completely preventing PTFB conditions and improving partial-throttle drivability.

## 6. (synthetic | modern_general | deep | fuel_type)
**symptoms:** Engine bogs down when stepping on the throttle on a gasoline engine.

**diagnosis:** Rapid throttle movement increases intake manifold pressure, which reduces the air's capacity to hold evaporated fuel. Fuel deposits on the intake runner walls, creating a temporary lean condition that causes the bog.

**change:** Tuner adjusts the 'TPS/TPS acceleration extra fuel' table, where the X-Axis is the 'From' TPS and the Y-Axis is the 'To' TPS. The tuner sets the enrichment for a TPS change from 0% to 1% to add 10% fuel, and for a change from 0% to 3% to add 17% fuel, accounting for the non-linear behavior of the throttle body.

**outcome:** The enrichment corrects the lean condition and keeps the engine from bogging down. The tuner verifies drivability, noting that the engine runs without noticeable bogging at AFRs between 9 and 16 (possibly 17), and stops tuning once no bogging is observed, as the goal is drivability rather than perfect AFRs during enrichment events.

## 7. (synthetic | modern_general | deep | fuel_type)
**symptoms:** After installing an additional injector controller (AIC) for a boosted application, the engine runs lean under load, and the tuner must establish a baseline fuel strategy before advancing timing.

**diagnosis:** The lean condition occurs because the primary fuel map does not account for the increased air mass from forced induction. The excerpt states that a turbocharger adds approximately 10 percent torque per pound of boost, which directly necessitates a proportional fuel increase. Alternatives like advancing ignition timing first are excluded because the tuning protocol explicitly requires working from rich to lean before increasing timing advance to maintain safe combustion.

**change:** Configure the AIC to deliver at least 10 percent extra fuel per-psi of boost, correcting for any differences in injector fuel-flow capacity. If the stock pulse width is unknown, measure it with a pulse width meter or estimate the additional horsepower per-psi and apply the fuel requirement formula for a 12.0–12.5 AFR target per cylinder.

**outcome:** The AFR under boost stabilizes within the 12.0–12.5 range, allowing the tuner to safely progress toward more timing advance without lean conditions.

## 8. (synthetic | subaru | deep | maf)
**symptoms:** Intermittent hesitation and limp-mode behavior, secondary turbo boost spiking to 22 psi in 3rd gear then tapering (vs. 18 psi in 1st/2nd gear), and a stored code 23 for the MAF sensor without a CEL. Data logging showed the ECU hard-learning to add about 8-12% of fuel, indicating a lean condition.

**diagnosis:** The tuner had altered the MAF calibration despite the 2001 Subaru Legacy B4 retaining a stock MAF sensor and housing. Forum analysis confirmed that stock intakes do not require MAF calibration changes, and the modified calibration was likely causing the lean fuel trims and triggering the stored code.

**change:** Reverted the MAF calibration to stock values in the Project Lambda tune.

**outcome:** The hesitation, limp mode, and boost spike persisted, confirming the calibration adjustment was not the root cause. Post-revert logging revealed the MAF voltage dropping below 0.3V for a split second under load, shifting the diagnostic focus from a tuning error to a suspected physical wiring harness break or connector issue.

## 9. (synthetic | modern_general | deep | ignition_knock)
**symptoms:** A forced-induction engine running on street gasoline exhibits sub-optimal spark timing and flat torque output at mid-to-high load, with frequent knock sensor activity and no measurable gains from bolt-on breathing modifications.

**diagnosis:** The performance bottleneck is artificial boost-control and knock-limited spark timing designed to prevent detonation and protect engine components from severe mechanical or thermal loading. Alternatives such as MAF scaling, idle air control, injector dead-time adjustments, or VE/load model recalibration are excluded because the engine is not airflow- or fuel-delivery limited; at stock power levels, forced-induction engines are rarely constrained by volumetric efficiency. The EMS is actively retarding timing as a detonation-prevention strategy, not due to sub-optimal default tuning or sensor scaling errors.

**change:** Switch to high-octane fuel to remove the detonation constraint. On a load-holding dynamometer, hold the engine at a specific RPM and first optimize the air/fuel ratio across the board with conservative ignition timing. Then, perform a spark hook test: advance spark timing incrementally at each breakpoint of engine loading available in the ECM’s timing table until the torque readout indicates maximum torque, at which point torque begins to drop or “hook.”

**outcome:** Torque output increases at each tested load breakpoint, and the EMS is able to advance spark timing past the previous knock-limited baseline without triggering detonation protection strategies. The engine successfully converts the higher octane fuel into measurable torque gains by eliminating the artificial timing retard.

## 10. (synthetic | modern_general | deep | idle)
**symptoms:** Engine idle speed drops below target and becomes unstable when the A/C compressor engages, risking a stall.

**diagnosis:** The base idle control strategy lacks the transient response required for sudden parasitic loads. Adjusting fuel trims or volumetric efficiency tables is excluded because the air-fuel ratio remains correct; the deficiency is purely in idle airflow positioning. The excerpt confirms that `setIdleAdd(percent)` directly adds a percentage to idle (incl. open loop), providing the correct causal mechanism to compensate for load-induced airflow deficits without altering base calibration.

**change:** Implement a Lua `onTick` function that calls `setIdleAdd(percent)` with a positive percentage value when an A/C request is detected, applying an additive offset to the idle target.

**outcome:** Idle RPM stabilizes at the target value during compressor engagement, eliminating hunting and stalling risk as the additive percentage directly increases idle airflow to match the new load condition.

## 11. (synthetic | modern_general | adequate | ve_load)
**symptoms:** Tuner observes an engine operating at part throttle and lower speeds with a stoichiometric mixture; the goal is to maximize fuel efficiency.

**diagnosis:** At part throttle, the engine operates at lower volumetric efficiency. Real-world combustion conditions, including swirling air/fuel masses and rapid changes, cause imperfect mixing that risks blowing unburned fuel out the exhaust. Richening the mixture is excluded because adding extra fuel would result in wasted unburned hydrocarbons when the goal is efficiency, whereas the objective is to ensure every fuel molecule is burned.

**change:** Lean out the mixture from the stoichiometric ratio (increase the ratio of oxygen to fuel) by adjusting the VE table values for part-throttle RPM and load breakpoints.

**outcome:** The mixture adjustment improves the likelihood of making use of every last fuel molecule, resulting in maximum fuel efficiency.

## 12. (synthetic | modern_general | adequate | injectors)
**symptoms:** After converting a naturally aspirated engine to forced induction and installing larger injectors, the mixture is too rich in the light-load region.

**diagnosis:** The larger injectors fuel the top end effectively but cause over-fueling at light load.

**change:** Modify the load reading using an overlay map in the piggyback calibrator by selecting cell values that subtract a precise amount from the load signal.

**outcome:** The ECM provides less fuel to the engine by shortening the injector pulse width.

## 13. (synthetic | modern_general | adequate | ve_load)
**symptoms:** The engine is not meeting the desired air/fuel target under relatively steady state conditions, with no acceleration enrichment or overrun fuel cut active.

**diagnosis:** Dynamic airflow effects in the inlet are causing measurement errors; the VE Table is the correct mechanism to adjust for these effects and correct the measured airmass.

**change:** Tune the VE Table to apply corrections to the fuel injection.

**outcome:** Corrections to the fuel injection are applied, allowing the engine to meet the desired air/fuel target.

## 14. (synthetic | modern_general | adequate | fuel_type)
**symptoms:** The tuner connects the USB cable to the rusEFI ECU while the car is off, then turns the ignition on. TunerStudio connects, but the SD card indicator shows 'SD card reading mode', and the tuner is unable to enable SD card logging.

**diagnosis:** The ECU determines SD card mode based on the power-up sequence. Because the ECU was first powered via USB, it entered SD card reading mode rather than logging mode.

**change:** The tuner disconnects the USB cable, powers the ECU via the car battery, and then reconnects the USB cable.

**outcome:** The TunerStudio indicator changes to 'SD card logging mode', allowing the tuner to enable logging to the SD card while connected to the PC.

## 15. (synthetic | modern_general | adequate | sensors)
**symptoms:** After increasing boost on the 2009 Subaru Impreza WRX (SADM, MT), the Check Engine Light illuminates with DTC P0108 during high-load pulls.

**diagnosis:** The manifold pressure sensor reading exceeds the threshold defined for the CEL, triggering the MAP sensor high input fault.

**change:** Tuner raises the threshold in the `Manifold Pressure Sensor Limits (CEL)` table.

**outcome:** DTC P0108 and the associated CEL no longer set during high-load pulls at the new boost level.

## 16. (organic | subaru_ej)
**symptoms:** Suspected excessive AVCS overlap (10*) with high-flow header causing fuel loss during overlap.

**diagnosis:** Reducing overlap to 5* and adjusting timing should improve efficiency and smoothness.

**change:** Set AVCS to 5* at highway RPM/loads; increased timing by 2* to 40*; installed front lip.

**outcome:** 31.25 mpg on highway trip.

## 17. (organic | subaru)
**symptoms:** hesitation and goes into almost a limp mode intermittently; 18psi on secondary turbo in 1st and 2nd gear but in 3rd it spikes up to 22; stored code 23 for the MAF sensor; idle LTFT 8-12%; MAF voltage drops below 0.3V for a split second

**diagnosis:** MAF calibration has been changed when the car is hitting boost... could this possibly be the issue; later suspecting a wiring issue on the maf harness

**change:** maf calibration set back to stock; tugging/wiggling the connector and harness

**outcome:** Didn't help my issue unfortunately; didn't really notice any changes

## 18. (organic | subaru)
**symptoms:** Partial-throttle boost causing drivability issues; transient boost spikes reaching ~20psi with shift knock during flat-foot shifts; EBC trading response for stability.

**diagnosis:** EBC cannot react fast enough to highly transient conditions; a mechanical boost controller provides a hard, unexceedable limit and faster response, while EBC handles part-throttle taper.

**change:** Installed Hallman Evo RX MBC in parallel with a GM 3-port interruption solenoid controlled by UTEC; mapped UTEC boost table (500 at 100% TPS, 150 at 60% TPS); later removed MBC bleed hole and adjusted UTEC map to 78-100 duty cycle.

**outcome:** Boost spikes reduced from ~3psi to <1psi; PTFB completely eliminated; boost tapers to ~10psi at 60% TPS and ~17psi at 90% TPS; hard limit set at 19psi; system described as 'rock solid' and 'more stable'.

## 19. (organic | subaru_ej)
**symptoms:** city MPG suffers

**diagnosis:** rubber bushings that expand over time and drag

**change:** Regreasing all of the caliper pins and removing the rubber bushings

**outcome:** ~1mpg gain city

## 20. (organic | subaru_ej)
**symptoms:** High knock sum (#4 double #2, 200+ and 100+), poor clutch modulation/lurching at low load

**diagnosis:** Suboptimal AVCS advance mapping causing excessive knock and drivability issues

**change:** Modified AVCS table: reduced advance in low load, ran 30 degrees below 1.00 load between 1600-2400 rpm

**outcome:** Knock sums dropped to 38 (#2) and 36 (#4); smooth clutch engagement, no lurching
