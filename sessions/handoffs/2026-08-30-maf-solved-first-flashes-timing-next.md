# Handoff: 2026-08-30: the car has been flashed three times, fuel is solved, timing is next

**DELTA since `2026-08-17-extended-params-and-drive-prep.md`.** 32 commits. Read that file for
the state this one departs from. **60 commits are unpushed**: Syed pushes when satisfied.

The headline: the project crossed from *building a pipeline* to *the pipeline having tuned the
car*. Three ROM writes, all verified byte-exact. Fuel error went from ~+30% to under 3%.

---

## 1. What the car's problem turned out to be

**The MAF transfer curve under-reports airflow, progressively above ~10 g/s, peaking around +32%.**

Established from six vacuum drives: `corr(trim, airflow) = +0.854` against load +0.708 and rpm
+0.737, and the decisive test, hold MAF fixed and swing load/rpm hard, trim moves 0.3–5.0 pp;
hold load fixed and swing MAF, trim moves 3.1–15.3 pp.

**This killed a framing the project had carried for weeks.** There is no VE table on this
platform. Subaru's 32-bit ECU is MAF-based, and `core/tables.py` had already annotated
`sensor.maf_transfer` as *"(speed-density: absent)"*. A 1-D curve correction replaced a planned
2-D map rewrite.

**One fault, three symptoms.** Load is derived from airflow, so the under-read also made the ECU
index the ignition map at too light a cell (the only explanation for knock at *stoichiometric*
AFR) and never cross the load threshold for open-loop enrichment.

