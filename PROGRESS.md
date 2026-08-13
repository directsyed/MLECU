# MLECU — Progress Log

Reverse-chronological (newest first). This is a portfolio/resume artifact — entries are written to be
legible to a technical reader who wasn't in the room. Performance numbers are also recorded in the
table at the bottom (date / metric / value / conditions) for a comparable history over time.

**Full forward plan: [docs/ROADMAP.md](docs/ROADMAP.md)** — every remaining arc from the first
ECU read to "the car is tuned," incl. the RAG-vs-fine-tune eval protocol and the definition of done.

---

## 2026-08-13 — WIDEBAND LIVE AND CROSS-VALIDATED: AEM agrees with the factory sensor to 0.02 AFR

Re-logged after fixing the AEM plugin. **`wideband_afr` now carries real data**, and it is
trustworthy: across all 1,351 samples the AEM reads mean 14.62 AFR while the factory A/F sensor
reads 14.64 — a **mean difference of -0.02 AFR (std 0.08)**. Two independent instruments agreeing
this tightly means both can be trusted, and it retroactively validates the factory-sensor trims
from the 2026-08-12 warm-idle log (the "held loosely" caveat there is now largely discharged for
the fuel channel).

**What this log is:** a **cold, elevated-idle warm-up shakedown taken right after the ECU hard
reset** — coolant rising 100->135 F, idle speed ~1137-1550 rpm (mean 1337), MAF ~7.3 g/s (about 2x
the warm-idle log's 3.5), and `af_learning` flat at 0.00 because the reset wiped it. It is closed
loop (correction actively moving, holding ~stoich), mechanically healthy (zero knock retard,
timing 15.5-19 deg, 0.00% transient samples), but it is **NOT a capture-protocol warm-idle hold**
and must not be fed to the estimator as one. Coincidentally it approximates the protocol's *fast
idle* condition (~2x airflow), just cold and pre-learning.

**One reading worth carrying forward, held loosely:** at this cold high-idle point the ECU needs
**+7.66% fuel correction** to hold stoich with learning wiped, versus the warm-idle log's +0.31%
total trim. Not comparable operating points (cold vs warm, wiped vs settled learning), so this is
not evidence of a lean condition yet — it is a number to re-check once a proper warm hold is taken
with learning settled.

## 2026-08-12 — FIRST REAL TELEMETRY: the log->role path works on a real car; wideband channel is dead in the file

1,878 samples over 129.6 s from the test vehicle — the first data this project has ever had that
did not come from its own simulator. Run through `logparse.parse_romraider_csv` unchanged.

**The parser handled real RomRaider v370 headers on the first attempt**: all 13 canonical roles
mapped, including the collision fixes made hours earlier the same night. `A/F Sensor #1 (AFR)`
correctly declined to alias onto `wideband_afr`, keeping the trusted instrument unambiguous by
design rather than by luck.

**Sample rate 14.49 Hz with 21 parameters — 3x the modelled prediction.** The bandwidth model in
`IDLE-LOG-PROFILE.md` assumed a request/response round trip per sample against SSM2's declared
4800 baud and predicted ~4.7 Hz. SSM2 supports a continuous-read mode where the address list is
sent once and the ECU streams, removing that overhead. Model replaced with the measurement.

**Steady-state quality is excellent: 0.00% of samples exceed either `GridSpec` transient
tolerance** (|d rpm| mean 8.7 max 79 against a 100 limit; |d tps| max 0.39 against 2.0). A 60 s
hold yields ~870 usable samples against `min_samples = 20`.

**Closed loop confirmed by the documented workaround** — `A/F Correction #1` std 2.65 %, actively
wandering rather than frozen. The substitute for the inaccessible `CL/OL Fueling` extended
parameter works.

**The blocker: `wideband_afr` is a column of zeros.** Exactly one distinct raw value, `0.00`,
across all 1,878 rows. The engine was running and fuelling normally — the factory A/F sensor read
12.40-15.16, mean 14.53 — so this is the AEM plugin, not the engine. **The capture protocol cannot
run without it**; it is a REQUIRED channel and the project's ground-truth instrument.

**First observation about the car, held loosely:** total fuel trim averages **+0.31 %**
(correction + learning), i.e. closed loop has idle fuelling essentially nailed, while idle speed
wanders **640-770 rpm** (std 17.6). That points away from idle *fuelling* as the cause of the bad
idle. Held loosely on purpose: without the wideband there is nothing to check the factory sensor
against, and if it is lying the trims are meaningless. That is precisely why the wideband is the
ground-truth instrument.

## 2026-08-11 — WIDEBAND LINK SOLVED, then a ground loop killed ECU comms: both faults were physical, neither was software

Two faults resolved on the car in one session, and **neither lived where its symptoms pointed.**

**Fault 1 — the wideband serial link (open since 2026-08-08).** The prior session's leading
suspect was a non-compliant USB-serial adapter. It was wrong, and so were the two hypotheses that
replaced it. Elimination ran: cheap chipset (killed — `VID_0403+PID_6001`, genuine FTDI FT232R
with a properly programmed serial) → TTL-vs-RS-232 level class (killed — **−5.74 V measured on
DB9 pin 3**, which only a real transceiver produces; a bare FT232R pin idles at +3.3/+5 V) → the
PC side including the read method itself (killed — a pin 2↔3 **loopback echoed**) → adapter damage
(killed — a reboot restored it) → **the hand-crimped DB9 shell, confirmed by bypassing it.**
Wiring the gauge straight to adapter pins 2/5 returned **301 bytes, ~50 clean `99.9\r\n` samples
in 5 s** — the gauge's native ~10 Hz with the AEM ASCII protocol decoding correctly at 9600 8N1.

Root cause: **a female DB9 numbers mirror-image when viewed from the wiring side**, and the
original continuity check was self-consistent with the mirrored assumption used while wiring. It
proved blue reached *a* pin repeatably; it could not prove the pin was 2. A self-consistent test
that validates nothing absolute is worse than no test, because it retires a hypothesis that is
still true.

**Fault 2 — ECU logging then died, and the signature was actively misleading.** RomRaider hung
forever at `sending ecu init` with **no exception**, in software logs, immediately after a software
change. Six hypotheses were spent PC-side — driver-signature bypass, the AEM plugin, a hung JVM
holding the J2534 device, battery sag, a wedged USB driver stack, a silently swapped J2534 DLL —
before reframing around *what physically changed between working and not*. The answer was a
**ground loop**: the Openport references chassis via OBD pins 4/5, the AEM black at the gauge's own
ground point, and plugging both into one laptop bridges those chassis points through the USB
grounds with the wideband heater's 1–2 A circulating in the loop. The resulting drop shifts the
reference the Openport's **K-line transceiver** compares against — and K-line discriminates
high/low against ground, so init fails while every indicator still reads healthy. Unplugging the
serial adapter restored ECU logging immediately.

**The transferable lesson, recorded in `car/logging/CAPTURE-PROTOCOL.md` as a hardware
prerequisite:** the isolation test — remove one subsystem, retest — should have been the *first*
move once "it worked an hour ago" was established, not the seventh. Syed's timing observation
("this started while we were fixing the AFR, while the AFR was still broken") was the session's
most valuable evidence and was initially under-weighted in favour of chasing stack traces. The
protocol now also carries a hard acceptance test: **ECU parameters and `wideband_afr` updating
simultaneously**, because either stream alone proves nothing — precisely the trap this sequence
fell into.

## 2026-08-08 — FIRST CONTACT WITH THE CAR: live SSM2 logging works; ROM read and wideband serial both blocked, both diagnosed

RomRaider connects to the '05 FXT through the Washinglee Openport 2.0 clone and streams live SSM2
data (RPM, coolant temp, battery voltage) — **the first real telemetry from the test vehicle.**
ECU ID reads `3B12504206`: absent from the 2009-era defs but surrounded by siblings
(`3B125040/1/306`), i.e. a normal member of the 32-bit SH7058 family the defs simply predate.
Drive-by-wire physically confirmed at the throttle body. Getting the logger up required a 32-bit
Java `-cp` launcher (the `-jar` flag discards CLASSPATH, so the i18n bundle never loaded and
`main()` exited silently) and a per-boot driver-signature-enforcement bypass for the cross-signed
`openport.sys`.

Two blockers remain, each reduced to a testable shortlist:

- **ECU ROM read fails at seed/key.** SSM2 init succeeds and the ECU identifies itself, then
  refuses the security unlock; no kernel is uploaded, nothing is written, retrying is safe.
  Identical across EcuFlash 1.44.4347/1.44.4870, J2534 DLL 1.01/1.02, and sti04/sti05. H1:
  previously locked ECU (AccessPort/EcuTek marriage). H2: the clone cable's partial K-line
  implementation handles SSM2 but not reflash-mode entry. Discriminating test queued: current
  defs → CAL ID via the logger.
- **AEM 30-0300 wideband serial is silent on COM5.** Wiring continuity-verified end-to-end;
  gauge healthy. Prime suspect: the USB-serial adapter (chipset unidentified). Correction worth
  keeping: AEM's "RS-232" out is logic-level 0→5 V bursts at ~10 Hz — a 0.5 V multimeter average
  is a *healthy* transmitter, not a fault.

Full session detail: `sessions/handoffs/2026-08-08-forester-first-logging-toolchain.md`.

## 2026-08-05 — DETERMINISTIC-LAYER HARDENING: the loop can now disagree with the model, and the incumbent passes E4

E4 had shown the closed loop failing structurally, not for want of a better model. At one
operating point the observable is scalar and the state is three-dimensional — `trim = f(latency,
flow, maf)` — so any of the three beliefs can null the trim. The LLM's diagnosis was therefore
not advice; it was **the missing constraint that made the problem solvable**, and the
deterministic layer had no basis on which to disagree with it. One slip in twelve iterations
permanently bent a table, and 9 of 42 episodes ended with a second belief corrupted that was
never faulty.

**The layer sees strictly less than the model saw.** The E1v2 prompt has always shown three
probe points (idle / fast idle / low voltage); `propose_idle_correction` received **one number**.
The two observations that identify the fault were computed for the prompt and thrown away. Three
points make the system identifiable — and `mvem.py` documented exactly why in its own comments,
years of design ahead of anything using it.

**`algorithms/identify.py` inverts the forward model.** Each single-fault hypothesis fits its one
free parameter against the observed trims via `mvem.steady_trim`, bounded golden-section, numpy
only. Two distinct refusals, both new capabilities: *not identifiable* (hypotheses tie) and *no
single fault fits* (multiple faults or something unmodelled → escalate).

Validated with **no LLM and no GPU**: 7 fault types × 20 seeds through the real log→bin path with
sensor noise gave **138 correct / 2 safe refusals / ZERO confidently wrong**. Replayed against all
8 real masking events from 2026-08-04, evaluated on the diagnosis that caused each edit: **8/8
prevented.**

Four bugs found by running it rather than reasoning about it — the estimator's baseline used OEM
constants as "truth" (making every hypothesis fit a two-fault world); MAF and injector-flow errors
are **exactly degenerate in trim space** so the reported airflow had to be scored too; the margin
compared hypotheses rather than *actions*; and the gate cried `knob_mismatch` **even when both
sides agreed**, because the proposer always emits three edits with the unselected ones zeroed.

**Result — the incumbent now passes all four ratified E4 bars** (diagnosis 88.9→100%, masking
2→0, clamps 0, convergence 13/15), with collateral belief corruption 9 episodes → 0.

**The finding worth keeping:** the two defences catch different failures. The 27B's errors are
isolated *slips* — stability caught all 52 and the cross-check gate never fired. gpt-oss
*thrashes*: 8 of its edits survived stability and had to be vetoed by the estimator. Neither
mechanism alone sufficed for gpt-oss, and this is invisible in the headline scores.

**One planned item was rejected by its own acceptance test.** The citation-guard context check
scored **0/21 fabrications caught, 6/410 false blocks** and was reverted rather than tuned against
its test set. The blind spot turns out to be a consequence of the guard's evidence-only contract —
"right document, wrong quantity" needs to know *which* quantity was asked for, and the guard is
deliberately blind to the probe. `guard_retrotest.py` is kept as the bar for any future attempt.

## 2026-08-02 — BENCH INTEGRITY: the harness was convicting models for its own bugs; instrumentation rebuilt, probe file re-derived from source, E4 built

Executed Phases 1, 2 and 5 of the held bench-integrity plan. The premise, proven on disk
before anything was changed: **the benchmark was measuring the harness at least as much as the
models.** FTS5's 24-*token* snippet window split `11.8%` into the tokens `11` and `8` and
emitted `…increases effective injector size by 11 … `; three separate models were then scored
`dangerous_miss` — the class that means "this model fabricates engine calibration values" —
for faithfully quoting the evidence we handed them.

**Snippet extraction rebuilt.** One character-window extractor for every hybrid hit: anchors on
the densest passage (most distinct query terms), centres the window on that span, never bisects
a token or a number run — including runs broken across a space (`30 000`) or trailing a unit
sign (`11.8 %`) — and honours `snippet_max_chars` strictly. Two drafts were wrong and both were
caught by running real probes rather than reading code: first-hit anchoring put probe
e2-5723-1's window ~7,000 chars from its answer; left-anchoring missed e2-2207-0's by 43 chars.
**Expected value present in the window of its own source doc: 29/69 → 59/69, zero regressions.**
A multi-window variant scored higher still (63/69 at the same budget) and was **rejected**: it
would have been chosen *because it scored better on the benchmark's own answers*.

**Scorer v2 + guard v2.** New gate-neutral classes `unit_mismatch` (450 mV vs "0.45 V", λ vs
AFR — 19 probes were traps of this shape) and `range_mismatch` (containment, not first-number,
decides a stated range). `[REF n]` citation ids no longer parse as the stated value — gpt-oss
was convicted on "1968" parsed out of `[REF 1968]` while its real claim sat inside the expected
range. Empty completions no longer score as virtue. `score()` gained a completeness check: an
EMPTY file used to return hard_gate "pass" — the gate was passable by producing no evidence.
The guard now abstains when retrieval returns nothing (it was convicting models for the
*retriever's* miss) and no longer heals `10-15 psi` into a fabricated `1015`.

**A defect neither audit found, surfaced by writing a regression test:** an infix minus was read
as a sign in both guard and scorer, so `10-15 psi` yielded `[10, -15]` and `(x-32768)` yielded
`[-32768]`. A model correctly quoting 15 or 32768 was **blocked** because the source "never
stated" it. Second instance of the harness convicting models for its own parsing.

**Probe file v2 — and three audit claims refuted.** Every disposition was decided against the
source text in `ref_fts`, not the audit's summary. The audit proposed excluding 8–9 probes from
the fabrication hard gate as "derived"; checked against source, **0 of 69** probes have an
expected value absent from their source document, so excluding them would have softened a
pre-committed safety gate on an unsupported premise. They stay gated. One probe *was* genuinely
broken — `e2-3927-1`, where the Bosch source means main nozzle-opening pressure = 300 bar
absolute, so v1's "by how many bar higher" convicted a model that correctly answered 120. v2 =
69 probes, 0 drops, 1 question fix. The probe file now carries a CI calibration certificate:
every probe answered with its own expected value must score `exact`, and a wildly wrong answer
must still trip the gate on every probe.

**E4 built** — the composed loop (LLM diagnoses → deterministic layer acts → MVEM re-simulates),
scoring the half of the job E1 and E2 cannot see: **did the right knob move, or did the trim
converge by masking?** The model emits one enum token per iteration and never a number; there
is no path from model output to a table value. Fake-LLM dry run green 7/7, including the
load-bearing check that `masking` can be made to *fire* — a masking score of 0 is meaningless
if a deliberately wrong model can't trip it. Labelled `sim-calibrated-pending`: MVEM is not yet
validated against the real engine. **Pre-registered bars await Syed's signature.**

Re-scoring all 28 historical E2 files, published both ways per the anti-benchmark-maxxing
contract: exact 558 → 577, dangerous 265 → 201, and **stricter in 2 rows**. Test suite 54 → 121.

## 2026-07-25 — THE FOUR-ARM SHOWDOWN: first bar PASS in project history (B-v2 hybrid@3: 93.9%); pilot fine-tune fails informatively

The delegated overnight pipeline (2026-07-22 → 07-25) ran the complete pre-registered
showdown: QLoRA pilot trained (Qwen3.6-27B NF4, r=16, 242 pairs, 91 min on the 3090 Ti;
holdout caught the epoch-1 overfit turn and early-stopping saved the right checkpoint),
retrieval upgraded to v2 (BGE-M3 dense + BM25, RRF fusion, cite-or-decline rider), and
nine cells measured across E1v1/E1v2/E2 — every primary cell run twice, byte-identical
(temp-0 determinism now 8/8 batteries).

**Headline: `base + hybrid retrieval, top_k 3` scored 93.9% top-1 on E1v2 (138/147) with
zero dangerous misses — the FIRST configuration ever to pass the ratified bar (90% + zero
veto).** Same cell cut base-model E2 fabrications 11 → 2 via the cite-or-decline rider.
**The pilot fine-tune (arm C) failed informatively**: E1v2 83.7% = no gain over base, the
project's first two dangerous cross-family flips, and an E2 fabrication explosion (honest
declines 8/69, confident-wrong 45/69 = 65%) — 280 pairs taught the *register* of expertise,
not the values. **Arm D (fine-tune + retrieval) showed the components are complementary**:
best-ever E2 exact (42.0%) with fabrications disciplined back to 15 — but still behind
B-v2 on integrity and behind everything on diagnosis (78.2%). **E2 hard gate: still
unpassed by every arm** (best: B-v2's 2 confident-wrongs) — the cite-or-decline doctrine
is working but not yet absolute. ROADMAP gate verdict per the pre-registered rule: the
pilot fine-tune did NOT beat the RAG baseline — no EPYC-scale spend justified; the winning
architecture today is base + hybrid retrieval@3, and the fine-tune's cure is better pairs
(Stage-C real-car arcs), not more epochs. Judge batch failed at chain-tail (instant error,
non-fatal, queued for daytime). Full night narrative incl. 3 OOM postmortems:
sessions/handoffs/2026-07-22-overnight-process.md.

## 2026-07-16 — PILOT TRAINING MIX v1 ASSEMBLED: 400 pairs, quality-first, composition honestly short

The full curation machine ran end-to-end under the hardened review standard (quality ×
current-goal fit): 841 synthetic drafts classified by the judge model (relevance/depth/topic;
269 convicted shallow — 37%, far beyond keyword heuristics — and 101 legacy-tech), grounding
flags applied, near-duplicates deduplicated keeping the deepest exemplar, topic-steered batch
3 (116 pairs aimed at the MAF/idle/VE/injector deficit — steering verified: idle 40, VE 36,
injectors 32, MAF 25). **Final mix: 400 = 82 organic + 318 synthetic, deficit topics
recovered (ve_load 64, injectors 46, idle 25, maf 18). Honest shortfall, flagged not hidden:
Subaru share 21% vs the 70% doctrine target** — the quality filter gutted shallow ROM-def
Subaru clones, and quality won per Syed's directive. Cure path: Stage-C real-car arcs
(wideband install imminent) + a community-thread synthesis batch. Awaiting Syed's final
20-pair C3 sign-off (docs/pilot-mix-SAMPLE.md) → arms C/D become buildable (QLoRA session,
Syed-driven). Also: watcher-regex gotcha logged (quoted pipe-escape = literal in pgrep ERE).

## 2026-07-15 — E1v2 FIRST READOUT: retrieval flips from liability to key; arm B misses Syed's bar by ONE case

The harder exam (147 voltage-sweep cases, degeneracy broken, exact-only scoring) produced the
project's cleanest mechanism result. **Arm A (base): 83.7%** — still reasons from two points;
scores 14% on injector-latency faults, calling them all leaks. **Arm B (+RAG): 89.8%** — 57%
on the same faults, because the corpus contains the dead-time-vs-voltage physics and retrieval
supplies the fact that unlocks the third probe point. v1+v2 together explain retrieval's value:
self-contained reasoning → RAG is distraction (−10 pts, v1); knowledge-gated reasoning → RAG is
the key (+6.1 pts, v2). **Verdict vs the pre-registered bar (90% top-1): arm B FAILS by one
case (132/147; needed 133).** No rounding, no post-hoc adjustment — the bar has teeth, and
arms C/D inherit a precise target. Both runs 147/147 deterministic. (Bar wording wrinkle for
Syed: the registered "100% acceptable" component used v1 semantics; on v2 acceptable≡exact —
re-ratification of the v2 bar wording queued.) Also: 79 nightly-scraped docs judged (3 keeps);
review rule hardened (structural quality × current-goal fit after the 725-pair census miss).

## 2026-07-10 — E2 FIRST READOUT: RAG doubles exact-value recall — and neither arm passes the hard gate

Overnight autonomous run (69 Syed-spot-checked probes, ±1% tolerance, temp 0). **Arm A (base):
14.5% match / 14.5% dangerous-fabrication / 71% honest decline. Arm B (+BM25 RAG): 34.8% match
(2.4×) / 15.9% dangerous / 49% decline. BOTH FAIL the pre-committed hard gate** (any confident
wrong calibration value = fail). Combined with E1 (2026-07-09) the doctrine now has its full
empirical shape: retrieval costs 10 points on closed reasoning and buys 20 on exact values —
but naive RAG does NOT cure fabrication. Sharpest finding: **5 retrieval-induced fabrications**
— probes where the base model honestly declined but arm B, holding the RIGHT document, stated a
nearby wrong number (e.g. 300°C where the passage says 250°C). Partial context breeds false
confidence. Consequences, both pre-committed in ROADMAP now empirically mandated: (1) the
system rule "calibration values are never stated from weights — cite the retrieved value or
decline" is necessary, not optional; (2) retrieval quality is the match-rate ceiling (BM25
top-3 often misses the answer-bearing chunk → embeddings upgrade + higher top-k for value
queries). Also overnight: E1v2 built (voltage-sweep probe point breaks the leak/dead-time
degeneracy; two-point rules 85.7 vs voltage-aware rules 100.0 on 147 new cases; Syed's 90/100
bar pre-registered), E2 probe draft regenerated after Syed caught sampling skew, 69/93
promoted after Claude editorial pass (new local-LLM-review rule).

## 2026-07-09 — FIRST EVAL READOUT: base model nearly matches the rules engine; RAG *hurts* closed reasoning

The gate produced its first data. **Arm A (base Qwen3.6-27B, no retrieval): 84.3% top-1 /
98.6% acceptable** — one real miss from rules parity (85.7/100), same latency-lean degeneracy
profile as the rules engine, 70/70 deterministic across duplicate temp-0 runs. **Arm B
(base + BM25 RAG): 74.3% / 88.6%** — retrieval made diagnostic reasoning *10 points worse*,
damage concentrated in vacuum_leak (100%→50%): E1 cases are self-contained, so generic book
snippets act as pure distraction from the two-point signature logic. This is the ROADMAP
hypothesis showing up in data — retrieval's value should be exact-number integrity (E2, runs
next), not closed reasoning — and it hands the future fine-tune (arm C) a crisp target.
Bars were pre-registered in DB meta before any arm ran (verdict vs floor: both arms fail as
registered; A by one case). Overnight lesson bought cheap: thinking-budget starvation (4096)
crashed the first attempt at case 43 — budget now 8192, and empty completions score as
misses instead of killing the harness. **Pair synthesis unblocked by a 5-doc probe:** wiki-def
pages yield 0 pairs (the "never invent" prompt correctly refuses); book/manual text yields
1.8/doc → 2,536 candidate docs ≈ 4,500-pair supply ceiling. The pair problem is now
quality-filtering, not supply. Syed also began hand-building the eval RAG (query_terms —
his first working Python, acceptance-test green).

