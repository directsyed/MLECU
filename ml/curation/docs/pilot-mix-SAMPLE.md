# Pilot mix v1 — 20-pair review sample (C3 final)

## 1. (synthetic | modern_general | deep | maf)
**symptoms:** Airflow calculations for the turbocharger inlet show errors when applying high-temperature engine cycle properties to the intake tract.

**diagnosis:** Air flow before it enters the engine, including inlet flow in turbochargers, is closer to standard temperature and requires different air properties than the high-temperature engine cycle.

**change:** Apply standard air property values for inlet flow in turbochargers: specific heat ratio k = 1.4, cp = 1.005 kJ/kg-K, cv = 0.718 kJ/kg-K.

**outcome:** Air property values correctly reflect standard temperature conditions for pre-engine airflow, distinct from the engine cycle.

## 2. (synthetic | modern_general | deep | injectors)
**symptoms:** Inconsistent fuel delivery and air-fuel ratio fluctuations under varying intake manifold pressures.

**diagnosis:** The fuel pressure drop across the injectors is not remaining constant.

**change:** Configure the pressure regulator to maintain line pressure at a fixed value of 270 kN/m² (39 psi), referenced relative to manifold pressure.

**outcome:** The fuel pressure drop across the injectors remains constant despite manifold pressure variations.

## 3. (synthetic | modern_general | deep | idle)
**symptoms:** Momentary RPM drop when the air conditioning compressor engages at idle.

**diagnosis:** The sudden mechanical load exceeds the response speed of the standard IAC stepper-motor logic, which cannot bypass air fast enough to maintain target idle speed. Relying solely on IAC correction is excluded because the excerpt states the IAC system 'may not be fast enough to deal with air conditioning–induced load changes at idle without a bothersome momentary drop in rpm.' The causal mechanism is insufficient proactive load compensation; the EMS must instead switch to a dedicated speed-loading cell optimized for AC engagement.

**change:** Configure user-defined nonlinear granularity to create RPM and loading breakpoints that are closer together around the idle range, and optimize the specific AC speed-loading cell by adding a little more timing or fuel.

**outcome:** The idle stabilizes almost instantly upon AC engagement, eliminating the momentary RPM drop as the EMS immediately applies the optimized cell parameters.

## 4. (synthetic | modern_general | deep | fuel_type)
**symptoms:** Elevated hydrocarbon emissions measured in the exhaust stream, with analysis indicating residual fuel originating from wall quenching regions.

**diagnosis:** Residual hydrocarbons left unburned come primarily from crevices in the vessel walls. The gap between the piston crown and cylinder liner forms a 'corner' geometry where the liner provides additional local flame cooling, likely increasing the quenching distance for this geometry above the typical two-wall quench distance value of 0.2 to 0.6 mm.

**change:** Reduced the crevice volume of the piston crown to liner gap to minimize the region where flame quenching prevents combustion.

**outcome:** Hydrocarbon emissions decreased, consistent with the correlation that crevice volume impacts HC emissions, as reducing the quenching region limits the source of residual hydrocarbons that diffuse into burned gases and oxidize.

## 5. (synthetic | modern_general | deep | sensors)
**symptoms:** Tuner observes high computational load in the heat transfer model and questions whether gas radiation terms are necessary for cycle-integrated analysis of a spark-ignition engine.

**diagnosis:** Gas radiation is proportional to T_g^4 and falls off more rapidly than convective heat flux as gas temperatures fall; estimates for engine combustion gases at peak conditions indicate gas radiation is only ~5% of peak convective heat transfer.

**change:** Removed gas radiation terms from the cycle-integrated heat transfer calculation.

**outcome:** Cycle-integrated heat transfer estimates remained accurate, as gas radiation can be neglected when integrated over the cycle.

## 6. (synthetic | modern_general | deep | injectors)
**symptoms:** Medium-swirl DI diesel engine at 2600 rev/min with fuel delivery of 75 mm³/cycle exhibits high engine-out NOx emissions. Tuner notes that attempts to modify squish-swirl interactions have been inconclusive due to complexity.

**diagnosis:** Injection timing controls the crank angle of combustion start. Retarded injection is the established mechanism to reduce NOx, as it shifts combustion phasing. Adjusting squish-swirl is excluded because unraveling the squish-swirl interaction is challenging. The current start-of-injection timing is too advanced relative to the retarded position required for NOx control.

**change:** Retard the start-of-injection timing.

**outcome:** Engine-out NOx emissions decreased substantially. Brake-specific fuel consumption (bsfc) increased with a modest penalty. Particulate mass emissions and smoke increased.

## 7. (synthetic | modern_general | deep | ve_load)
**symptoms:** Vehicle enters limp mode under heavy load with throttle position limited to less than 20 percent; turbo or supercharger conversion installed.

