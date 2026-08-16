# Community score-3 docs — retrieval-usefulness review (2026-08-16)

**What this is.** Syed's ruling (2026-08-15): keep the judge's ≥4 bar unchanged; recover value from
the score-3 community docs by *review*, not by moving the bar; nothing enters any retrieval index
without his sign-off. This file is that review — **recommendations only, nothing indexed.**

**What was reviewed.** All **95** community documents with `judge_score = 3` at 2026-08-16 (the 95
existing; the C2 overnight judge run adds more 3s later — they are NOT in this file and need the same
pass). Reviewed by Claude subagents in 8 batches under one fixed rubric (`community-3s-review-RUBRIC.md`; raw per-doc JSONL in
`community-3s-review-2026-08-16.jsonl`; the rubric text is also reproduced at the bottom), each doc read
in full including the 330 kB thread; ≥15% of verdicts spot-checked against the source text by the
orchestrating agent (all held).

**What "keep" means here.** *Would this thread be useful if RETRIEVED for the diagnostic queries the
project currently lacks answers to* — idle diagnosis (leak vs latency vs MAF vs flow), smoke testing,
healthy-idle MAF baselines, EJ20X-in-EJ255 mismatch, VE/timing correction from logs, RomRaider/Openport
procedure — judged as a forum post that would sit in the **separate, tier-tagged community index**
(Track D machinery, built tonight, switched off). Not prose quality.

**Honest limit (checklist §B6).** A text reviewer cannot know whether a fix actually worked. The
`markers` columns record *signals of verifiability* — outcome reported, causal chain present, numbers
with units+conditions, thread resolved, corroboration by more than one poster — **not correctness.**
A confidently wrong post with all five markers is indistinguishable from a correct one here.

## Counts

| | keep | drop | total |
|---|---|---|---|
| **all** | **28** | **67** | 95 |
| forum_legacygt | 11 | 17 | 28 |
| forum_msextra | 2 | 24 | 26 |
| forum_nasioc | 8 | 5 | 13 |
| forum_romraider | 5 | 14 | 19 |
| forum_speeduino | 1 | 7 | 8 |
| forum_subaruforester | 1 | 0 | 1 |

Retrieval value for the current gaps (all / keep): high 2/2 · medium 25/25 · low 68/1. Subaru-specific: 61/95.

Verifiability markers present (all / keep): outcome_reported 32/17 · causal_chain 56/27 · numbers_with_units_conditions 64/27 · thread_resolved 19/7 · corroboration 38/19

### Needs-alignment census — topics (all docs / keep docs)

| topic | all | keep |
|---|---|---|
| megasquirt_speeduino | 33 | 3 |
| generic_other | 30 | 3 |
| idle | 27 | 9 |
| romraider_ecuflash_tooling | 18 | 8 |
| boost_control | 17 | 9 |
| maf_scaling | 16 | 14 |
| timing_knock | 16 | 9 |
| wideband_afr | 15 | 9 |
| injector_scaling | 14 | 9 |
| ve_tune | 12 | 6 |
| vacuum_leak | 12 | 10 |
| logging_method | 11 | 7 |
| tgv | 10 | 7 |
| injector_latency | 9 | 6 |
| avcs | 5 | 3 |
| smoke_test | 5 | 4 |
| rom_read_flash | 2 | 0 |
| displacement_mismatch | 2 | 1 |
| ej20x_swap | 1 | 0 |

**Reading the census honestly.** The score-3 pile is dominated by generic/off-platform chat and
MegaSquirt/Speeduino config threads; the Subaru idle-diagnosis material the project actually lacks
(vacuum_leak, smoke_test, injector_latency, maf_baseline) is a small minority, and *no doc in the pile
supplies a healthy-idle MAF g/s baseline for an EJ engine* — the single number the deterministic layer
most needs (checklist A3) is not in these forums at score 3. What the keeps DO supply: leak-vs-latency
reasoning with numbers, smoke-test examples, injector-latency-vs-scaling separation, MAF-scaling
practice, Subaru timing/AVCS/TGV table architecture, wideband wiring, and a few EJ20X-swap facts.

## Per-document recommendations