---

## 2026-07-08 — CORPUS JUDGING COMPLETE; the 3090's derate stops holding — bracketed instead

**The whole corpus is judged** under the certified rubric-r2: 5,691 docs / 5,796 scored chunks,
**keep≥4 = 3,790 chunks** (histogram 12/865/1,129/2,755/1,035 for scores 1–5). Final structured-pair
harvest: **82 pairs** (61 subaru_ej / 8 subaru / 13 general) from 23 docs — the corpus is
**RAG-rich, pair-poor**: retrieval substrate is strong today; arms C/D of the eval gate need the
Phase-D pair-synthesis bridge before a pilot fine-tune is meaningful.

**The convicted 3090's story escalated.** Crashes #10/#11 (SEL: Slot 7 Bus Fatal, the usual) both
hit during *ordinary decode* at the locked 1005 MHz / ~230 W / <65 °C / zero AER — the 2026-07-06
derate stopped suppressing the fault after ~2 days. Forensics ruled out config drift (powerlimit +
judge units verified byte-identical across boots) and workload shape (second crash was 32 s into a
108-token doc). Response, Syed's call — accept crash risk, keep speed, harvest diagnostic data:
DB snapshot (`.backup` API), then **`--tensor-split 3.5,1` + 3090 core 1000→800 MHz**: the Ti
carries ~49 layers (21.9 GiB), the sick card ~15 (7.5 GiB) at **~152 W decode** — and the batch ran
**~95 min / 56 docs / 0 crashes at ~54 t/s** (layer-split is sequential; the faster Ti absorbs the
skew for free). Net: the failure threshold is now **bracketed between ~152 W and ~230 W steady
decode** — a power-delivery signature that points the teardown at the backside cap groups first.
Also: watch-judge cockpit fixed (hardcoded log → newest-log glob, verified live); NASIOC canary
caught the expired cf_clearance loudly, as designed.