**diagnosis:** The turbo conversion increases engine airflow beyond the limits defined in the EMS safety model. The EMS uses feedback from MAF or MAP sensors to verify actual engine loading against predicted loading. When airflow exceeds the values in the maximum airflow table, the ECU concludes there is a serious problem with the ETC system and enters limp mode to prevent unintended acceleration. The excerpt notes that turbo conversions are nearly impossible on ETC engines without reprogramming this table, as the stock thresholds are too low for the increased flow.

**change:** Reprogram the maximum airflow table to allow higher flow rates under heavy load. Increase the table values to approximately 20 percent above the expected maximum flow for the specific combination of stock and modified parts and boost levels.

**outcome:** Limp mode is prevented under heavy load conditions; throttle control is restored, allowing the engine to utilize the increased airflow without triggering the fail-safe limit.

## 8. (synthetic | modern_general | deep | ve_load)
**symptoms:** At low RPM and part-throttle cruise, the ECU logs high manifold pressure but the engine runs poorly with incorrect fueling and hesitation.

**diagnosis:** The long-duration cam profile causes late intake valve closing, allowing the intake mixture to pump back into the intake manifold at small throttle openings. This pump-back phenomenon raises manifold pressure (lowers vacuum) without increasing actual airflow. The ECU's load model misinterprets the high manifold pressure as heavy load, commanding incorrect fueling. MAF scaling or fuel trim adjustments are excluded because the manifold pressure sensor is reading accurately; the error stems from the VE/load model's assumption that high pressure equals high airflow, which is invalidated by valve overlap and reverse flow.

**change:** Reduce the volumetric efficiency (VE) values in the low-RPM, part-throttle cells of the load model table to compensate for the artificially high manifold pressure reading caused by pump-back.

**outcome:** The ECU's fueling command aligns with actual airflow, correcting the air/fuel ratio to the target range and eliminating hesitation despite the persistently high manifold pressure.

## 9. (synthetic | modern_general | deep | ve_load)
**symptoms:** Under progressive throttle application, the turbocharged engine exhibits hesitation, inconsistent torque delivery, and elevated exhaust gas temperatures, indicating improper fuel delivery across the operating range.

**diagnosis:** The DFI system calculates fueling using a 16x16 injection pulse width matrix indexed by MAP sensor load and crank trigger RPM, rather than a traditional volumetric efficiency (VE) table. Because the architecture explicitly lacks a VE table, the ECU cannot auto-scale fueling based on airflow models; it relies entirely on explicit pulse width values for each of the 256 load/speed combinations. Relying on VE-based scaling or closed-loop fuel trims is excluded because the DFI architecture requires manual cell-by-cell population via laptop, and uncalibrated cells risk dangerously lean mixtures under load. The root cause is an unpopulated injection pulse width matrix that fails to deliver the correct fuel mass as load and speed increase.

**change:** Connected a laptop to the DFI interface connector and used Calmap to populate the 16x16 injection pulse width matrix. Established a safe start-up map, then tuned zero-load pulse widths across all RPMs. Set light-load values, then gradually increased engine load at various speeds while monitoring air/fuel ratios, exhaust gas temperatures, and dyno power/torque. Adjusted pulse widths cell-by-cell to achieve lean best torque at heavier loads, enriching only where fuel cooling was required, while strictly avoiding dangerously lean mixtures in any cell.

**outcome:** The calibrated matrix delivered precise injection pulse widths across all 256 load/speed combinations, eliminating lean conditions and optimizing the air/fuel ratio for maximum torque without detonation risk.

## 10. (synthetic | modern_general | deep | fuel_type)
**symptoms:** Knock sensor triggers timing retard, exhaust gas temperatures exceed safe limits, and torque is capped at wide-open throttle.

**diagnosis:** EGR is active at high load, displacing fresh air and limiting maximum bmep, while the mixture is too lean for peak torque and knock prevention. Figure 7.1 and Table 7.1 show that WOT operation requires 0% EGR to maximize airflow and enrichment to 7.2% fuel mass to maximize torque, prevent knocking, and reduce exhaust temperature.

**change:** Disable EGR flow at WOT and enrich the air/fuel ratio to target 7.2% fuel mass in the in-cylinder mixture per Table 7.1.

**outcome:** Knock-induced timing retard ceased, exhaust gas temperatures decreased, and maximum torque increased, directly reflecting the excerpt's stated effects of high-load enrichment and EGR elimination.

## 11. (synthetic | modern_general | adequate | fuel_type)
**symptoms:** Tuner observes an AFR reading of 20.0 while the vehicle is decelerating in gear at high RPM with the throttle completely lifted.

**diagnosis:** The excerpt identifies this condition as fuel cutoff, which occurs when lifting off the throttle during deceleration in gear at high RPM. The chart lists the approximate AFR for fuel cutoff as 20.0, which is lean.

**change:** Tuner recognizes the reading as normal fuel cutoff behavior and excludes this region from fuel tuning adjustments.

**outcome:** Tuner avoids unnecessary fuel enrichment, confirming the lean reading of 20.0 is expected during fuel cutoff.