**Still unresolved, and it matters:** we cannot tell a wrong calibration from **unmetered air in
Syed's custom MAF→turbo tubing**. The correction compensates identically either way. A fuel
delivery fault that scales with demand is also not excluded, duty is proportional to airflow, so
the flow-dependent shape cannot separate them. **The smoke test and a fuel-pressure gauge remain
the only discriminators, and both are still outstanding** (Syed's gauge is at his shop).
Contamination *is* ruled out, he cleaned the element and the curve did not move.

---

## 2. What was built

| piece | where | note |
|---|---|---|
| MAF transfer stage | `ecutune/algorithms/maf_transfer.py` | first stage to tune a **curve**; no integral term (48 independent bins, no degeneracy); never extrapolates; 2% deadband |
| Sensor-calibration clamp | `safety/clamps.py::clamp_sensor_calibration` | new `targets_kind="sensor"` category bounding **evidence + displacement + monotonicity** instead of velocity, disjoint from the fuel clamps and property-tested to leave them byte-identical |
| **`romwrite`** | `safety/romwrite/` | the safety-critical build: encoder (uses the def's own `frexpr`, round-trips or refuses), patcher, 4-stage verification, change report |
| **SH7058 checksum** | `safety/romwrite/checksum.py` | **derived, not found**: ROADMAP E.4(c) had it open, repo had zero content |
| `--tune-maf`, `--verify-flash` | `ecutune/cli.py` | whole pipeline in one command; 11-check GO/NO-GO pre-flash audit |
| E5 real-log LLM bridge | `ml/eval/harness/e5_real_logs.py` | first non-synthetic LLM run in the project |

**Checksum specifics** (needed by any future writer): block at file offset `0xFFB80` on 1 MB ROMs,
12-byte big-endian records `{start, end_inclusive, stored}` satisfying
`(Σ BE-uint32 over [start,end] + stored) mod 2**32 == 0x5AA5A55A`. Our ROM has exactly one active
record, `0x2000..0xFFAF7`. The block sits outside every region it covers, so repair is a one-pass
fixed point. **Claimed for our family only**: foreign ROMs do not parse there and
`read_records` raises rather than guessing.

---

## 3. The three flashes

| | candidate sha256 | result |
|---|---|---|
| iteration 1 (08-29) | `9d33d08b7d4e604b…` | read-back **byte-identical** |
| iteration 2 (08-30) | `01fc6905c2004593…` | read-back **byte-identical** |
| iteration 3 (08-30) | `3e64b627d0f532f8…` | read-back **byte-identical** |

74 bytes now differ from stock. Cumulative MAF correction **+35.2%** at peak against the ratified
40% envelope. Archived in `car/ecu/rom read/` with `SHA256SUMS.txt`.

**Tooling facts a successor must not relitigate:**
- **FastECU only.** EcuFlash's SecurityAccess key is rejected on this ECU **even with the green
  connectors joined**, retested 2026-08-29, log captured in `ecu/ROM-READ-BLOCKER.md`. Not a
  guess any more.
- **Never use FastECU's "test write."** Read from source: the erase is sent *unconditionally*;
  only the final commit is swapped for a validate. It erases a page and leaves it unprogrammed.
  decisions.md **D28**.
- Writes are block-by-block with unmodified blocks skipped, so a stock→stock "rehearsal" flash
  would write nothing and prove nothing.
- The green test-mode connectors are required for the ECU to accept a write.

**Result: fuel is solved.** Every airflow band within ±3% (was ~+30%).

---

## 4. Where the car is now, and why timing is next

**IAM collapsed from 0.500 to 0.000 for 52 seconds while running** on the 2026-08-30 drive
(`drive-20260830-02-postflash3-timing.csv`), recovering only to 0.125. The ECU has withdrawn all
dynamic advance, its strongest protective response.

`Base Timing` commands **38–42° BTDC at 0.7–1.0 g/rev**, where this car makes boost. The map was
written for an 8.4:1 EJ255 where 0.85 g/rev is ~59% of NA max; on the 9.5:1 EJ20X the same cell is
~73%. Two factors compounding, `car/CLAUDE.md`'s candidate #4, reached by elimination.

**Two findings that redirect the obvious fixes:**
- `Primary Open Loop Fueling` commands **14.7 stoich across every cell below 1.15 g/rev**. So
  lowering the CL→OL threshold or zeroing the CL→OL delay (the common community advice, corpus
  doc 944) would change *when*, not *what*. The enrichment lever is the OL fuel map itself.
- The CL→OL trigger is **86.03% throttle plate** or 6–7 ms base pulse width. Max plate reached is
  49.8%, confirmed on the correct DBW channel. Enrichment is not broken; it has never been asked
  for. Partial-throttle boost in closed loop is factory intent.

---

## 5. A prediction of mine that failed

decisions.md **D30** argued that correcting the MAF would retard boost timing 4–11° by fixing the
load lookup, and that knock would fall. **It did not:**

| drive | onsets | worst | max boost |
|---|---|---|---|
| pre-flash | 8 | −5.00° | +1.60 psi |
| after iter 1 | 21 | −5.02° | +6.24 psi |
| after iter 2 | 18 | −6.49° | +5.66 psi |
| after iter 3 | 23 | −7.00° | +6.53 psi |

The arithmetic was right; it was evidently swamped by Syed driving progressively harder as the car
got safer. Boost rose across the set, so it is confounded, but there is no sign of the predicted
improvement and IAM has since gone to zero. **Do not treat D30's mechanism as established.**

---

## 6. Decisions ratified this session (decisions.md D21–D30)

- **D21**: the "no boost before the smoke test" rule was **circular** (the shop is a highway
  drive away) and is withdrawn. Base tune first. *Syed's correction; do not re-impose it.*
- **D26**: `boost_load_threshold` 1.5 → **0.60 g/rev**. It is a *classifier* deciding which cells
  `clamp_afr_floor` checks, not a boost limit. At 1.5 it protected nothing: this car crosses
  atmospheric at ~0.6 and all 31 knock events sat at 0.58–0.79.
- **D29**: load-aware timing ceilings (**45 / 30 / 22°** by load), cumulative `sensor_envelope`
  (0.40) against the archived stock ROM, and `belief_envelope` moved into `config.yaml`.
- **Timing stage** (2026-08-30): hybrid evidence+ceiling basis; apply the ceiling to undriven
  cells; **6° per iteration** rate cap.

---

## 7. Bugs found and fixed (worth knowing, several were latent for weeks)

- `clamps._sign()` computed `(x>0)-(x<0)`, which raises `TypeError` on a numpy scalar. Any
  array-derived proposal would have crashed `clamp_ve_rate_limit`. Never hit because only the sim
  had produced proposals.
- **Four silent schema collisions.** RomRaider's column order is *not stable between sessions*,
  the AEM wideband was column 10 in one log and column 25 in the next, and the parser resolved
  duplicate role claims by first-column-wins. `Final Fueling Base (lambda)` and `Closed Loop
  Fueling Target (lambda)` both hijacked `wideband_afr`; `A/F Learning Airflow Range` (an *index*)
  collided with `A/F Learning` (a *percentage*). Now detected (`LogTable.collisions`) and resolved
  by an explicit `schema.prefer()` table.
- `clamp_sensor_calibration` guaranteed a strictly ascending curve using a 1e-9 separation.
  float32 has ~1.2e-7 relative precision, so **the guarantee died at the storage boundary** and
  the flashed curve would have had flat spots. Caught by the write path's own read-back.
  *An in-memory guarantee that does not survive encoding is not a guarantee.*
- `patch_logger_def.py` silently rewrote all 40,404 lines of the v370 def CRLF→LF, and the
  "exactly 57 lines changed" validation had been measured *after* normalising line endings.

---

## 8. The E5 LLM trial (first real-log run in the project)

Qwen3.6-27B, blind, 2 arms × 2 input treatments. **1 of 4.** Only raw-rows + open-ended reached
the MAF curve. The three failures chose `injector_flow_lean`, which the data refutes (a constant
error cannot produce +0.6% at low flow and +30% at high). One losing arm *saw* the idle
contradiction and rationalised it away, then dismissed MAF on a generic prior, at 85–90% confidence.

**Headline: input format flipped the diagnosis.** Same model, same temperature, same data,
pre-digested summary tables wrong, raw rows right. n=1 per cell, so suggestive not established.
Full review: `ml/eval/results/RUNDOWN-2026-08-27-e5-real-logs.md`.

Note the safety architecture would have caught the failures unaided: three of four name
`fuel.injector_flow` while `identify()` names `sensor.maf_transfer`, so
`clamp_diagnosis_agreement` aborts.

---

## 9. NEXT: the timing stage

**The full plan is committed at `docs/PLAN-timing-stage-2026-08-30.md`. Read it first.**

It carries the ratified decisions and, critically, **five blockers that must be fixed before any
timing code runs**, including two of mine:

1. **The load ceilings Syed ratified never fire.** The ROM stores the axis as float32, so
   `0.55` reads back as `0.5499999523` and `load >= 0.55` is False. Both bands start one column
   late. Needs an epsilon and a test pinned to the ROM's real breakpoints.
2. **`clamp_knock_auto_abort` is inert in production.** `ctx.knock_active` is never set outside
   tests. Same for `fuel_trims_converged` (so **any** timing proposal is currently deferred) and
   `steady_state_ok`.
3. `report.py:50` map-2D index bug, crashes on the first edit with `row >= 1`.
4. Timing has no rate limit and no cumulative envelope (both gate on `targets_kind`).
5. `_verify_flash` is hardcoded to the MAF curve.

### Syed's open physical items
- **Smoke test**: the only thing that separates a wrong MAF calibration from an intake leak.
- **Fuel pressure test**: the one hypothesis never tested at all.
- Off-machine third copy of the stock ROM.
- Keep out of sustained boost until timing is addressed.

### Working rules earned this session
- `pkill -f` matches your own shell, kill by PID. (Hit again this session.)
- Every parameter list to Syed must be **alphabetical**; priority goes in a column.
- ~24 SSM2 parameters is the practical logging ceiling on this ECU.
- Run approved plans end-to-end; stop only for decisions, not status reports.
