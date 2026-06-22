# infrastructure/monitoring/

GPU/host health + thermal capture.

**Status:** baseline only — `nvidia-smi` shows the 3090 idle at 37 °C. No sustained-load capture yet.

**Will contain:** the `nvidia-smi` query-loop logger (`temperature.gpu,temperature.memory,clocks.sm,power.draw,utilization.gpu --format=csv -l 2`), the **mem-junction-under-load** test harness (gpu-burn + memtest_vulkan) that settles the OEM-3090 repad question, and the thermal logs themselves.

This is a **learning-priority** area (fan-curve calibration) — teach, don't auto-complete.
