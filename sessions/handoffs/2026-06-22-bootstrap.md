# Handoff: 2026-06-22. Bootstrap

**Type:** delta (first handoff, establishes the baseline).

## What happened this session
- Read the MLECU bootstrap package; ran the upfront interview with Syed; built and committed the repo.
- Verified live machine state on the T630 (`syedlab`): RTX 3090 up, driver 580.159.03 / CUDA 13.0, idle 37 °C.

## State now
- Repo at `~/Shared/Computing Projects/MLECU/`, pushed to a **private** GitHub remote (`directsyed/MLECU`).
- Structure: lean root `CLAUDE.md` + `infrastructure/` / `ml/` / `car/` domain `CLAUDE.md` files + stub
  READMEs; refined `context/` plus `context/bootstrap-source/` (verbatim origin); `PROGRESS.md`,
  `decisions.md`, `README.md`.
- Interview decisions + 9 divergences from the package architecture are logged in `decisions.md`.

## In progress
- Nothing executing, bootstrap is complete.

## Next (sequenced)
1. **Close out GPU/server bring-up**: *learning-priority, teach it:* ipmitool fan-curve calibration,
   then the **mem-junction-under-load** soak (gpu-burn + memtest_vulkan) to settle the OEM-3090 repad
   question. Record the under-load mem-junction temp into `PROGRESS.md`.
2. Build the **LLM-corpus data scraper** (`ml/data-pipeline/`), *build-priority, build then explain.*
3. Stand up the **LLM-judge curation engine** (`ml/curation/`), *learning-priority, teach it.*

## Watch-outs
- ipmitool manual fan mode disables auto-ramp, raise fan % before any GPU load.
- Confirm the installed PSUs are the 1100W pair before stressing the GPU.
- Car domain is dormant until a wideband is acquired, don't start logging work before then.
- Don't touch / import the external `Hardware Parser/` project.