| id | source | title | summary | rec | reason | value | markers O/C/N/R/X |
|---|---|---|---|---|---|---|---|
| 960 | legacygt | Tuning for Fuel Economy | Six-year 05 LGT/04 FXT MPG tuning log: AVCS/timing/WGDC/IAT-comp/tire experiments with pump-MPG outcomes, lambda-vs-AFR ROM facts, MAF-connector trim fix. | **keep** | Cruise/MPG focus, thin on idle; but Subaru-specific MAF-scaling-by-g/s-band, MAF-connector trim signature (STFT -25%), timing-too-high IAM drops, AVCS-overlap knock, AF3/lambda ROM facts are quotable. | medium | `●●●·●` |
| 961 | legacygt | Retune after injector swap? | 05 LGT jerking/RPM hunting, AF correction -20..+20, learning -7; fuel pooled in cylinder, leaking 650cc injector swapped to OEM 550cc; retune question unanswered. | **keep** | Symptom set (hunting idle, wild AF correction, no CEL) traced to leaking injector plus injector-scaling mismatch after swap; useful differential for gap 1 despite no outcome. | medium | `·●●··` |
| 962 | legacygt | Learning view and reliability tuning | Stock 08 OBXT owner asks whether to raise Learning View resolution and zero CL-to-OL delay; one reply says higher resolution runs better. | **drop** | Planning chat with no logs, numbers, or mechanism; nothing a diagnostic query would use. | low | `·····` |
| 965 | legacygt | Deleting CEL and etune options | 08 OBXT rebuild with mis-installed TGV actuators; asks about deleting CEL via tune vs fixing; break-in-before-tune debate, tuner logistics. | **drop** | Tooling/logistics chat about a TGV CEL; no data, procedure, or symptoms relevant to idle, leaks, or calibration gaps. | low | `·····` |
| 966 | legacygt | Fine Knock learn+DAM questions | 05 LGT VF52 saw DAM 0.875 once, fine knock learn -5 to -8 on throttle lift; replies ask for LTFTs and to email tuner. | **drop** | Unresolved knock question with no logs, diagnosis, or outcome; only hint is 'check LTFTs', too thin for retrieval. | low | `··●··` |
| 1024 | speeduino | COP Ignition on Datsun L24 | Carbureted 240Z owner plans COP/Speeduino ignition; advice to lock distributor advance, use Pertronix as trigger via diode, smart coils. | **drop** | Off-platform carb/ignition-conversion planning with no transferable diagnostic principle for Subaru idle/fueling gaps. | low | `·●●·●` |
| 1025 | speeduino | Rotax 912A (80HP) with BMW R1100 throttle bodies/injectors t | Aircraft Rotax carb-to-EFI Speeduino plan, 1800-5200 rpm; reply recommends WBO2, sequential injection, and controlling ignition too. | **drop** | Aircraft Speeduino planning, no execution or data; nothing transferable to the diagnostic gaps. | low | `·····` |
| 1028 | speeduino | How to test the dead time of fuel injectors? | Bench method for injector dead time without a scope: measure flow over long pulse, then 1000x10ms vs 1000x5ms pulses, derive offset from shortfall. | **keep** | Transferable measurement principle for injector latency (gap 1): how dead time is derived from short vs long pulse volume comparison. | medium | `·●●··` |
| 1032 | msextra | MS2 closed loop idle behaving strangely | Miata DIYPNP idle valve jumps to 43% duty after 26 s; reply: IAC direction reversed (duty falls, rpm rises), NB valve normally 20-30% duty. | **drop** | MegaSquirt IAC configuration issue; reversed-IAC principle not applicable to Subaru ECU idle diagnosis; unresolved. | low | `·●●··` |
| 1034 | msextra | HEI 8 pin timing issues | Jeep AMC 360 Microsquirt with HEI module shows +/-5-7 deg random timing swing at locked 10 BTDC; cable/module swaps no help; polarity suggested. | **drop** | Off-platform ignition trigger noise problem, unresolved; no relevance to Subaru diagnostic gaps. | low | `··●··` |
| 1035 | msextra | Boost tuning and blow off valves | Turbo Ninja MS2: autotune leaned VE to AFR ~17 at 5-7k rpm/120-180 kPa after BOV change; O2 lag blamed; cell-by-cell VE fixes, ran better. | **keep** | Transferable gap-5 example: VE correction from logged AFR vs target with sample-weighted conservative moves, and sensor-lag corrupting autotune during transients. | medium | `●●●·●` |
| 1083 | legacygt | 5EAT tune for a higher idle? | Asks if raising 5EAT idle from 700 to 1000 rpm reduces launch lag; reply: no load at idle so still in vacuum, no boost. | **drop** | Two-post hypothetical about idle speed and boost; no diagnostic content for idle quality or fueling gaps. | low | `·●●··` |
| 1086 | legacygt | (NZ) About to go get my 2010 legacy GT tuned at torque perfo | 2010 LGT with exhaust cutout overboosts to fuel cut on cold nights; 3-port BCS/wastegate advice; tuned to 16 psi, subjective feel only. | **drop** | Boost-cut/tuner-selection chat with no logs, AFR, or trims; confounded multi-part change and subjective outcome; not relevant to current gaps. | low | `●●●●●` |
| 1088 | legacygt | How to address lean condition in open loop | LGT lean 15.2-15.7 AFR at 0.70-0.85 g/rev 3.9-4k rpm; advice: log Final Fueling vs wideband, MAF vs injector model, per-injector PW comps, CL/OL tables. | **keep** | Direct gap-5/gap-1 material: how to attribute target-vs-actual AFR error to MAF scaling, injector scaling, comps or unmetered air on a Subaru ECU, with table names. | high | `·●●·●` |
| 1090 | speeduino | TS  perform automatic calibration and tuning using a narrowb | Asks if TunerStudio autotune works with narrowband; replies: narrowband gives only rich/stoich/lean, get a $25-50 DIY WBO2, tuning is finding best AFR by testing. | **drop** | Generic sensor-philosophy discussion; project already has a wideband, no procedure or numbers relevant to gaps. | low | `·●·●●` |
| 1098 | msextra | Idle stumble on cold start within first 3 seconds | 86 Trooper Microsquirt cold-start stumble first 3 s; ASE/cranking pulse changes did not help; suggestions on CL initial value axis and crank-to-run taper, unresolved. | **drop** | MegaSquirt-specific cold-start enrichment fiddling with no resolution or transferable principle for Subaru idle diagnosis. | low | `●·●··` |
| 1104 | romraider | 2002 wrx sti singapore model | JDM WRX ECU into EDM 02 STi: no CEL, no fuel prime, no OBD comms; reply: swap cam/crank pins, try FastECU to read locked ECU. | **drop** | Two-line ECU pinout swap question, no procedure or outcome; too thin to serve ROM-read or any diagnostic query. | low | `·····` |
| 1108 | romraider | Tuning help baja MT ez30/36R lost | Baja EZ36R on EZ30R MT ECU: IAM drops to zero at start, no knock, AVCS stuck 10%, idle locked 500 rpm; single post, no replies. | **drop** | Symptom list only, no diagnosis or replies; H6 ECU/harness mismatch not a usable analog for EJ20X-in-EJ255 calibration query. | low | `··●··` |
| 1109 | romraider | 04 forester not making expected power, what am i doing wrong | 04 FXT VF48 250hp not 300, ~90% WGDC, AFR 10.5-11 vs 11.5 target, suspects uppipe leak; replies: pre-turbo leak lean, post-turbo leak rich. | **keep** | Forester XT + VF48 near-match; gives the leak-location vs trim/AFR direction principle and MAF-rescale suspicion with numbers; outcome pending. | medium | `·●●·●` |
| 1110 | subaruforester | Datalog discussion thread | FXT log-sharing; thefoos: set injector scalar to tested flow, leave latency, dial MAF in RomRaider; a6n6d6y: injectors first then MAF; meth AFR ~12.5. | **keep** | Two experienced posters give reasoned order-of-operations for injector scaling vs latency vs MAF scaling — directly the gap-1 separation question; rest is boost chat. | medium | `●●●·●` |
| 1112 | legacygt | '99 GT-B tuning 300 - 320bhp? | NZ 99 Legacy GT-B owner asks how to reach 300 bhp; replies: pre-Rev-D ECUs barely tunable, buy a Rev D instead; resale and S401 chat. | **drop** | Platform/tuner-availability and market chat, no data or diagnostics; irrelevant to gaps. | low | `·····` |
| 1121 | speeduino | Please anaylize this tune MSQ file,from a commercial SPeedui | CB400 with commercial Speeduino MSQ hard to start, runs lean, VT stuck at 12V; replies: tables corrupted, tune the VE table yourself; no outcome. | **drop** | Off-platform corrupted-tune request with no diagnosis or numbers; nothing transferable. | low | `·····` |
| 1122 | speeduino | 0.3 version board not support the idle control motor? | Speeduino v0.3 board lacks stepper IAC; advice to tune idle open-loop on fixed throttle stop, warm engine, WUE at 100% before enabling IAC. | **drop** | Speeduino hardware talk; only generic idle order-of-operations, no logs, numbers, or Subaru relevance to the current gaps. | low | `···●·` |
| 1123 | speeduino | How does Gemini do with working out idle tune | OP pastes a Gemini-generated Speeduino idle-tuning checklist; forum veteran critiques it; decel-stall question unanswered beyond 'watch VE cells live'. | **drop** | AI-generated generic checklist plus opinion; no data, no resolution, no transferable Subaru diagnostic content. | low | `·····` |
| 1125 | speeduino | Ignition only conversion of 1970's motorcycle engine? | Planning a Speeduino ignition-only conversion on a 650cc motorcycle: cam trigger wheel sizing, optical vs Hall sensor, EMI screening. | **drop** | Off-platform hardware planning with no engine-behavior data; nothing transferable to Subaru idle/fuel/timing gaps. | low | `··●·●` |
| 1126 | msextra | Fuel Injector Sizing Calculators giving low HP figures? | OP questions why injector HP calculators (BSFC 0.6, 2.8 bar) undershoot brochure HP; replies say calculators undersize and BSFC 0.6 is too high. | **drop** | Generic injector sizing chat, unresolved, no logs; not a diagnostic gap topic. | low | `··●··` |
| 1131 | msextra | oscillting TPS signal at idle | Microsquirt parallel install: TPS oscillates 0-1.5% at idle, causing AE at idle; rewiring/sensor swap only minor help; MAPdot/TPSdot threshold advice. | **drop** | MegaSquirt-specific TPS noise and AE threshold tuning; unresolved; no transferable principle for Subaru idle gaps. | low | `●●●··` |
| 1134 | romraider | Quick question regarding cold idle | Why cold high idle drops after a throttle blip on 2010 STI; answer is an AI-generated 'post-start idle adder' explanation, tables not found in ROM defs. | **drop** | Unverified AI-generated table structure that another poster could not locate; cold-idle blip behavior is not a current gap. | low | `·●···` |
| 1135 | romraider | Why is my Final Fueling Base running 17AFR's in closed loop | Single unanswered post: Final Fueling Base randomly targets 16-20 AFR in closed loop, STFT spikes to 25%, actual AFR ~14.7. | **drop** | One-post question with no replies, no diagnosis; nearly empty. | low | `··●··` |
| 1137 | romraider | Want to install a 3 port on a 2016 VA JDM STI | Two-post thread: 3-port boost solenoid install on VA STI; reply says drop wastegate min/max duty by 10 and log. | **drop** | Boost-control planning stub with no data or outcome; not a current gap. | low | `·····` |
| 5772 | nasioc | 05 Forester XT build help | 05 FXT injector/TGV planning: stock yellow side-feed 535cc = STI, top-feed blues 565cc, 06 WRX TGVs fit if deleted, harness differs, sequential-to-parallel. | **keep** | Test-car-matching facts on 05 FXT injectors, TGV delete hardware and harness; useful for injector-scaling and TGV queries though no logs. | medium | `··●··` |
| 5773 | nasioc | Let's talk AVCS tuning.....anyone...? | 200-post NASIOC debate on intake AVCS tuning: theory, tuner disagreements, several logged A/B tests (AFR, MAF V, boost, DeltaDash) at varied advance. | **keep** | Off-idle but teaches AVCS->VE->AFR/MAF/boost causality with numbers, cam-centerline mismatch caveat (JDM vs USDM cams on same map) and dyn-compression/knock warning; useful for EJ20X-cams-on-EJ255-map queries. | medium | `●●●·●` |
| 5774 | nasioc | Logging AFR with AP v3 and AEM UEGO - How to wire it up. | Wiring AEM UEGO 0-5V into rear O2/TGV input for AP logging; X-series brown ground; P0138 from 1-5V vs 0-1V; zero AF3 tables to stop trim skew. | **keep** | Direct Subaru wideband install/logging procedure incl. AEM 30-0300 grounding, P0138 mechanism and rear-O2 trim influence (up to 7.35%). | medium | `●●●●●` |
| 5779 | legacygt | Where is the smoke coming from? (see video) Is the wastegate | Smoke test on Legacy GT shows leak at wastegate actuator; confirmed by smoking actuator directly; explains no boost; OP moves to VF52 swap. | **keep** | Subaru smoke-test example: leak source found and confirmed by pressurizing actuator; teaches where leaks appear, though no trim/AFR numbers. | medium | `●●·●●` |
| 5788 | msextra | Understanding VSS CL Idle | MS3 Hemi cold-start stalling: CL idle drops out on rpm jitter, over/under thresholds, WUE vs cold-drive AFR 16 idle/13 driving; unresolved. | **drop** | MegaSquirt-specific idle PID/state config, long and unresolved; little transferable to Subaru gaps. | low | `·●●·●` |
| 5792 | romraider | 06 wrx bloush 30g dominator and injector dynamics 1050cc inj | 06 WRX with ID1050 injectors, TGV delete, CAI: AF learning +25% at idle, misfires, stalls; advice: wideband logs, latency/scaling, MAF scaling, smoke test. | **keep** | Subaru idle case with the exact differential (leak vs latency vs MAF scaling) and +25% idle learning; unresolved but query-relevant. | medium | `·●●·●` |
| 5798 | romraider | '04 FXT Timing Map Advice Wanted | 04 FXT EJ255 self-tune: base timing + KCA summed as target, IAT comp adds ~3 deg, IAM pulls from KCA, TGV open/closed tables split; no outcome. | **keep** | Subaru FXT timing architecture (base+KCA, IAM retreat, TGV-status tables) directly informs timing/knock and TGV-delete table handling. | medium | `·●●·●` |
| 5799 | romraider | 2007 EDM Legacy 3.0RB running issues | EZ30D Legacy: rich smoke, failed emissions, cold light-throttle jerk, hunting fuel trims; replies suggest AFR sensor, smoke test, plugs/coils. | **drop** | EZ30 not EJ; generic troubleshooting list, no data, unresolved. | low | `·····` |
| 5802 | legacygt | 06 self tuning question. | Misplaced newbie boost question; replies explain narrowband inaccuracy near 11:1, wideband options, stock ECU target/initial/max WGDC logic, MBC futility, boost fuel cut. | **drop** | Boost-control theory and wideband advice only; no idle, trims, leaks, or MAF content; nothing serves current diagnostic gaps. | low | `·●●·●` |
| 5804 | legacygt | Knock-Knock-Knock; its Christmas | EJ257 cruise knock -11 with fluctuating AF correction; MAF cleaned/swapped, injectors changed, inlet-boot leak suggested; compression 130 vs 150 psi cyl 4, unresolved. | **keep** | Useful checklist for knock plus fluctuating AF correction: MAF scaling/cleaning, torn inlet boot causing knock and AF learning, then compression/leakdown numbers. | medium | `●●●··` |
| 5808 | legacygt | HELP - Engine Knocking :( | E85 build suddenly counts heavy knock, DAM drops to 1.125/0.5; fresh fuel and ECU reset don't help; ends with knock sensor circuit CEL. | **drop** | Unresolved knock-sensor/E85 saga with no diagnosis or fix; no idle, trim, or leak content relevant to current gaps. | low | `··●·●` |
| 5812 | msextra | Map Sensor as Cam Input at 6-cyl ITB | MS3 user asks about using MAP pulse as cam sync on 6-cyl ITB TVR; told it only works for singles/odd twins; plans custom board. | **drop** | MegaSquirt trigger-hardware question with no transferable diagnostic principle for a Subaru ECU project. | low | `·●·●·` |
| 5814 | msextra | Idle vs cruise AFR during warmup issues | MS Hemi cold idle lean 15.5-16 AFR while cruise fine; VE-idle blending, CLT-based AFR target workaround, injector timing experiment stumbles, deadtime accuracy warning. | **drop** | MegaSquirt-specific warmup table workarounds; only transferable nugget is deadtime error skewing multiplicative enrichments, too thin to justify indexing. | low | `●●●·●` |
| 5820 | romraider | EZ30 Tuning WOT | Single unanswered post: JDM 3.0R throttle opening restricted first second in 1st gear; suspects torque tables; evidence only in images. | **drop** | Unanswered EZ30 DBW torque-limit question with image-only evidence; irrelevant to EJ idle/fueling gaps. | low | `·····` |
| 5821 | romraider | EZ36 Ignition timing | Link G4 EZ36 owner running EZ30 timing maps asks for stock EZ36 tables to stay conservative; pointed to stock ROM repository. | **drop** | Request for reference tables with no data, symptoms, or method; nothing retrievable for EJ timing/knock or idle gaps. | low | `·····` |
| 5823 | nasioc | new hybrid mbc/ebc method of boost control | Parallel ball/spring MBC + 3-port interrupt solenoid boost control: routing, WGDC/target/turbo-dynamics tables, troubleshooting wrong ports, many users confirm spike-free boost. | **keep** | Boost control is not a current gap (car has not driven); but Subaru-specific, corroborated, with tables and 3-port troubleshooting steps useful for later boost-spike/oscillation queries. | low | `●●●●●` |
| 5826 | nasioc | A Complete Tuning Guide | Tuning-guide feedback thread: wastegate/BCS mechanics, MAF-scaling scatter tightened after fixing intake leaks, TD boost-tuning logs, Tea Cups' ECU fueling/knock-logic corrections. | **keep** | Leak-vs-latency signature in MAF-scaling scatter and Tea Cups' A/F correction/learning, CL/OL, FBKC/FLKC explanations serve gaps 1 and 5; boost-control bulk is off-gap; guide body removed. | medium | `●●●·●` |
| 5829 | legacygt | LGT AVCS Tuning Discussion | LGT intake-AVCS mapping discussion: street A/B tests, header/turbo effects, idle AFR/vacuum shifts with advance, cruise-spike removal cutting knock sums, overlap-degree figures. | **keep** | Serves VE/timing/knock queries: AVCS advance changes VE and required timing, low-load advance drives knock/stumble, idle AFR/vacuum shift numbers; not core idle-leak gap. | medium | `●●●·●` |
| 5830 | legacygt | ECM swap | Rough idle blamed on ECM/harness, actually cam sensor; second poster clones ROM via Tactrix/ECUFlash, P1571 immobilizer mismatch, fixed by moving 8-pin EEPROM. | **drop** | ECU-swap immobilizer procedure is resolved and corroborated but off current gaps; rough-idle cam-sensor fix has no log data. | low | `●●·●●` |
| 5834 | legacygt | Help with V3 showing feedback knock | FBKC -9 at 2300-2500 rpm in 5th; told fine if DAM 1 and FLKC under 2.5; knock sensor orientation/torque, crank/cam windowing, false knock explained. | **keep** | Practical knock-handling rules of thumb (DAM/FLKC thresholds), false-knock sources, and ECU knock-window mechanism; directly serves knock-handling gap. | medium | `·●●●·` |
| 5835 | legacygt | New to tuning, where to begin... | VF52 swap newbie with Openport asks for basemap; told get gauges, read RomRaider guides, tune CL then OL, or hire tuner; hires Cryotune. | **drop** | Generic beginner advice with no data or procedure; no value for idle, leak, MAF, or flashing gaps. | low | `···●●` |
| 5840 | msextra | Barriers to set timing | MS user can't see timing marks with crank cover on; tooth-log-during-cranking method suggested to find TDC; OP just removed cover. | **drop** | MegaSquirt crank-trigger setup on motorcycle engines; no transferable principle for Subaru ECU diagnosis. | low | `●●·●●` |
| 5841 | msextra | Having trouble making sense of VE table vs. datalogged data | MS3x 2JZ VE table jagged after autotune; VE Analyzer/smoothing advice; rich idle surges worse when leaned, suspects deadtime at 1.4 ms PW, 0.658 ms deadtime. | **drop** | MegaSquirt autotune workflow; injector-latency-at-idle suspicion is unverified and platform-specific, weak for Subaru injector-latency query. | low | `●●●·●` |
| 5842 | msextra | 660cc to 1000cc injectors and went way lean | MS injector upsize to 1000cc went 23 AFR no-start; needed +40% VE; replies say enter deadtimes and use E85 stoich 9.1 in req-fuel calc. | **drop** | MegaSquirt required-fuel/E85 stoich mistake; injector scaling plus deadtime principle is generic and unverified here. | low | `●●●·●` |
| 5848 | romraider | Legacy gt crazy lean under boost. | Resurrected 07 LGT hits 19.x AFR under boost at low injector duty; suspects fuel delivery; pulls pump, strainer clogged, replacement ordered. | **drop** | Two-post fuel-delivery lean-under-boost with no confirmed outcome; not idle, leak, MAF, or flashing content. | low | `·●●··` |
| 5850 | romraider | Knock and slow AVCS responses? | Single post: 2017 STI FLKC -1.5 to -4 above 6000 rpm after 10W-60 oil change; asks if thick oil slows AVCS; logs only in images. | **drop** | Unanswered high-rpm knock/AVCS hypothesis with image-only logs; no idle or timing-handling guidance. | low | `··●··` |
| 5852 | nasioc | Open Source Speed Density Patches | Merp SD patch announcement; MAF maxing at 4.7 V; MAF vs SD tradeoffs: MAF removes VE from equation, SD sensitive to exhaust mods, leaks, elevation. | **keep** | Clear MAF-vs-VE principle: with MAF the ECU measures airflow directly, so displacement/VE mismatch matters less; helps reason about EJ20X-on-EJ255 calibration. | medium | `·●●·●` |
| 5853 | nasioc | 2004 STi ECU speed density | How to apply Merpmod SD to 04 STI: copy maps from 500 to 710 ROM version; brief SD tuning order (OL fuel, injectors, boost, VE). | **drop** | Thin SD-patch how-to with no data; tuning order is generic; not serving idle or MAF gaps. | low | `●··●·` |
| 5854 | nasioc | If I up my boost what should all get changed in my tune | 05 FXT MBC boost-up question; replies: use EBCS, ECU trims fuel to targets, pull ~5 deg timing and add 5-10% fuel then log FBKC/FLKC/AFR. | **drop** | Generic boost-up planning with rules of thumb, no execution or data; off current idle/leak/MAF gaps. | low | `·●···` |
| 5855 | nasioc | Injector scaling | PE850/PE800 injector scaling and latency debate: rated-vs-actual flow at 43.5 psi, scalar vs MAF vs latency roles, lean idle/maxed trims fixed by raising latency. | **keep** | Directly separates injector latency (idle AFR/trims maxed) from scalar (WOT AFR) and MAF (load/airflow); nj1266 gives before/after idle trims - core gap-1 material. | high | `●●●●●` |
| 5860 | legacygt | false knock? | FBKC rose from -1.4 to -2/-5 and DAM 0.75 after dropping socket and worm clamp under intake manifold; socket retrieved, clamp missing, no follow-up. | **drop** | Plausible false-knock-from-foreign-object story but unresolved, no outcome; marginal for knock gap. | low | `·●●··` |
| 5862 | legacygt | Lean Idle, near perfect AFR under throttle while in open loo | DIY-swapped built EJ, TGV deletes, aftermarket injectors: MAF adapter-plate leak sealed fixed lean under throttle, idle still 17-19 AFR; unanswered. | **keep** | Symptom profile mirrors project car (swap, TGV delete, big injectors, lean idle); documents that a MAF-side leak fixed load AFR but not idle. | medium | `●●●··` |
| 5863 | legacygt | Extremely high MAF reading during pull | BtSsm logged 500+ g/s MAF spike; MAF voltage unchanged at 4.16 V proves read error; too many requested parameters overloads ECU polling. | **keep** | Transferable logging-integrity principle: cross-check MAF g/s against MAF volts, discard read errors, limit SSM parameter count; useful for logging gap. | medium | `·●●··` |
| 5866 | msextra | Tuning IAC with ITBs running Alpha-N | MS2 Porsche 911 ITBs on Alpha-N: IAC air not reflected in TPS load so warmup fuel can't raise idle; secondary MAP fuel table workaround suggested. | **drop** | MegaSquirt Alpha-N/ITB idle control specifics; no transferable principle for MAF-based Subaru idle diagnosis. | low | `·●●·●` |
| 5867 | msextra | Idle Surge | MS idle surge after driving: WUE last bin 108% still adding fuel at 190 F; advised set 100, rescale VE, flatten idle cells; no follow-up. | **drop** | MegaSquirt warmup-table config error; principle (enrichment still active when warm causes surge) is weakly transferable, no outcome. | low | `·●●·●` |
| 5868 | msextra | idle goes up after engine reaches operating temp | MS II Durango idle climbs to 3k rpm when warm; erratic TPS -1.8 to 11% blocks closed-loop idle via RPM DOT limit; replace TPS advised. | **drop** | MegaSquirt-specific closed-loop idle entry logic; no outcome; not useful for Subaru idle gaps. | low | `·●●··` |
| 5870 | msextra | Subaru EZ30 starts, idles, won't rev | Single unanswered post: MS3 EZ30 on ITBs idles but bogs or cuts on rev; asks about VR sync loss. | **drop** | Nearly empty unanswered MegaSquirt post; no data, no diagnosis. | low | `·····` |
| 5875 | romraider | Help me understand why the boost map looks this way | R205 EJ207 stock boost target map has a dip; reply says SI-Drive/DBW may request torque via throttle not boost, log throttle and TGVs. | **drop** | Boost-map curiosity on DBW STI, image-only evidence, no logs; irrelevant to idle/leak/MAF gaps. | low | `·●···` |
| 5879 | nasioc | Ecu pulling 6 degrees of timing | 05 STI pulls ~6 deg at 2600/3500/4500 rpm even with knock sensor disabled; grounds, coils, plugs done; tuner suggests new ECU; unanswered. | **drop** | Unresolved timing-pull mystery with only null results; no mechanism identified; low value for knock-handling gap. | low | `··●··` |
| 5880 | nasioc | Maf Scaling Values for 2015 WRX | Request for MAF scaling values for ETS intake on 2015 WRX with -12 AF correction; no replies beyond an image link. | **drop** | Unanswered request for scaling numbers; no procedure or data; nothing retrievable. | low | `·····` |
| 5885 | nasioc | 04 STI Ecuflash Idle Tuning Issue | 04 STI with large MAF tube dies after reflash until learned; very lean on decel, idle 500 vs 1000 target, MAF rescale didn't help; unanswered. | **drop** | Relevant symptoms (lean idle, MAF housing change) but single unanswered post with no diagnosis or numbers beyond rpm. | low | `··●··` |
| 5915 | nasioc | noise while car is under load and building boost | 2017 STI whine above ~5 psi after service; DIY smoke test found PCV leak, hot boost-leak test another; real cause exhaust crossover gasket, fixed. | **keep** | Resolved arc showing smoke test and hot boost-leak test procedure finding leaks, plus exhaust-leak-as-noise lesson; supports leak-testing gap. | medium | `●●●●·` |
| 5968 | legacygt | Lost my tune | 05 LGT shakes/misfires after plug+coil job and ECU reset; smoke test found nothing, bad grounds fixed, ends suspecting 5V reference wire. | **drop** | Unresolved electrical/misfire hunt with no trims, MAF or AFR data; smoke test negative and DIY smoke rig aside, nothing a gap query would retrieve usefully. | low | `·····` |
| 5970 | msextra | SD datalogging stopped recording mid track day - troubleshoo | MS3 SD-card logging stops mid-lap; suggested card corruption, reformat or swap card; no test done. | **drop** | MegaSquirt SD-card housekeeping, no outcome, no transferable diagnostic principle for any gap. | low | `·····` |
| 5971 | msextra | ms3x with staged mainboard driven injectors | MS3X staged injection on 363 SBF: secondaries won't fire in test window but do in sequential; running on 1300cc elbow injectors alone floods engine, unresolved. | **drop** | Off-platform staged-injection config issue, single poster, no diagnosis; nothing transferable to Subaru idle/injector gaps. | low | `●····` |
| 5972 | msextra | boost control, launch boost duty% | MS3X open-loop boost: setting launch boost duty 0->30 gave 0% WG duty most of a quarter-mile; reverting restored 40%; no explanation given. | **drop** | MegaSquirt-specific launch-control quirk, unexplained and unresolved; boost control is not a current gap and no principle transfers. | low | `●·●··` |
| 5983 | legacygt | 2007 LGT Engine Swap into 2005 LGT | 07 D25 longblock into 05 LGT using 05 intake/harness/electronics; canbus v1/v2 incompatible; swap done, 2000 km fine; brief EJ20X/Y warning (high CR, SAVCS gutless). | **drop** | Mechanical swap planning; the only gap-adjacent content is one-line opinion on EJ20X/Y high CR and AVCS with no symptoms, logs, or calibration detail. | low | `●··●●` |
| 5984 | legacygt | Swap to sportier AT transmissions? | 08 LGT 5EAT cold-shift delay; discussion of TCU limits, transgo kits, ATF changes, tire fitment; no change executed. | **drop** | Automatic transmission and wheel-fitment chat; zero engine tuning or idle diagnostic content for any gap. | low | `·····` |
| 5985 | legacygt | Rough Idle - Engine Dies and Won't Idle after 15 minutes of  | 07 Legacy 2.5i hunts and stalls after ~15 min hot idle above IAT 140-150F; MAP dips with each miss; new MAF and front O2 both no effect; unresolved. | **keep** | Live-data reasoning on hunting idle (O2 lean -> PW up -> rich cycle, MAP-vs-leak logic, IAT threshold, two negative part swaps) serves idle-diagnosis queries despite no fix. | medium | `●●●·●` |
| 5990 | legacygt | 2006 Legacy GT Not building Requested Boost During Tuning | 06 LGT VF52 makes 8-11 psi vs 16 target with WGDC 0% in logs after swapping EBCS/harness/ECU; WG line blocked hits 20-21 psi; EWG installed, root cause never found. | **keep** | Subaru log-based boost diagnosis (WGDC 0 = spring pressure, block-WG-line test, g/rev baselines) plus wideband-into-TGV-input logging tip; not a current gap so medium. | medium | `●●●·●` |
| 5991 | msextra | Wondering if my AFR target tables are off. | Single post: MS2 Mercedes 190E hesitation at part throttle/high load low rpm, asks if AFR target table dip causes it; no replies. | **drop** | One unanswered question, no data, off-platform; nothing to retrieve. | low | `·····` |
| 5996 | msextra | Can i save this tune after injector change | MS3: swapping to same-rated 1200cc EV14s went lean, PW 2.0->2.5 ms; consensus: fix injector constants (deadtime, voltage offset, size) first, then retune VE; labeled flow often wrong. | **keep** | Transferable principle for gap 1/5: injector latency and true flow must be characterized before VE correction; PW shift with units and mislabeled-flow example. | medium | `·●●·●` |
| 6005 | legacygt | Overheating LGT thread.. | 05 LGT temp gauge climbing with no cabin heat at 3C; overflow bone dry, topped coolant, gauge still to 3/4; low coolant/air pocket suspected. | **drop** | Cooling-system air-pocket thread; not related to any tuning or idle diagnostic gap. | low | `●●●··` |
| 6006 | legacygt | Upgrade parts AFTER e-tune | 05 LGT owner asks whether to install bigger injectors/pump before finishing e-tune; advice on retune need, VF52 wastegate, injector sizes; coil pack fixed misfire. | **drop** | Parts-upgrade planning chat; injector-size and duty-cycle anecdotes are not idle/MAF/leak diagnostics and add nothing to current gaps. | low | `●·●●●` |
| 6010 | legacygt | Crank - No Start after dash swap | JDM Legacy no-start after dash/cluster swap; immobilizer VIN mismatch suspected; original cluster + long battery disconnect restored start; EEPROM read attempt failed. | **drop** | Immobilizer/cluster electrical issue, no engine-tuning or idle diagnostic content; irrelevant to every listed gap. | low | `●●·●·` |
| 6013 | msextra | New to MS3/TS - Idle quality issues | MS3PNP Miata idle hunting/stall on hot restart; advisors point to fixed 10 deg timing, idle-valve min duty above table, VE variance; no follow-up. | **drop** | MegaSquirt-specific idle table config; no outcome, no transferable principle for factory Subaru ECU idle diagnosis. | low | `·●●·●` |
| 6015 | msextra | Rich AFR when releasing 2-step | MS3Pro E85 drag car dips to 10.1 AFR for 0.5 s off 2-step; TPS accel-enrichment suspected; OP later doubts it, unresolved. | **drop** | MegaSquirt launch-control transient fueling, unresolved; nothing transferable to idle/leak/MAF gaps. | low | `·●●··` |
| 6016 | msextra | MS3 Internal Mxp4250ap map sensor overreading | MS3 reads 150 kPa at atmosphere despite correct 1.79 V sensor output and 20.4 V battery reading; ground-offset suggested; OP recalibrates as workaround. | **drop** | MegaSquirt hardware/ground fault, unresolved; no bearing on Subaru ECU diagnostic gaps. | low | `·●●··` |
| 6177 | msextra | Datalog RPM does not match Dyno RPM - MS3X/Tunerstudio | MS3X USB datalog peaks 6650 rpm vs dyno 7150 rpm; SD logging 10x faster suggested; timing-light check advised; no resolution. | **drop** | Engine-dyno RPM discrepancy on MegaSquirt; not relevant to Subaru logging or idle diagnosis gaps. | low | `·●●··` |
| 6196 | msextra | MS3X - EGO PID settings causing rapid AFR oscillation during | Single unanswered post: MS3X ITB L28 AFR oscillates 13.7-15.3 with EGO 92-105% at steady 3100 rpm; asks for PID values. | **drop** | Unanswered MegaSquirt closed-loop PID question; no answer, no transferable content for current gaps. | low | `··●··` |
| 6212 | romraider | MAF Shaping and Scaling Spreadsheet | RomRaider tool thread: smooth a log-scaled Subaru MAF curve via 2nd derivative; multiple users report smoother drivability, tighter trims; warns idle cells sensitive. | **keep** | Subaru MAF-scaling method with transferable rules (keep curve smooth, distrust >7% deltas, idle cells cut 75-85% nearly stalled motor); serves MAF-scaling gap. | medium | `●●●●●` |
| 6224 | romraider | Regrab Maf Alterations from RR jpg file? | Lost RomRaider MAF log; advice: low MAF voltages (1.13-2.0 V) wander +/-5% with air density, don't chase; -4% scaling flipped to +6% at idle. | **keep** | Short but useful principle for idle MAF-scaling queries: sub-2 V trims drift +/-5% day to day; separates atmospheric wander from real scaling error. | medium | `●●●··` |
| 6233 | romraider | NA 2014 Forester 2.5i CVT questions + logs | Single post: FB25 NA Forester WOT commanded AFR stuck at 13.197 regardless of fuel map edits; wideband agrees; 12.7 at 1.5x load; no replies. | **drop** | Unanswered FB-series open-loop fueling question, evidence in attachments; not EJ, no resolution, no relevance to idle/leak gaps. | low | `··●··` |
| 6236 | romraider | Does the RomRaider Logger Dyno measure WHP | 07 FXT stage-1 logs 162 kW on RR logger dyno; answered it estimates WHP, environment-sensitive, use only for relative before/after comparison. | **drop** | Power-estimate tool Q&A; no diagnostic content for idle, leaks, MAF, or flashing gaps. | low | `··●●●` |
| 6247 | romraider | Question: Understanding Airboys Spreadsheet | 07 WRX at 7200 ft logs 7 psi vs gauge 11-12 psi; explained baro ~11.2 psi skews Relative Sea Level param, use Manifold Relative Pressure Corrected. | **drop** | Altitude/boost-parameter selection tip only; test car is not at altitude and boost logging is not a current gap; no outcome reported. | low | `·●●··` |

Markers legend: O outcome reported · C causal chain · N numbers with units+conditions · R thread resolved · X corroboration.

## Recommended next step (Syed's call, not taken tonight)

1. Sign off (or edit) the **28 keeps** above. Nothing moves until you do.
2. When the C2 judge run finishes, run the same rubric over the *new* score-3 docs and append them here.
3. If approved: `ensure_community_index(state, min_score=4)` will index the ≥4 docs; the reviewed keeps
   need a way in that does NOT rewrite `document.tier` or `judge_score` — e.g. a `human_label`
   row (`label_set='community-3s-review', rater='claude'`, `score=4`) that the community-index
   predicate can OR into. That predicate change is a one-liner and is **not** written tonight.

## Rubric (verbatim)

```
# Score-3 community doc review — FIXED RUBRIC (2026-08-16)

You are reviewing forum threads that an LLM judge scored 3/5 ("some substance, not enough to
promote") for MLECU — an AI-assisted ECU tuning system whose test car is a 2005 Subaru Forester
XT with a JDM EJ20X 2.0 L swap running the stock EJ255 2.5 L calibration, TGVs deleted, exhaust
AVCS deleted, VF48 turbo, catless. The car idles poorly and has never been driven.

The question is NOT "is this good writing" and NOT "is this correct" (a text reviewer cannot know
whether a fix actually worked). The question is: **would this thread be USEFUL if RETRIEVED for
the diagnostic queries the project currently lacks answers to?** Those gaps, in priority order:

1. Idle diagnosis: vacuum leak vs injector latency vs MAF scaling vs injector flow — what
   separates them in logs (trims vs airflow, trims vs battery voltage, smoke test results).
2. Smoke/leak testing procedure and what leaks look like in trims/AFR.
3. Healthy-idle MAF g/s baselines for EJ-series engines (esp. TGV-deleted), rpm dependence.
4. EJ20X-in-EJ255-calibration (or similar displacement/CR mismatch) symptoms and fixes.
5. VE / load-model correction from logged AFR vs target; timing for higher CR on 93 octane;
   knock handling. (Timing is a RETREAT mechanism in MLECU — removing timing autonomously,
   adding requires human review.)
6. RomRaider/ECUFlash/Openport logging + flashing procedure, SSM2, ROM read problems.
7. Wideband install/logging (AEM 30-0300), MegaSquirt/Speeduino content is LOW value unless it
   teaches a transferable diagnostic principle.

For EACH document, output ONE JSON object on ONE line (JSONL), no prose around it, with exactly:

{"id": <int>, "source": "<source>", "title": "<title, trimmed to 80 chars>",
 "summary": "<one line, <=25 words: what the thread actually contains>",
 "recommendation": "keep" | "drop",
 "reason": "<one line, <=30 words, judged on RETRIEVAL USEFULNESS for the gaps above>",
 "markers": {"outcome_reported": true|false, "causal_chain": true|false,
             "numbers_with_units_conditions": true|false, "thread_resolved": true|false,
             "corroboration": true|false},
 "topics": [<zero or more of: "vacuum_leak","smoke_test","idle","maf_scaling","maf_baseline",
            "injector_latency","injector_scaling","ve_tune","timing_knock","boost_control",
            "avcs","tgv","ej20x_swap","displacement_mismatch","wideband_afr","logging_method",
            "romraider_ecuflash_tooling","rom_read_flash","megasquirt_speeduino","generic_other">],
 "subaru_specific": true|false,
 "retrieval_value_for_current_gap": "high" | "medium" | "low"}

Rules:
- "keep" means: worth putting into the SEPARATE community retrieval index (tagged as a forum
  post) because a realistic diagnostic query would be well served by it. A post that says "same
  thing happened to me — smoke test found a torn intake boot, trims went from +12 to +2" is a
  KEEP even if it is two lines, because it is exactly what a vacuum-leak query needs.
- "drop" means: generic chat, unresolved speculation with no numbers, off-platform tooling talk
  with no transferable principle, parts-for-sale, or duplicated content.
- markers are about VERIFIABILITY SIGNALS, not correctness: did anyone report the outcome, is
  there a cause→effect chain, are there numbers WITH units and conditions, did the thread reach a
  resolution, does more than one poster corroborate.
- Read the whole document (Read tool; long files: read in offsets). The judge's rationale is at
  the top of each file — you may disagree with it.
- Do NOT invent content. If a doc is nearly empty, say so and drop it.
- Output ONLY the JSONL lines, one per doc, in id order. Nothing else.

```
