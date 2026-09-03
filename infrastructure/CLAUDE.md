# infrastructure/: Compute + Server Domain

Loaded when working on the T630, GPUs, power, networking, monitoring, or storage.
Live hardware facts: `../context/hardware-state.md` (the most frequently-changing file, keep it current).

## Subdirs
- `server/`: T630 config: ipmitool fan control, BIOS, PERC H730→HBA, dual-CPU plan.
- `networking/`: WireGuard, Tailscale, netplan, DuckDNS, remote access.
- `monitoring/`: nvidia-smi logging, thermal capture, the mem-junction-under-load test.

## Current state (June 22, 2026, full detail in ../context/hardware-state.md)
- **Host:** Dell PowerEdge T630 `syedlab`, Ubuntu 24.04 (BIOS/legacy boot), static `10.0.0.200`, iDRAC8 `10.0.0.210`.
- **CPU:** 1× Xeon E5-2630 v3 (CPU2 socket empty). Dual-CPU plan: 2× E5-2660 v4 (105W, standard heatsink), **BIOS update off the v3 FIRST** (v4/Broadwell needs newer than BIOS 2.5.4).
- **GPU:** 1× **HP OEM RTX 3090** live in slot 3, driver 580.159.03 / CUDA 13.0, idle 37 °C. Zotac **3090 Ti still blocked** (power: needs 3× 8-pin ≈ 450W; clearance: SW RAID header fouls slot 3; slots 6/7 fit but need CPU2).
- **Power:** target 2× Dell **1100W** pair (verify installed); X7C1K interposer chain installed.
- **Storage:** **ZFS DEFERRED** (per Syed, not near-term). H730 → HBA mode is the path when stood up.

## Domain hard rules (from ../context/principles.md §3, §6)
- **PSU safety:** redundant PSUs do NOT add capacity (2×495W = 495W usable); never improvise dual-PSU to one GPU (needs an ADD2PSU sync board); **never force a card backplate against the SW RAID standup pins** (short risk); **multimeter every GPU power cable end before first connect.**
- **iDRAC:** 100% fans on an unrecognized card is expected, tame with `ipmitool raw` (manual mode disables auto-ramp → raise % before any load).
- **BIOS update with the known-good CPU installed before any CPU generation change.**
- No PCIe bifurcation (Dell firmware lock, irrelevant, each GPU gets its own x16). Never boot two machines from the same clone (IP collision on 10.0.0.200).

## Next thread (LEARNING-PRIORITY, teach, don't auto-complete; see root CLAUDE.md)
**Close out GPU/server bring-up:** (1) ipmitool **fan-curve calibration**; (2) **mem-junction-under-load** soak (gpu-burn + memtest_vulkan) to settle the OEM-3090 repad question. Walk Syed through each command; let him drive.
