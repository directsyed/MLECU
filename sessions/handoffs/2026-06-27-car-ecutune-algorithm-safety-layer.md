# 2026-06-27 - car/ecutune: deterministic algorithm + safety layer (Track A)

**Context:** Syed asked for next objectives given current constraints. He chose **Track A** (build the
deterministic algorithm + safety layer, *build-priority*, Claude builds + explains) and **Track B**
(the LLM-judge design, *learning-priority*, co-design, NOT yet started). This session delivered
Track A in full, offline (no car, no GPU needed). Plan file:
`~/.claude/plans/read-the-claude-md-context-optimized-falcon.md`.

## What changed (delta)
- **New package `car/ecutune/`**: own `.venv` (numpy + hypothesis), mirrors `corpus_pipeline`
  conventions, zero runtime coupling. CLI: `python -m ecutune.cli {--status,--run-convergence [--seed N]}`.
- **`safety/`**: 7 ordered pure-function clamps + `apply_proposal()` as the single Table write path
  + a source-scan meta-test. **The project's hard constraint is now testable code, not prose.**
- **`logparse/`**: RomRaider/SSM2 CSV parser (tolerant header→role map) + airflow×rpm binning
  (steady-state gate, trim-error = AF Correction + AF Learning).
- **`algorithms/`**: bounded-integral / damped-PI controller (±3% clamp = anti-windup) + idle
  global-scalar corrector (latency→flow→MAF; emits a `Proposal`, never self-applies).
- **`simulation/`**: MVEM + convergence harness (the keystone).
- **Offline proof:** seeded idle trim **+14.8% → 3.86% in 4 iters, 0 clamp violations, deterministic**,
  all seeds. **31 tests green.**
- Updated `PROGRESS.md` (+4 perf rows), `decisions.md` (design choices), and the four `car/` README
  stubs (flipped from "not started" → built). Committed to `main`.

## Key decisions (full reasoning in decisions.md 2026-06-27)
- AFR-floor clamp runs **last** (final hard word on boost AFR; may richen past the rate-limit, rich is safe).
- Idle scalars degenerate at one operating point → the loop converges **trim**, not each scalar exactly; fixed split weights (latency 0.2 / flow 0.7 / MAF 0.1).
- Controller gains kp0.5 / ki0.05 / damping0.7; the ±3% safety clamp is also the anti-windup.
- MVEM = mean-value, steady-state, idle-fuel only; knock is a scripted test state.

## Open: confirm with Syed (flagged in code as assumptions)
- Seeded mismatch magnitudes (flow 850/820, latency 0.95/1.0, MAF 0.98/1.0) → set from the **real swap**.
- stoich 14.7 / AFR floor 11.5; trim = AF Correction + AF Learning; default fuel-table axis (MAF g/s vs g/rev load) + the exact wideband channel header; per-row timing ceilings in `config.yaml` are **placeholders**.

## Next
- **Track B, LLM-judge design (learning thread, NOT started).** Co-design the 1–5 rubric +
  reference-tier grounding/retrieval + `(symptoms→diagnosis→change→outcome)` extraction schema, then
  scaffold the `State.pending_for_judge()` → `mark_judged()` plumbing with a stub scorer. The judge
  *run* stays deferred to the 48 GB (2×3090) setup. Input contract already exists; 926 docs pending.
- **car Stage-3 boost PID** + **real-log replay** remain (wideband-gated). `synth_log` already emits
  the real `LogTable` shape, so real RomRaider logs drop into the same path.