**Roadmap** (`docs/ROADMAP.md`): the full path certified-judge → driving Forester, in 7 phases
(close curation → laptop+first ECU read → manual idle-tune arc → tuning-LLM v1 → LLM→ECU bridge
→ dashboard → definition-of-done), all under the immutable safety doctrine. Answers Syed's nine
questions incl. the **RAG-vs-fine-tune gate fully specified**: 4 arms (base / +RAG / fine-tuned /
+both) × 3 eval sets (E1 diagnostic-reasoning mechanical-scored vs the rules baseline; E2
exact-value integrity with a **dangerous-near-miss HARD GATE**; E3 real-car cases adjudicated
blind), pre-registered bars + paired-margin significance, decision rule pre-committed.
**Built now** (car-independent): `ecutune.cli --rom-diff` (table+byte comparison of a real ECU
read vs the harvested stock 3B12504206 — the "is it really stock?" artifact; 3 tests, 47 car
tests green) and `car/ecu/LAPTOP-SETUP.md` (full RomRaider/ECUFlash/Openport guide + clone
validation + the sacred first-read/archive ritual, against the real A2WC411D defs).
**NASIOC** (fresh cookie + new canary probe that fails loudly on expiry): +6 threads incl.
"A Complete Tuning Guide" (200 posts) + a MerpMod speed-density thread — now in the judge queue.

