# Plan — the ignition timing stage

> **Committed copy of the working plan** (the live one lives outside the repo in
> `~/.claude/plans/`, which a fresh agent cannot see). Paired with
> `sessions/handoffs/2026-08-30-maf-solved-first-flashes-timing-next.md` — read the handoff
> first for context, then this for the work.

*Supersedes the MAF plan that previously occupied this file; that arc is complete (three flashes,
all byte-exact, fuel now within ±3% across every airflow band).*

## Context

The car has spent its entire knock-adaptation budget. On the 2026-08-30 drive **IAM collapsed
from 0.500 to 0.000 and stayed there for 52 seconds** while running (863–3065 rpm), recovering
only to 0.125 by the end. IAM 0 means the ECU has withdrawn *all* dynamic ignition advance — the
strongest protective response it has.

The cause is structural. `Base Timing` commands **38–42° BTDC at 0.7–1.0 g/rev**, where this car
makes boost. That map was written for an EJ255: 8.4:1 compression, and 0.85 g/rev is ~59% of its
NA maximum. On the EJ20X the same cell is ~73% of NA max at 9.5:1. Two factors compounding, both
pointing the same way — the exact candidate `car/CLAUDE.md` listed as #4 before any data existed.

Fuel is now excluded as a confound: three MAF iterations took the cruise region from ~+30% trim to
under 3%, so the load axis the timing map is indexed on is finally trustworthy.

**A prediction of mine failed and is not being quietly dropped.** decisions.md D30 argued that
correcting the MAF would retard boost timing 4–11° by fixing the load lookup, and that knock would
fall. Across four drives at comparable boost it did not (onsets 21→18→23, worst −5.02→−6.49→−7.00°),
and IAM has since gone to zero. The load-lookup effect is real arithmetic, but it was evidently
swamped by something else — most likely that Syed drove progressively harder as the car got safer.

## Decisions taken (Syed, 2026-08-30)

| Decision | Choice |
|---|---|
| Correction basis | **Hybrid** — evidence-driven where knock was observed, ratified ceiling as a backstop elsewhere |
| Undriven cells | **Apply the ceiling** — it is an octane/compression limit, not a data-derived number, and the drive to the shop is highway |
| Rate limit | **6° per iteration**, re-log between passes |

## Five blockers found during exploration — all must be fixed first

**1. The load ceilings Syed ratified never fire.** `config.yaml` says `load >= 0.55` and
`>= 0.85`, but the ROM stores the axis as float32: the breakpoints read back as `0.5499999523`
and `0.8499999642`. `config.py:100`'s `if load >= lc.load` is False at both. **Both bands
silently start one column late** — col 2 gets 45° instead of 30°, col 4 gets 30° instead of 22°.
Fix: compare with a small epsilon, and add a test that pins each ceiling against the ROM's actual
float32 breakpoints rather than the decimal literals.

**2. `clamp_knock_auto_abort` is inert in production.** `ctx.knock_active` is never set anywhere
in `ecutune/` — only in tests. The clamp its own docstring calls *"the single most important
clamp"* has never fired on real data. Same for `fuel_trims_converged` (so **any** timing proposal
is currently deferred outright) and `steady_state_ok`. `SafetyCfg.fuel_trim_converged_tol` exists
and is read by nobody. All three must be computed and passed by the CLI.

**3. `report.py:50` has a map-2D index bug that will crash on the first edit with `row >= 1`:**
`i = e.col if kind != "map_2d" else e.row * a.shape[0] + e.col` — but `a` was raveled, so
`a.shape[0]` is 270 (total elements), not `n_x = 15`. Must be `values.shape[1]`.

**4. Timing is bounded by exactly one clamp.** `ve_rate_limit`, `belief_envelope` and
`sensor_calibration` all gate on `targets_kind` being `"fuel"` or `"sensor"`. Timing therefore has
no rate limit, no cumulative envelope against stock, and no floor — retard is unbounded. Syed's
6°/iteration ruling closes the first; a cumulative envelope closes the second.

**5. `cli.py::_verify_flash` is hardcoded to the MAF curve** (`moved == [SENSOR_MAF_TRANSFER]`,
"strictly ascending", `max_sensor_recal`). A timing candidate gets NO-GO until it is parameterised.

Plus one encoder subtlety: Base Timing is uint8 at 0.3516°/step and `encode()` rounds to
**nearest**, so an approved value can land up to **+0.176° advanced** of what the clamp allowed.
Round toward retard for timing, or re-assert the ceiling post-encode.

## Work

### 1 — Fix the blockers (`config.py`, `clamps.py`, `report.py`, `cli.py`)
Epsilon-tolerant ceiling comparison; wire `knock_active` / `fuel_trims_converged` /
`steady_state_ok` from the binned grid in `_tune_maf` and the new timing path; fix the report
index; parameterise `_verify_flash` by semantic table with timing-appropriate checks.

### 2 — `clamp_timing_rate_limit` + timing envelope (`safety/clamps.py`)
New MODIFIER on `targets_kind == "timing"`, inserted before `clamp_timing_row_ceiling`. Bounds
|new − current| ≤ `safety.max_timing_step` (6.0°) and bounds cumulative distance from the archived
stock ROM via `ctx.baseline_tables`, mirroring `sensor_envelope`. Retard-only: reject any edit that
*advances* timing, since nothing in this stage should ever add advance.

### 3 — The stage (`algorithms/timing_retard.py`)
Pure proposer, same contract as `maf_transfer.py`. Bins the log against the timing map's **own**
breakpoints — `GridSpec(x_role="load", x_breaks=<map load axis>, y_role="rpm", y_breaks=<map rpm
axis>)`, which lines up 1:1 with `CellEdit(row=rpm, col=load)`. **`require_closed_loop=False`** —
the MAF stage sets it True, which is right for fuel trims but would discard exactly the open-loop
boost samples where timing matters.

Per cell: `evidence = feedback_knock + fine_learning_knock + IAM deficit`; proposed value =
`min(stock − evidence, ceiling)`. Cells with no data fall back to `min(stock, ceiling)` — the
backstop Syed approved. Emits `targets_kind="timing"`.

`BinnedGrid` carries `mean_knock` but not `timing_total` or `fine_knock_learn`; extend `bin_log`
to bin those two (both are already canonical roles).

### 4 — Wire, verify, report
New `--tune-timing` CLI path mirroring `--tune-maf`, including `--baseline-rom`. Read-back
verification must be explicit — `patch()` only checks curve ordering, and that is skipped for
`map_2d`.

## Verification

- `cd car && .venv/bin/python -m pytest tests/ -q` stays green (currently **143**).
- New tests: ceiling fires on the ROM's *actual* float32 breakpoints (blocker 1); rate limit holds
  for any input; retard-only rejection; cumulative envelope; map-2D round-trip through
  `patch()` → `read_semantic_tables` at a cell with `row >= 1` (blocker 3); `_verify_flash` GO on a
  timing candidate.
- Property tests extending `tests/properties/test_props_safety.py`: no surviving timing edit ever
  exceeds its cell's ceiling *after encoding*; idempotency.
- End-to-end on the real ROM + `drive-20260830-02-postflash3-timing.csv`: change report reproduces
  a hand-checked sample of cells; byte-diff touches only Base Timing + checksum.

## Explicitly not in scope

The Primary Open Loop Fueling map (commands 14.7 stoich to 1.15 g/rev — a separate, later change),
boost/wastegate control, and any further MAF iteration until new high-airflow data exists.
