# infrastructure/monitoring/

GPU/host health + thermal capture.

**Status:** baseline only — `nvidia-smi` shows the 3090 idle at 37 °C. No sustained-load capture yet.

## Mem-junction temperature on Linux (the repad-decision blocker — RESOLVED)

`nvidia-smi`/NVML **do not expose GDDR6X junction temp on GeForce cards** (`temperature.memory` = N/A; NVIDIA dev-forum request open for years). Read it instead with a **direct BAR0 register reader**:

- **Tool:** [`ThomasBaruzier/gddr6-core-junction-vram-temps`](https://github.com/ThomasBaruzier/gddr6-core-junction-vram-temps) (`gputemps`) — reads **core + junction + VRAM**, RTX 3090 (GA102) tested, `--json` JSONL output for logging. Build: `gcc gputemps.c -o gputemps -O3 -lnvidia-ml -lpci` (`libpci-dev` + NVML header; Docker fallback).
- **Requirement:** kernel boot param `iomem=relaxed` (GRUB edit + reboot). Secure Boot N/A here (legacy/BIOS boot).
- Reads registers directly (not via the driver / VRAM contents) → safe to poll *during* memtest_vulkan without the Windows GPU-Z-on-OCCT false-error problem.

## Soak plan (settles the OEM-3090 repad question)

- **Primary: memtest_vulkan** — hammers the GDDR6X junction hardest *and* is the same tool that gave the 106 °C reading in the Omen → apples-to-apples in the T630. Prebuilt binary.
- **Secondary: gpu-burn** — CUDA power-virus; highest total board power, best proxy for real ML load + whole-cooling-system stress (needs `nvcc`). Run tests one at a time.
- **Run with `gpu-fan-control` active** — one soak validates the fan curve *and* yields the repad number. **Abort if** junction ~110 °C, thermal throttle, or any memtest error.

## Monitoring stack (poll together)
- `nvidia-smi` → core / power / clocks / **throttle reasons** (`-q -d PERFORMANCE`)
- `gputemps` → junction / VRAM
- `ipmitool sdr type fan` → chassis fan RPM (confirms the curve ramps)
- **Will contain:** a unified CSV logger over these three + the captured soak logs; record the steady-state max junction temp into `../../PROGRESS.md`.

This is a **learning-priority** area (fan-curve calibration, thermal characterization) — teach, don't auto-complete.