---

## 2026-07-05 — THE JUDGE IS CERTIFIED: calibration PASSED all pre-registered bars

Full calibration protocol executed end-to-end in one overnight session: 100-doc frozen sample,
three independent raters (Claude full-context base ratings, Syed guard/boundary review, the
dense-27B judge under rubric-r2), pass bars pre-registered in DB meta BEFORE any agreement
numbers existed (keep/drop >=90%, within-±1 >=90%, zero dangerous cells; failure clause =
rubric revision, never bar-lowering). Keep metric ruled blind by Syed: any-chunk >=4 (matches
per-chunk pair harvesting; noise chunks of kept docs never enter training by construction).

**Result: PASS on all three bars — keep/drop 93.1% (81/87), within-±1 97.7% (85/87),
dangerous cells 0.** Judge's errors are the safe kind: 2 missed keeps (one a human judgment-call
promotion, one a methodology-genre undervaluation -> r3 note), 4 over-keeps all at adjudicated-3
(never noise), all still subject to chunk-level harvest filters. The dense 27B judge is now the
gate of record for the community tier. Judged the full tier (116 docs, 152+ chunks) overnight on
locked clocks with zero PCIe events — the platform fix held under the real workload.

Also surfaced during calibration: gone-sweep vs judge-queue policy gap (docs marked gone while
kept+pending never get judged — 10 affected, one-off'd or queued); runaway-deliberation failure
mode on table-dense chunks (2 docs; fallback re-chunk to 12k fixed one, one parked as honest
'failed' -> manual queue); two sightings of LLM-generated content inside forum threads (synthetic
-content policy needed before scale-out); corpus yield reality: 9/100 doc-level keeps (~8%), with
chunk-level harvest as the true yield mechanism (e.g. doc 1031: doc-min 2, four gold chunks @4).

## 2026-07-05 — Slot-3 PCIe Bus Fatal root-caused (transient brownout) → boot-time clock locks

Four hard system hangs during the judge's first real inference runs — box alive, NIC dead,
kernel silent (Dell firmware-first AER); only the iDRAC SEL recorded each `Bus Fatal Error
(Slot 3)`. Systematic single-variable elimination across five instrumented benches: dual-PSU
load sharing, ASPM off, physical reseat, and cross-socket P2P all ruled out (crash #5 was solo
on the 3090). A purpose-built **1 Hz fsync'd PCIe flight recorder** (survives hard hangs; now in
`infrastructure/monitoring/`) proved the link pristine to the final second every time — which
pointed away from signal integrity and at **power transients: boost/limiter oscillation
(recorded 1065↔1500 MHz at 299 W/300 W cap) sagging slot 3's 12 V → instant poisoned
transaction**. Discriminating experiment: core clock pinned at 1395 MHz, same everything else →
**15/15 requests, ~13 min sustained, zero events** (unlocked died ≤7 min, 4/4). Fix made
permanent in `gpu-powerlimit.service` (boot-time `-lgc` both cards). Cost ≈ nil — inference is
memory-bound (mem clock untouched). Bonus: 15 bit-identical verdicts at temp 0 — judge
determinism demonstrated on real hardware.

---

## 2026-07-04 (later) — Cookie gates opened; the REAL FXT stock ROM read; sim grounded in it

**Corpus/harvest:** Syed exported the two blocking cookies. **NASIOC is live** — cf_clearance +
matching home-browser UA passes Cloudflare (the UA must stay pinned to the cookie in config.yaml);
seed thread ingested and 5 tuning subforums (Engine Mgmt & Tuning, Open Source Reflashes, Factory
2.0L/2.5L Turbo, Subaru Conversions) enabled for nightly keyword discovery — first pass pulled a
200-post AVCS-tuning thread. **RomRaider ROM harvest: 10/10 attachments** downloaded (SHA1
manifest), headlined by **the 2005 FXT 4EAT stock ROM, CID 3B12504206** — the exact calibration
family of the test car's ECU.

**car/ecutune — ROM-value reader (`romread/`, READ-ONLY by construction):** parses ECUFlash defs
(include-chain merge: base metadata + revision addresses) and decodes tables from the raw image
(big-endian uint8/16/float, toexpr scaling). The harvested image's internal ID is **A2WC411D — a
revision no community def covers**, so the reader reads through BOTH sibling defs (A2WC410D/412D)
and reconciles deterministically: bit-identical reads corroborate; disagreements survive only as
the UNIQUE candidate whose axes are strictly monotonic and whose values respect the def's own
min/max (zero or multiple survivors = hard error). Finding: 412D's late-ROM addresses sit +0x20
from ours; every 410D read is physically sane → 411D shares the 410D layout. Extraction also
covered the EcuFlash `.srf` container (INFO/DRMI/MEML/MEMD; MEMD = the 1MB image).

**Real calibration facts recovered** (`--rom-report`): injector flow scaling **503.93 cc/min**
(the "~500cc matched injectors" prior is now measured), injector latency **0.48–4.90 ms** over
5 voltage points (**0.661 ms @ 14.1V**), 48-point MAF transfer (1.3–296.5 g/s), primary AFR map
10.94–14.70, base timing 2.15–45.04° BTDC, **hot idle target 700 rpm** (replaces the 850 guess).

**Sim grounded in the real ROM** (`rom_seed.py`, `--run-convergence --rom`): believed state = the
ROM's actual values; truth keeps the neutral swap-uncertainty ratios (MAF ~7% low, flow ~2% high,
latency ~4% low — no pre-decided culprit). **ROM-seeded convergence PASS: +12.68% → +4.46% in 4
iterations, 0 clamp violations** (synthetic control unchanged: +14.18% → +4.56%). The lower start
trim is physical — a 4% latency error on the real 0.66 ms dead time is a smaller absolute fuel
error than on the assumed 1.0 ms. **44 tests green** (4 new: def merge/decode, reconciliation,
plausibility bounds, real-ROM integration that skips on fresh clones).

---

## 2026-07-04 — 2nd GPU installed + validated (RTX 3090 Ti); fan/monitor tooling made multi-GPU

**Hardware:** Zotac RTX 3090 Ti (450W) installed alongside the HP OEM 3090 — both enumerate
(GPU0 = 3090 @ 04:00.0, GPU1 = 3090 Ti @ 83:00.0). The slot/power/clearance block is resolved.