## 12. (synthetic | modern_general | adequate | injectors)
**symptoms:** Tuner attempts to configure the microRusEFI to batch fire eight injectors.

**diagnosis:** The microRusEFI is primarily a 4-cylinder ECU. Configuring two injectors per output will burn the ECU.

**change:** Abort the 8-injector batch fire configuration; do not wire two injectors per output.

**outcome:** ECU hardware is preserved; configuration remains within the safe limits of the 4-cylinder primary design.

## 13. (synthetic | modern_general | adequate | injectors)
**symptoms:** Excessive combustion noise and prolonged cranking during cold starts, with unstable RPM in the lower speed and load range.

**diagnosis:** The ECU controls the solenoid valve energization timing to define the start of injection and injected fuel quantity. In the lower speed and load range, suboptimal timing causes uncontrolled pressure buildup before the nozzle-opening pressure is exceeded, increasing noise and degrading cold-start performance. Mechanical line-length mismatch is excluded because the high-pressure lines are specified as equal-length seamless steel tubes, and cam timing error is ruled out because start of injection is synchronized with piston position via the incremental trigger wheel. The causal mechanism is improper ECU calibration of injection timing and quantity for low-load operation.

**change:** Adjust the start-of-injection timing and injected fuel quantity parameters for the lower speed and load range, utilizing the BIP (beginning of injection period) signal to balance out tolerances in the overall system.

**outcome:** Combustion noise is significantly reduced and cold-starting performance improves, with the integrated idle-speed governor maintaining stable RPM without surge.

## 14. (synthetic | modern_general | adequate | injectors)
**symptoms:** Significant fuel impingement is observed on the port walls, valve stem, and valve head, contributing to wall wetting.

**diagnosis:** Injection timing is aligned such that fuel is injected toward a closed intake valve, which causes much of the fuel to impinge on these surfaces.

**change:** Adjust the injection timing relative to the intake valve-lift profile to avoid injecting toward a closed intake valve.

**outcome:** Fuel impingement on the port walls, valve stem, and valve head is reduced.

## 15. (synthetic | modern_general | adequate | boost)
**symptoms:** Wideband sensor indicates a lean mixture under boost, risking lean-mixture damage.

**diagnosis:** The onset of boost increases cylinder density and power output, requiring additional fuel beyond the stock pulse width. Without compensation in the boosted speed-loading cells, the air/fuel ratio drops below safe limits.

**change:** Set the AIC to deliver at least 10 percent extra fuel per-psi boost in the fuel map pulse width for the target speed-loading cells that will be boosted.

**outcome:** Air/fuel ratio stabilizes at 12.0–12.5, eliminating the lean condition and protecting the engine from lean-mixture damage.

## 16. (organic | subaru_ej)
**symptoms:** Misfires on 1-2 cylinders at very light load, ~2600 RPM in 2nd/3rd gear, IPW @ 2.0ms.

**diagnosis:** Per-injector compensations adding too much fuel (10-16%) in low load zones causing misfire counts.

**change:** Reduced per-injector comps by 67%, then zeroed, then applied values from 2004 STI JDM ROM.

**outcome:** Seemed good on 30-minute test drive.

## 17. (organic | general)
**symptoms:** EGO corrections exceeding 3%, rich island at 10-18 TPS and 3500-4500 RPM, AFR variance across load/RPM cells

**diagnosis:** VE table requires cell-specific correction to stabilize EGO trims and eliminate rich/lean pockets

**change:** Applied VE correction pass focusing on rich cells, planning a final full sweep

**outcome:** EGO corrections reduced to ~3% across the table except the specified rich island

## 18. (organic | subaru_ej)
**symptoms:** Mid-20s MPG baseline; 3psi manifold backpressure at 2900 RPM / ~10 in/hg load

**diagnosis:** Exhaust restriction may be limiting efficiency; new exhaust may require different AVCS/timing calibration

**change:** Installed 3" turbo-back exhaust; tested AVCS 5°/40° ignition tune, then AVCS 10°/36° ignition tune

**outcome:** Backpressure dropped to 2psi; MPG recorded at 29.72 and 29.50 respectively; concluded 'exhaust = no real gain'

## 19. (organic | subaru_ej)
**symptoms:** MPG dropped to 28.94 after installing a Big 16G turbo, down from a 30.0 baseline.

**diagnosis:** The larger turbo produces a cooler, denser intake charge, increasing cylinder oxygen and requiring less ignition advance to prevent combustion before TDC.

**change:** Reduced ignition timing from 45° to 40° at 2800-3200 RPM; later optimized to 38°.

**outcome:** 30.98 MPG on the return leg; subsequent A-B-A tests confirmed 40° (29.88/28.19) outperformed 45° (29.45/27.15), and 38° yielded 30.85 MPG on a controlled A-B-A trip.

## 20. (organic | subaru_ej)
**symptoms:** city MPG suffers

**diagnosis:** rubber bushings that expand over time and drag

**change:** Regreasing all of the caliper pins and removing the rubber bushings

**outcome:** ~1mpg gain city
