# infrastructure/server/

T630 host configuration and operations.

**Status:** host up (`syedlab`, Ubuntu 24.04, BIOS 2.5.4, legacy/BIOS boot), 1× Xeon E5-2630 v3.

**Will contain:** ipmitool fan-control scripts, BIOS-update notes, the PERC H730→HBA procedure, the dual-CPU (2× E5-2660 v4) upgrade runbook (BIOS-first), iDRAC notes.

## Fan control — `gpu-fan-control.sh` (closed-loop, GPU + CPU)

The iDRAC can't see the RTX 3090, so in auto mode it maxes the chassis fans. `gpu-fan-control.sh` runs them in iDRAC **manual mode** off a temperature curve instead. Source of truth is here; install copies to `/usr/local/sbin/`.

**Chassis fans:** 2 active (Fan1/Fan2); the other 4 sensor slots are unpopulated/Disabled (no alarm). PSU bay `#0x63` intentionally has no AC (single power source) — SEL "redundancy lost" is benign.

**PWM→RPM calibration (manual mode, idle, 2026-06-22):**

| PWM % | byte | Fan1 | Fan2 |
|---|---|---|---|
| 20 | 0x14 | 1320 | 1200 |
| 30 | 0x1e | 1800 | 1680 |
| 40 | 0x28 | 2280 | 2160 |
| 50 | 0x32 | 2640 | 2640 |

≈ linear, ~46 RPM per 1% PWM (`RPM ≈ 46×% + 350`).

**Locked curve (GPU core → fan %):** 30% floor ≤40 °C → linear to 70% at 70 °C → steep to 100% at 80 °C. CPU term applied as `max(gpu, cpu)`: 30% ≤50 °C → 100% at 80 °C. Eyeball it with `./gpu-fan-control.sh selftest` (no hardware/root). Revisit the curve after the in-chassis soak.

**Manual ipmitool reference (Dell 13G):** manual `raw 0x30 0x30 0x01 0x00` · auto `…0x01 0x01` · set-all `raw 0x30 0x30 0x02 0xff <pct-hex>` · read `sdr type fan` / `sdr type temperature`.

**Install (after the hand-test validates behavior):**
```bash
sudo cp infrastructure/server/gpu-fan-control.sh /usr/local/sbin/ && sudo chmod +x /usr/local/sbin/gpu-fan-control.sh
sudo cp infrastructure/server/gpu-fan-control.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now gpu-fan-control.service
journalctl -u gpu-fan-control -f
```
The unit's `ExecStopPost` reverts to iDRAC auto (dead-man's switch — auto maxes the fans, so a dead controller = guaranteed cooling).

See `../../context/hardware-state.md` for live state and `../CLAUDE.md` for domain rules.