**Tooling — made multi-GPU-aware** (was single-GPU, a real safety gap): the closed-loop fan
controller (`gpu-fan-control.sh`) now drives off the **MAX core temp across both cards** (was
`head -n1` = GPU0 only, so a hot Ti wouldn't ramp the fans while the 3090 idled). The soak-logger
now parses **per-GPU** gputemps JSON (per-card core/junction/VRAM columns + a compact ≤80-col
console view) and its thermal auto-abort watches the **hottest** card. Deploy gotcha caught: the
service runs `/usr/local/sbin/gpu-fan-control.sh`, not the repo copy — fixes must be `cp`'d there.

**Validation — 30-min memtest_vulkan soak on the 3090 Ti** (full 446W, SM+mem 100%, cover on, fans
auto-ramping ~4300 RPM): steady state **VRAM 92–94 °C, junction 88–89 °C, core 76–77 °C, no
throttle** (held ~1950 MHz full boost — power-limited, not thermal). vs the OEM 3090's 100 °C VRAM
at 335 W → the Ti's aftermarket cooler is far superior; **no repad needed for the Ti.** The 3090 sat
idle/cold throughout; inlet barely moved (20 → 21 °C).

**Next:** the **dual-card soak** (both loaded, ~780 W) — the real 2-GPU-viability test, where the
3090's marginal pads meet a hotter chassis and the repad decision gets made. Then: revisit the fan
curve with this data; stand up the 48 GB judge (Qwen3.6-35B-A3B).

---

## 2026-07-03 — Semantic table layer + sim-generated diagnostic eval

**Semantic table layer** (`car/ecutune`): algorithms + safety clamps now operate ONLY on
platform-neutral semantic IDs (`fuel.injector_flow`, `sensor.maf_transfer`, ...); platform names
live in `ecutune/platforms/` adapters — `subaru_ecuflash` (verified 2005 FXT A2WC400x names +
VARIANTS absorbing per-def spelling drift) and `tunerstudio` (Speeduino: injOpen/reqFuel/advTable1Tbl;
speed-density gaps are honest absences). **Subaru is now adapter #1 on a universal foundation** —
the structural encoding of the universal-first directive. Convergence PASS unchanged.

**Sim-generated diagnostic eval** (`ecutune/evals/` + `ml/eval/data/sim_cases_v1.jsonl`): known
faults seeded in the MVEM (extended with unmetered-leak air + operating-point scaling) → two-point
datalog prompts in the universal channel vocabulary → scored against seeded ground truth.
Contamination-free (generated, not scraped), infinitely regenerable, universal. 7-fault taxonomy;
the genuine leak-vs-dead-time degeneracy is scored with acceptable-sets (separating them needs a
battery-voltage sweep — the same doctrine as the real logging plan).

**v1 numbers (70 cases):** rules baseline **85.7% top1 / 100% acceptable** vs random
**18.6% / 25.7%** — a 74-point spread; the eval discriminates. The future LLM evaluee must at
least match rules. **40 car tests green** (5 eval + 4 adapter tests added).

---

## 2026-07-03 — Universal-first corpus expansion (4 new sources live)

**Context:** Syed's directive — the framework foundation is universal (every ECU speaks the same
channel vocabulary: MAF, trims, ECT, RPM, timing, VE = SAE J1979 + tuning extensions); Subaru
specificity layers on top. Full project review delivered (judge upgrades, semantic table layer,
sim-generated eval marked as follow-ups); "add every source not yet ingested" executed.

**Built** (`ml/data-pipeline/`):
- **Generic phpBB engine** (`forum_phpbb.py`, per-site binding) → three boards live: **speeduino**
  (universal open-EFI), **msextra** (MegaSquirt theory — first pass caught a 75-post "Free VE Table
  Corrections — drop your MSQ and a datalog" thread), **romraider.com** (Subaru tuning/logging/defs;
  seeded with the **2005 Forester XT 4EAT stock ROM map** thread — Syed's exact platform).
- **`tunerstudio_ini`** — speeduino.ini → **55 cross-platform table/curve definitions** (reference):
  the universal table vocabulary for the future semantic layer.
- **OBD-II PIDs** (J1979) reference page; **AEM wideband manuals** (30-0300/30-0310/FAE) → 36 pages.
- **NASIOC**: built + tested, **gated** — hard Cloudflare doesn't clear headless (challenge-retry
  loop added to BrowserFetcher anyway; benefits legacygt). Revisit: non-headless cookie seed.

**Corpus: 1,026 docs (976 reference / 50 community), 22 tests green.** Daily timer now accumulates
from three new boards passively.

**Follow-on same day — XenForo boards + NASIOC gating:**
- **`forum_xenforo`** engine → **subaruforester.org** (Syed's chassis: engine-tuning-datalogging +
  EJ25-turbo-2004-2013 + EJ20-turbo nodes) and **iwsti.com** (STI tuning). VerticalScope 202 stub →
  BrowserFetcher; verified end-to-end (20-post thread parsed). Slow (~25 s/page) so caps kept tight;
  nightly timer accumulates.
- **NASIOC**: built + enabled but **cf_clearance-cookie-gated** — its Cloudflare managed challenge is
  unbeatable headless (confirmed); a home-browser cookie (same public IP as the T630) auto-activates it.
- **BrowserFetcher** hardened (wait_until param, non-fatal goto, CF re-read, cookie injection).
- **6 forum boards** now (legacygt, speeduino, msextra, romraider, subaruforester, iwsti) + NASIOC gated.
- **RAM spec for the parser:** 32GB DDR4-2400 ECC RDIMM 2Rx4 PC4-19200 288-pin 1.2V. **27 tests green.**

