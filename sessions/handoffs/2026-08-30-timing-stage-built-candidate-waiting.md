# Handoff — 2026-08-30 (later): the timing stage is built, and iteration 1 is waiting for review

**DELTA since `2026-08-30-maf-solved-first-flashes-timing-next.md`.** Read that first; this one
only covers what changed. The plan it pointed at (`docs/PLAN-timing-stage-2026-08-30.md`) has
been executed end to end and now carries a STATUS banner listing the divergences.

**Nothing has been flashed this session.** The deliverable is a candidate file + change report.

---

## 1. What Syed needs to decide

**A. Review and flash (or not) `car/ecu/rom write/CANDIDATE_timing_iter1_2026-08-30.bin`.**
Change report beside it. Audited **GO**. 184 of 270 Base Timing cells retarded, 188 bytes in 15
ranges plus the checksum record, worst advance introduced **+0.0000 deg**. Same flash discipline
as the three MAF writes: **FastECU only**, green connectors joined, never the "test write" (D28).

**B. Ratify or change two numbers I set** (both in `car/config.yaml`, both commented in place):

| number | value | how I got it |
|---|---|---|
| `max_timing_retard` | 20.0 deg | derived — the ratified ceilings themselves demand at most 18.117 deg, so below ~18.2 it would fight them; 20.0 leaves ~1.9 deg of evidence headroom |
| `min_timing_advance` | 0.0 deg BTDC | a backstop, not a tuning limit; the stock map's own minimum is 2.148 deg |

**C. Know that this takes 3 passes, not 1.** 156 cells are still above their ceiling after
iteration 1, worst by 11.79 deg — **2 more drive/re-log/flash cycles** at the ratified 6 deg per
iteration. That is the cost of your rate-limit ruling and it is working as intended (D31).

---

## 2. The five blockers, closed

Each has a regression test that I **verified fails when the original bug is put back** — a pin,
not a claim.

| # | was | now |
|---|---|---|
| 1 | load ceilings never fired: ROM stores the axis as float32, so `0.55` is `0.5499999523` and `load >= 0.55` is **False at the ratified column** | `SafetyCfg._at_or_above` with a 1e-6 relative epsilon; test pins the ROM's *actual* breakpoints |
| 2 | `knock_active` / `fuel_trims_converged` / `steady_state_ok` never set outside tests | new `logparse/signals.py` measures all four from the log |
| 3 | `report.py` indexed a 2-D map `row * a.shape[0]` on a **raveled** array (270, not 15) | fixed + `patch()` now reads back **every** edited cell, any table kind |
| 4 | timing had **no** rate limit, cumulative bound or floor | `clamp_timing_rate_limit` (retard-only + cumulative floor + 6 deg step + absolute floor) |
| 5 | `_verify_flash` hardcoded to the MAF curve | `_FLASH_PROFILES` + `--expect maf\|timing` |

Blocker 1 was worse than the plan said: it silently mis-set **both** bands, including the boost
column at 0.85 g/rev.

---

## 3. Four things that came out differently from the plan (decisions.md D31–D34)

**D31 — the rate limit belongs AFTER the ceiling.** The plan said before. The ceiling is a
floor-to-a-value operation that drops the worst cell 18.12 deg in one move, so running it last
would have overridden the ratified 6 deg/iteration and left the rate cap decorative — the same
failure mode as blocker 1. Ceiling picks the destination; the rate limit paces the journey.

**D32 — two gates deadlocked the moment they were wired truthfully, and now carry a verified
exemption.** `clamp_knock_auto_abort` fires on every log that could justify a retard (this car
knocks — that is the point). `clamp_fuel_before_timing` stays shut because one airflow band
(**59.31 g/s, 29 samples**) still reads **+7.44%** — and closing it needs high-airflow data,
which needs boost, which is what the timing work exists to make safe. **That is D21's
circularity on a new axis.** Both gates now pass a proposal in which no cell ends up more
advanced than it currently is, checked against the live tables and **never against proposal
metadata** — the future LLM is a proposal producer, so a metadata flag would be a gate it could
open for itself. Fuel and sensor proposals get no exemption; the only way past for those is a
human typing `--ack-knock`, which prints loudly and lands in the change report.