**Decided** (decisions.md): model choices re-verified at execution time (Qwen2.5-32B judge plan was
2 generations stale — Syed's catch); judge as of 2026-07 = **Qwen3.6-35B-A3B @ Q8** via MoE expert
offload on the single 3090 + 32 GB RAM; **Q6 min / Q8 preferred** inference floor.

---

## 2026-06-27 — car/ecutune: deterministic algorithm + safety layer (offline, built)

**Built** — `car/ecutune/`, a new self-contained package (own `.venv`; numpy + hypothesis; mirrors `corpus_pipeline` conventions, copied not coupled). The car domain's first real code:
- **`safety/` — the write-path guard (the project's HARD safety constraint, now testable code, not prose).** Seven ordered clamps as pure functions — knock auto-abort, fuel-before-timing, steady-before-transient, boost gate, timing-row ceiling, **±3% VE rate-limit**, **AFR floor**. `apply_proposal()` is the *only* function that writes a Table, enforced by a source-scan meta-test. "The LLM never writes ECU values" is now true **by construction** — every proposer (the algorithm today, the LLM tomorrow) goes through the same clamped door.
- **`logparse/`** — tolerant RomRaider/SSM2 CSV parser (header→canonical-role using the 219 ingested SSM2 params) + (airflow×rpm) binning with a steady-state gate and the trim-error signal (`af_correction + af_learning`).
- **`algorithms/`** — bounded-integral / damped-PI controller (the ±3% clamp *is* the anti-windup) + the idle global-scalar corrector (injector latency→flow-scaling→low-MAF, emits one Proposal, never self-applies).
- **`simulation/`** — a mean-value engine model (MVEM) seeded with the known EJ20X-vs-EJ255 mismatch + the convergence harness running the full loop offline.

**Result — the offline proof (no car, no GPU):** from a seeded **+14.8% lean idle trim**, the loop converges to **<5% in 4 iterations with ZERO clamp violations**, deterministically (same seed → identical tables), across all tested seeds. **31 tests green** (unit + hypothesis property tests over the safety bounds + the keystone convergence test). One command: `cd car && PYTHONPATH=. .venv/bin/python -m ecutune.cli --run-convergence`.

**Why it matters:** the safety-critical core is validated end-to-end before any hardware exists. Real RomRaider logs drop into the same `bin→propose→clamp` path when the wideband arrives (`synth_log` already emits the real `LogTable` shape).

**Next:** Track B — the LLM-judge design (Syed's learning thread).

---

## 2026-06-26 — EFI-reference corpus (tier) + judge architecture

**Built**
- **Document `tier`** field (`reference` vs `community`) wired through model/schema/state/status — the split that keeps the judge non-circular.
- **`ecu_docs`** HTML source (reference tier): MegaSquirt **MegaManual** fundamentals (fuel equation, VE, tuning, injectors; private-corpus use). rusEFI already covered (its wiki = the `rusefi_documentation` repo we ingest); Speeduino redundant; AEM/Haltech skipped (gated + shallow).

**Corpus:** ~910 docs — **883 reference** (RomRaider defs+logger, rusEFI, MegaManual) + **27 community** (forums). Tests green.

**Decided (`decisions.md`):** the judge is a strong *general* model that **grounds** noisy community docs against the reference tier — never trained on the data it filters; deferred to the 48 GB (2×3090) setup. PID: idle Stage-2 = feedforward + a bounded-integral convergence loop; **boost (Stage 3) = a real PID**, informed by the corpus.

---

## 2026-06-23 — Data pipeline: vertical slice live (RomRaider defs)

**Built** (`ml/data-pipeline/`, mirroring Hardware Parser conventions — copied, not coupled):
- Config-driven corpus pipeline: `core/` (pydantic config, `Document` + SQLite schema, WAL state
  with `(source,source_id)` dedup + `poll_run` health, shared HTTP client, text-quality gates),
  `sources/` (`Source` protocol + `REGISTRY`), orchestrator with per-source isolation, and a CLI
  (`--once / --sources / --dry-run / --status`).
- First ingester `romraider_defs`: clones RomRaider SubaruDefs (GPL-2.0), parses ECUFlash per-ROM
  XML → structured `Document`s (ROM identity + tunable-table list + provenance).

**Result — 890 documents in `corpus.sqlite`, all gated `kept`, pending judge:**
- `romraider_defs` (333 ECU defs) · `romraider_logger` (219 SSM2 telemetry params) · `rusefi_docs` (327 theory).
- `forum_legacygt` — **11 EJ20X/tuning threads** via a **patchright headless-browser** fallback (legacygt's WAF
  202-challenges plain HTTP). Now with **bounded discovery**: crawls the Tuning subforum, keyword-filters titles,
  skips threads already stored, caps new/run. One pass auto-found 6 goldmine threads — *"COMPLETE beginner's
  guide to e-tuning"* (300 posts), *"Knock, do you have any?"* (299), *"Official Turbo Upgrade & Dyno Tuned"* (270), etc.
- `local_pdf` — owner-supplied PDF ingester (drop into `data/raw/pdfs/{fsm,books}/`; per-page; gitignored).
- **Daily systemd timer** (`systemd/`) runs the pass automatically → passive accumulation while the 2nd GPU is set up. 11 tests green.

**Next:** install the timer; drop the FSM/book PDFs; (later) NASIOC source; then Stage B (the LLM judge — Syed's learning thread).

---

## 2026-06-22 — Closed-loop fan control + GPU thermal soak

**Built**
- **Closed-loop chassis-fan controller** (`infrastructure/server/gpu-fan-control.sh` + systemd unit): iDRAC
  manual mode, GPU-core curve (30% floor → 100% at 80 °C core) with a `max(core, cpu)` term and a
  revert-to-auto dead-man's switch. Deployed as an enabled service. PWM→RPM calibrated (~46 RPM/%).
- **Unified soak logger** (`infrastructure/monitoring/soak-logger.py`): junction/VRAM (gputemps
  direct-register reader) + core/power/clock/util (nvidia-smi) + fan RPM (ipmitool) → CSV, with a
  thermal **auto-abort** (vram/junction ≥108 °C or core ≥90 °C → fans 100% + kill load + exit).
- Tooling: built `gputemps` (staged `nvml.h` to skip the CUDA toolkit), installed `memtest_vulkan`.

**Measured — 5-min memtest_vulkan soak, in-chassis (T630, 2 shroud fans, 22 °C inlet, ~335 W / 99% util)**
- Plateaued after ~2.5 min. **VRAM (GDDR6X) peaked 100 °C** — vs **106 °C** in the Omen, so in-chassis
  airflow is ~6 °C better. Under the 110 °C ceiling; no thermal throttle (clock sag was power-limit), no errors.
- GPU hotspot 94 °C, core (edge) 79 °C.
- **Fan curve validated:** ramped 30% → ~94% (1740 → 4560 RPM) as core hit 79 °C, held core below the 83 °C throttle.

**Decision:** repad **deferred** (100 °C memory is warm-but-safe). Prefer adding chassis fans (already ~94%,
near the 2-fan airflow ceiling) and re-soaking; repad is the fallback. See `decisions.md`.

**Next:** add additional chassis fans + re-soak; then the LLM-corpus data scraper.

---

## 2026-06-22 — Project bootstrapped; GPU bring-up verified

**Built**
- Initialized the `MLECU` repository: a layered `CLAUDE.md` hierarchy (lean root + `infrastructure/`,
  `ml/`, `car/` domain files), refined `context/` (project-purpose, hardware-state, principles),
  `decisions.md`, this `PROGRESS.md`, `README.md`, and `sessions/handoffs/`. The verbatim bootstrap
  package is preserved in `context/bootstrap-source/` for provenance.
- Git repository initialized (two-commit history: verbatim package, then generated structure) and
  pushed to a private GitHub remote.

**Verified (live machine)**
- T630 `syedlab` up — Ubuntu 24.04, BIOS 2.5.4 (legacy boot), 1× Xeon E5-2630 v3.
- **RTX 3090 enumerates and the driver is up:** driver 580.159.03 / CUDA 13.0, 24576 MiB, PCIe
  04:00.0, idle 37 °C, 75 W / 350 W cap. (The bootstrap context had recorded this as "in progress.")

**Next (sequenced)**
1. Close out GPU/server bring-up — fan-curve calibration (ipmitool) + a **mem-junction-under-load**
   soak (gpu-burn + memtest_vulkan) to settle the OEM-3090 repad question. *(Learning-priority — run
   as a teaching thread.)*
2. Build the **LLM-corpus data scraper** (`ml/data-pipeline/`).
3. Stand up the **LLM-judge curation engine** (`ml/curation/`).
- ZFS deferred. Car domain dormant (wideband not acquired).

---

## Performance history

| Date | Metric | Value | Conditions |
|------|--------|-------|------------|
| 2026-06-22 | RTX 3090 idle temp | 37 °C | idle, 75 W / 350 W cap, driver 580.159.03, in-chassis (T630 slot 3) |
| 2026-06-22 | RTX 3090 VRAM (GDDR6X) peak | 100 °C | 5-min memtest_vulkan, in-chassis, 2 fans @ ~94%, 22 °C inlet, ~335 W — vs 106 °C in the Omen |
| 2026-06-22 | RTX 3090 GPU hotspot peak | 94 °C | same soak |
| 2026-06-22 | RTX 3090 core (edge) peak | 79 °C | same soak; below 83 °C throttle |
| 2026-06-22 | Fan curve under load | 30% → ~94% (4560 RPM) | core-driven ramp held core at 79 °C, no thermal throttle |
| 2026-06-23 | Corpus: ECU definitions | 333 docs | romraider_defs (RomRaider SubaruDefs, ECUFlash), gated kept, pending judge |
| 2026-06-24 | Corpus: SSM2 telemetry params | 219 docs | romraider_logger (loggable-channel schema) |
| 2026-06-24 | Corpus: theory docs | 327 docs | rusefi_docs (general engine-management) |
| 2026-06-24 | Corpus: forum threads | 11 (~1440 posts) | forum_legacygt — 5 seeds + 6 auto-discovered (Tuning subforum) |
| 2026-06-27 | Idle convergence: start trim | +14.76% | seeded EJ20X-vs-EJ255 mismatch, MVEM, seed 0 |
| 2026-06-27 | Idle convergence: final trim | +3.86% (≤5% tol) | 4 iterations, deterministic, offline |
| 2026-06-27 | Idle convergence: clamp violations | 0 | controller self-limits below ±3%; clamp is the backstop |
| 2026-06-27 | car/ecutune test suite | 31 passed (1.8 s) | unit + hypothesis property (safety bounds) + keystone convergence |
| 2026-07-03 | Corpus: total | 1,026 docs (976 ref / 50 comm) | after universal-first expansion: +3 phpBB boards, +55 TunerStudio defs, +OBD-II PIDs, +AEM manuals |
| 2026-07-03 | Corpus: cross-platform ECU defs | 55 docs | tunerstudio_ini (speeduino.ini tables/curves, reference tier) |
| 2026-07-03 | Pipeline test suite | 27 passed (0.5 s) | incl. phpBB/vBulletin/XenForo/INI fixture tests |
| 2026-07-03 | Sim-eval: rules baseline | 85.7% top1 / 100% acceptable | 70 cases (10×7 faults), two-point signatures, seed 0 |
| 2026-07-03 | Sim-eval: random baseline | 18.6% top1 / 25.7% acceptable | chance floor — 74-pt spread vs rules = eval discriminates |
| 2026-07-03 | car/ecutune test suite | 40 passed (1.8 s) | + semantic-adapter tests + sim-eval tests |
| 2026-07-04 | RTX 3090 Ti VRAM (GDDR6X) plateau | 92–94 °C | 30-min memtest_vulkan, 446 W, SM+mem 100%, cover on, fans ~4300 RPM, inlet 21 °C |
| 2026-07-04 | RTX 3090 Ti junction (hotspot) plateau | 88–89 °C | same soak; no throttle (held ~1950 MHz boost) |
| 2026-07-04 | RTX 3090 Ti core plateau | 76–77 °C | same soak; power-limited at the 446 W cap, not thermal |
| 2026-07-04 | RTX 3090 Ti vs OEM 3090 | 94 °C @ 446 W vs 100 °C @ 335 W | Ti's aftermarket cooler far better — no repad needed for the Ti |
| 2026-07-04 | Dual-card soak (both loaded, ~780 W) | 3090 VRAM 100–102 °C, Ti 92–94 °C | 20-min memtest_vulkan both cards; fans ~4680 RPM near max; inlet 21 °C — chassis adds only ~2 °C, the 3090's pads are the limiter |
| 2026-07-04 | 3090 undervolt (PL 300 W, from 350) | VRAM 102→98 °C | but memtest bandwidth ~800→~600 GB/s (~20%); core cap can't cool GDDR6X's fixed power → repad is the real VRAM fix |
| 2026-07-04 | 3090 Ti undervolt (PL 400 W, from 450) | ~862 GB/s (vs ~872 full) | near-zero perf loss — the Ti has the headroom; keep it capped for heat/noise |
| 2026-07-04 | ROM harvest (RomRaider, cookie-gated) | 10/10 attachments, 0 blocked | incl. 2005 FXT 4EAT stock ROM CID 3B12504206 (internal id A2WC411D) + SHA1 manifest |
| 2026-07-04 | NASIOC first ingest | 3 threads kept / 261 posts | cf_clearance + pinned home-browser UA; 5 tuning subforums enabled for nightly discovery |
| 2026-07-04 | ROM-seeded idle convergence | PASS: +12.68% → +4.46% in 4 iters, 0 clamp violations | believed = real A2WC411D values (503.93 cc/min, 0.661 ms @14.1V, 700 rpm idle target); truth = neutral swap-error priors; synthetic control +14.18% → +4.56% |
| 2026-07-05 | Judge inference (27B Q8, dual-GPU, MTP) | ~64 tok/s decode, 1282 tok/s prefill, draft acceptance 0.73 | Qwen3.6-27B-MTP Q8_0 split across 3090+Ti, before crash; ~40 s/doc end-to-end |
| 2026-07-05 | Slot-3 Bus Fatal MTBF, unlocked clocks | 4/4 crashes ≤7 min under bursty inference | steady memtest 30 min passes; reseat/ASPM/dual-PSU/P2P eliminated; link pristine to last second (flight recorder) |
| 2026-07-05 | Locked-clock stability (3090 @1395 MHz) | 15/15 requests, ~13 min, 0 PCIe events | solo Q6_K bench, 51.8 s/req; identical verdicts ×15 (temp-0 determinism); fix persisted via gpu-powerlimit.service |
| 2026-07-05 | Judge calibration (dense 27B, rubric-r2) | PASS: keep/drop 93.1%, ±1 97.7%, dangerous 0 | 87 community docs vs adjudicated 3-rater labels; bars pre-registered; any-chunk≥4 keep metric ruled blind |
| 2026-07-05 | Full community tier judged | 116 docs / 152+ chunks overnight, 0 crashes | locked clocks, ~40-90 s/doc, 3 JSON re-asks total at 6144+ budget; 1 doc honest-failed (table-dense rumination) |
| 2026-07-08 | CORPUS JUDGING COMPLETE (rubric-r2) | 5,691 docs / 5,796 chunks; keep≥4 = 3,790 | both tiers 100% judged; 2 honest-fails; score histogram 12/865/1,129/2,755/1,035 |
| 2026-07-08 | Final training-pair harvest (r2) | 82 pairs kept (61 subaru_ej) | from 23 docs; vs 500–1,000 pilot target → pair-synthesis bridge required (ROADMAP Phase D) |
| 2026-07-08 | 3090 crashes #10/#11 (Slot 7 Bus Fatal) | died in plain decode @ locked 1005 MHz, ~230 W, <65 °C, 0 AER | 1000-MHz derate stopped holding after ~2 days; config drift + workload shape ruled out; 0 data loss (doc-atomic runner + snapshot) |
| 2026-07-08 | Stability bracket (split 3.5:1 + 800 MHz) | 56 docs / ~95 min / 0 crashes @ ~54 t/s | 3090 @ ~152 W (15 layers), Ti ~296 W (49 layers); threshold bracketed 152 W < fail < 230 W — power-delivery signature for the teardown |

*Add rows as benchmarks/evals/training runs produce numbers — GPU thermals, inference
throughput/latency, fine-tune eval scores, corpus size/quality, tuning-loop convergence.*
| 2026-07-09 | E1 arm A (base 27B, no RAG) | 84.3% top1 / 98.6% acceptable | 70 sim cases ×2 runs, 70/70 deterministic; vs rules 85.7/100 — fails pre-registered floor by 1 case |
| 2026-07-09 | E1 arm B (base + BM25 RAG) | 74.3% top1 / 88.6% acceptable | RAG −10 pts on closed reasoning; vacuum_leak 100→50% — snippets distract two-point logic |
| 2026-07-09 | Pairgen source probe | wiki defs: 0 pairs/19 docs; manual text: 1.8 pairs/doc | supply ceiling ≈4.5k pairs from 2,536 book docs — filtering problem, not supply |
| 2026-07-10 | E2 arm A (base, 69 probes) | 14.5% match / 14.5% dangerous / 71% decline | HARD GATE FAIL; tol ±1%, temp 0 |
| 2026-07-10 | E2 arm B (base+RAG) | 34.8% match / 15.9% dangerous / 49% decline | 2.4× recall vs A; GATE FAIL; 5 retrieval-induced fabrications (right doc, wrong number) |
| 2026-07-10 | E1v2 baselines (147 cases, voltage sweep) | rules 85.7/85.7, rules_v2 100/100, random 12.9 | degeneracy broken with complete info; Syed bar 90/100 pre-registered |
| 2026-07-15 | E1v2 arm A (base, 147 cases) | 83.7% top1, latency-fault 14% | two-point reasoning persists; 147/147 deterministic ×2 |
| 2026-07-15 | E1v2 arm B (base+RAG) | 89.8% top1, latency-fault 57% | FAILS 90% bar by 1 case; retrieval supplies voltage physics (+6.1 vs A — reversal of v1) |
| 2026-07-16 | Pilot mix v1 assembled | 400 pairs (82 organic + 318 synthetic) | 841 drafts -> filters/dedup; ve_load 64, injectors 46, idle 25, maf 18; Subaru 21% vs 70% target (flagged) |
| 2026-07-16 | Classifier verdicts on 841 drafts | 37% shallow, 12% legacy-tech | hardened standard executed as code; deep survivors 146+ |
| 2026-07-16 | C3 remediation: off_field re-screen | 231/501 (46%) convicted off-field | Syed's 3-of-20 sample catches generalized; classifier now enforces "actionable via ROM editor" |
| 2026-07-16 | Community batch 4 (28 keep-threads) | 36 pairs: 20 subaru, 25 deep | best quality-density of any batch; gone-marked threads mined |
| 2026-07-16 | Pilot mix v2 | 330 pairs (82 organic + 248 synthetic), Subaru 27% | pool honestly exhausted below 400 cap; fresh sample staged |
| 2026-07-23 | QLoRA pilot training (arm C adapter) | 91 min, 90 steps, train 2.06→1.34, val best 1.772@ep1 | Qwen3.6-27B NF4 r=16 on Ti only; holdout caught epoch-2+ overfit; epoch-1 ckpt served |
| 2026-07-23 | Retrieval-v2 index build | 5,608 chunks × 1024-dim, 23MB, 2.2h CPU | BGE-M3, L2-normalized, RRF-fused with BM25 behind unchanged retrieve() seam |
| 2026-07-23 | E1v2 arm C (fine-tune) | 83.7% top1, 2 dangerous flips | FAILS bar (accuracy + veto); first dangerous misses of any arm; ×2 deterministic |
| 2026-07-23 | E2 arm C (fine-tune) | 21.7% match / 65.2% dangerous / 11.6% decline | GATE FAIL; fine-tune collapsed declines 71%→12% — register without knowledge |
| 2026-07-24 | E1v2 arm D (ft + hybrid@6) | 78.2% top1, 0 dangerous | retrieval distracts diagnosis but eliminated C's flips; ×2 deterministic |
| 2026-07-24 | E2 arm D (ft + hybrid@6) | 42.0% match / 21.7% dangerous / 34.8% decline | best exact-match of any arm; GATE FAIL; fabrications 45→15 vs C |
| 2026-07-24 | E1v2 arm B-v2 (base + hybrid@3) | **93.9% top1, 0 dangerous — FIRST BAR PASS** | hybrid ranking beats bm25's 89.8; @6 variant 83.7 (distraction confirmed dose-dependent) |
| 2026-07-24 | E2 arm B-v2 (base + hybrid@6) | 36.2% match / 2.9% dangerous / 60.9% decline | GATE FAIL by 2 (closest ever); cite-or-decline rider cut base fabrications 11→2 |
| 2026-07-25 | Scorer v1.1 re-score (all 12 E2 files) | B-v2@6 2→1 dang; C 45→44; D@6 15→14; B-v1 11→9 | leading-dot + spaced-thousands parse bugs (retro-test catch); no gate verdicts flipped |
| 2026-07-25 | Citation-guard retro-test | 13/13 absent-number fabrications blocked; 0/26 false blocks | evidence-only, deterministic; 1 known would-leak class (cited-but-wrong-selection) |
| 2026-07-25 | E2 arm B-v3 (hybrid@6 + guard) | 37.7% match / 1.4% dangerous / 60.9% decline | GATE FAIL by ONE (e2-5723-1: right doc, right physics, 11 vs 11.8 rounding); attempted 1/blocked 0/leaked 1; ×2 identical |
| 2026-08-02 | E1v2 gpt-oss arm A @16k budget (corrected) | 86.4% top-1, 0 dangerous, 4 blanks | truncation fix +5.4pp vs 8k run; timeout 1800s; closes the showdown matrix |
| 2026-08-02 | Bench audit (2 agents) | 18 code findings + 57/69 probes flagged + 9 validation gaps | scorer [REF] parse, snippet truncation class, probe traps; ALL E2 verdicts asterisked pending Phase-1 fixes |
| 2026-08-05 | Deterministic estimator (no LLM, no GPU) | 138 correct / 2 safe refusals / **0 confidently wrong** of 140 | 7 faults x 20 seeds through the real log->bin path with sensor noise |
| 2026-08-05 | Estimator vs the 8 real E4 masking events | **8/8 prevented** | per-iteration, on the diagnosis that caused each edit; exact to first divergence |
| 2026-08-05 | E4 re-run, 27B dense (ratified bars) | diagnosis 100% · masking 0 · clamps 0 · convergence 13/15 | **all four bars PASS** (was 88.9% / 2 / 0 / 15-15) |
| 2026-08-05 | E4 re-run, gpt-oss-120b | diagnosis 77.8% · masking 0 · clamps 0 · convergence 11/15 | safety bars pass, capability bars fail |
| 2026-08-05 | Collateral belief corruption (both models) | 9 episodes -> **0** | metric added because `masking` keys on the majority diagnosis and under-counted |
| 2026-08-05 | Defence-layer attribution | 27B: 52 stability / 0 gate · gpt-oss: 54 stability / **8 gate** | the two layers catch different failure modes; neither alone sufficed for gpt-oss |
| 2026-08-05 | Citation-guard context check (REJECTED) | 0/21 caught, 6/410 false blocks | reverted, not tuned; blind spot is a consequence of the evidence-only contract |
| 2026-08-03 | E2-v2 final matrix (k6+guard, 5 models) | 27B 47/2 · gpt-oss 48/0 · 35B 47/3 · 80B 43/1 · Mistral 34/2 | probes v2 + scorer v2 + fixed snippets, MTP-off, 16384 tok / 24576 ctx; only gpt-oss gate-clean |
| 2026-08-03 | E2 closed-book (arm A), all 5 models | 7-10 exact of 69; 3-14 CONFIDENT fabrications each | H3 confirmed: no model carries Subaru calibration constants in weights |
| 2026-08-03 | top_k 6 vs 3 (H4, new) | k6 > k3 in 5/5 models: 47>40, 48>42, 47>41, 43>39, 34>29 | coverage rises AND precision holds — the two normally trade |
| 2026-08-03 | 27B E2 gate, old vs fixed instrumentation | 19ex/0dg @27.5% cov (PASS) -> 47ex/2dg @72.5% cov (FAIL) | the old PASS was an artifact of evidence starved by our own snippet bug |
| 2026-08-03 | E1v2 armB@3 re-verify, finalists | 27B 93.2 -> 92.5 (in noise) · gpt-oss 83.7 -> 78.9 (outside) | snippet fix hit VALUE LOOKUP only, not diagnosis; better evidence made gpt-oss worse |
| 2026-08-03 | Verdict vs pre-registered bars | NO model passes both (E1 90%+0dang, E2 0 fabrications) | finalists fail in opposite directions; E4 is the tiebreaker |
| 2026-08-02 | Snippet extraction v2 (evidence recall) | 29/69 → 59/69 expected values in-window | own-source doc, 1200-char cap, zero regressions; old = FTS5 24-token snippet |
| 2026-08-02 | Scorer v2 re-score (all 28 E2 files) | exact 558→577; dangerous 265→201 | [REF]-strip + intervals + unit/range classes + infix-minus fix; stricter in 2 rows; both gate-PASS cells still 0 dangerous |
| 2026-08-02 | Probe file v2 audit-vs-source | 0/69 values absent from source; 1 question fixed, 0 dropped | 3 audit claims refuted; hard gate NOT softened; 18/69 quote diffs all PDF artifacts |
| 2026-08-02 | E4 fake-LLM dry run | 7/7 checks; oracle residual 3.8% vs wrong-knob 9.3% | scoring falsifiable — masking provably fires on a deliberately wrong model; sim-calibrated-pending |
| 2026-08-02 | Eval test suite | 54 → 121 tests green | every Phase-1 fix landed with a regression test from the observed failure |
| 2026-08-08 | SSM2 live logging (real car, first contact) | WORKING — RPM, ECT, battery V streaming | RomRaider via Washinglee OP2 clone, 32-bit JRE `-cp` launcher; ECU ID `3B12504206` |
| 2026-08-08 | ECU ROM read (EcuFlash, sti05) | BLOCKED at seed/key — unlock refused, nothing written | identical on 1.44.4347/1.44.4870, DLL 1.01/1.02, sti04/sti05; H1 locked ECU vs H2 clone K-line |
| 2026-08-08 | AEM 30-0300 wideband serial → PC | BLOCKED — COM5 opens, zero bytes | wiring continuity-verified end-to-end; USB-serial chipset unidentified = prime suspect |
| 2026-08-11 | AEM wideband serial link | **SOLVED** — 301 bytes, ~50 samples in 5 s | gauge's native ~10 Hz, AEM ASCII decoding at 9600 8N1; root cause = hand-crimped DB9 shell on the wrong pin |
| 2026-08-11 | Wideband fault-elimination chain | 5 hypotheses killed by measurement, incl. all 3 pre-registered | genuine FTDI · −5.74 V on pin 3 · loopback echo · reboot · bypass; every original suspect was wrong |
| 2026-08-11 | ECU logging with both cables connected | **FAILS** — hangs at `sending ecu init`, no exception | ground loop: Openport (OBD pin 4/5) + AEM gauge ground bridged via laptop USB, heater 1–2 A in the loop |
| 2026-08-11 | ECU logging, serial adapter unplugged | **WORKS** — isolation test decisive | fix = break the loop (signal-only wire, or ADuM3160-class USB isolator), NOT relocating the ground |
| 2026-08-11 | Ground-loop fix applied (drop DB9 pin 5) | **BOTH streams live** — AFR matches gauge | signal-wire-only; return path via chassis + Openport OBD ground; zero cost |
| 2026-08-11 | ECU ID `3B12504206` identity | **CONFIRMED correct part** — 05/USDM/FXT/AT/SH7058/sti05 | 332 defs entries parsed; family gap is 1 uncontributed AT revision, MT twin `3B12584206` present |
| 2026-08-11 | ROM read retry (charger on, no ground loop) | STILL BLOCKED at seed/key — **but ECU returns a seed** | vendor DLL 1.01.4341, firmware 1.17.4877 unchanged; failure is at KEY validation, weakening the clone-cable hypothesis |
| 2026-08-12 | First real log: parser on live-car export | **13/13 canonical roles mapped** | real RomRaider v370 headers, unmodified parser; first non-synthetic data in the project |
| 2026-08-12 | SSM2 sample rate, 21 params (measured) | **14.49 Hz** (model predicted 4.7) | continuous-read mode; model was 3x pessimistic, replaced by measurement |
| 2026-08-12 | Steady-state quality vs GridSpec | **0.00% of samples transient** | \|d rpm\| mean 8.7/max 79 vs tol 100; \|d tps\| max 0.39 vs tol 2.0 |
| 2026-08-12 | `wideband_afr` in first log | **DEAD — 1 distinct value (0.00) across 1878 rows** | factory A/F sensor 12.40-15.16 mean 14.53, so engine fine; AEM plugin at fault. BLOCKS capture |
| 2026-08-12 | Idle fuel trim (corr+learn), closed loop | **+0.31% mean** | idle fuelling essentially correct; provisional until wideband validates the factory sensor |
| 2026-08-12 | Idle speed stability | 640-770 rpm, std 17.6 | the presenting complaint, quantified for the first time |
| 2026-08-13 | Wideband live in-file (AEM plugin fixed) | **real data, 14.40-14.90 AFR** | was a column of zeros on 2026-08-12; capture protocol's ground-truth instrument now works |
| 2026-08-13 | AEM vs factory A/F sensor agreement | **-0.02 AFR mean diff, std 0.08 (n=1351)** | two independent instruments cross-validate; both trustworthy at idle/stoich |
| 2026-08-13 | Post-reset cold high-idle shakedown | 1337 rpm mean, coolant 100-135F, 0 knock | healthy warm-up; NOT a protocol warm-idle hold (learning wiped, cold) |