**D33 — the ROM corrected two numbers I had guessed.** I first applied a flat 2.0 deg of lost
dynamic advance to every driven cell, from an assumed healthy IAM of 1.0. The ROM says:
`Advance Multiplier (Initial)` = **0.5**, so an observed IAM of 0.500 is the **factory value**,
not a halved one — *the 2026-08-26 analysis read it as damage, and that reading was wrong* (the
collapse to 0.000 is still entirely real). And IAM multiplies **`Knock Correction Advance Max`**
(0xC8FB0), an 18x16 map that is **0.00 across the whole idle and cruise region** and 3.16–9.14 deg
in boost. My constant was wrong in both directions at once: it pulled 2.11 deg out of the idle
band that `car/CLAUDE.md` records as validated *knock-free*, while under-correcting boost cells
needing up to 4.57. **The ROM already knew** — same lesson as the MAF arc.

**D34 — a property test found a hole reading the code did not.** The cumulative retard floor is
inert without a baseline and a ceiling only bounds from above, so with no baseline **nothing**
bounded retard: iterating the clamp walked a cell to **−49 deg BTDC**, past TDC. Added an
absolute `min_timing_advance` and made `--baseline-rom` **mandatory** for `--tune-timing`.
*A rate limit that bounds a single step does not bound a sequence* — worth asking of every
per-iteration bound in the layer.

---

## 4. Two more silent schema collisions (that makes five and six)

- `IAM (1-byte)** (multiplier)` matched **no rule at all**. The channel that recorded the ECU
  withdrawing all advance for 52 seconds was invisible to the layer.
- `Ignition Base Timing*` matched `\btiming\b` and landed on `timing_total` — the role meaning
  FINAL commanded advance. It lost to `Ignition Total Timing` only by column order.

Both now have their own roles (`iam`, `timing_base`). `tps` gained an explicit `prefer()` for the
**DBW plate angle** (max 49.8%, matching the previous handoff's figure) over the pedal channel;
`iam` prefers the 4-byte parameter. And `Knock Sum* (count)` — a cumulative counter, non-zero on
6425 of 7402 samples — is one of **three** headers claiming `knock_retard`; it loses only because
of the existing `prefer()` rule, now pinned by a test.

---

## 5. Numbers

| metric | value |
|---|---|
| cells above their ratified ceiling, stock map | 178 / 270, worst 18.117 deg at 2400 rpm / 0.85 g/rev |
| iteration 1 | 184 cells (23 evidence-driven, 161 ceiling-only), mean pull 3.92 deg, worst 6.33 deg |
| remaining after iteration 1 | 156 cells above ceiling, worst by 11.79 deg → 2 more passes |
| worst advance introduced by the write path | +0.0000 deg (retard-only, re-proved on the bytes) |
| knock onsets / worst, post-flash-3 drive | 23 / −7.00 deg (reproduces the published figure) |
| tests | **187 passed** (was 143); +6 hypothesis properties |
| MAF iteration 3 re-derived | **byte-identical** to the flashed ROM (`3e64b627d0f532f8…`) |

---

## 6. NEXT

1. **Syed reviews the change report**; ratifies or changes `max_timing_retard` /
   `min_timing_advance`; flashes iteration 1 if he agrees.
2. **Drive and re-log** with the same 24-parameter set (it carries `Ignition Base Timing`, `IAM`
   and the plate angle — keep it). Then `--tune-timing` again for iteration 2.
3. Watch whether **IAM recovers** off 0.000. That is the single clearest read on whether this
   worked, and it is a better signal than onset counts, which are confounded by how hard the car
   is driven (the D30 failure).
4. **Still outstanding, unchanged, and still the only discriminators:** the **smoke test** (a
   wrong MAF calibration vs unmetered air in the custom tubing) and a **fuel-pressure test**.
   Also still open: an off-machine third copy of the stock ROM.

### Not in scope, deliberately
`Primary Open Loop Fueling` (commands 14.7 stoich to 1.15 g/rev), boost/wastegate control, and
any further MAF iteration until high-airflow data exists — which is now also the only thing
blocking `clamp_fuel_before_timing` from closing honestly rather than by exemption.

### Working rules earned this session
- **A per-iteration bound is not a bound on a sequence.** Ask "and after N iterations?" of every
  one of them.
- **An exemption must be verified from state the proposer does not control.** Metadata is not a
  safety input; a human at a CLI is.
- **Check the ROM before configuring a constant.** Twice now the ROM held the number.
- Regression tests for a fixed bug are worth **re-breaking the code to confirm** they fail.
