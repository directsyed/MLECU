# car/logging/

Live ECU telemetry capture (SSM2-over-K-line) + the telemetry schema.

**Status:** live capture **DORMANT — wideband not acquired** (the ground-truth instrument; nothing proceeds without it). But the offline **parser + binning are BUILT** in `../ecutune/logparse/` (RomRaider/SSM2 CSV → canonical channels → airflow×rpm bins with steady-state gating). Real captured logs drop straight into it; only the live SSM2-over-K-line capture waits on hardware.

**Will contain:** SSM2 capture (FreeSSM / RomRaider Logger), parsing, and the logged-channel schema — RPM, MAF g/s, AFR correction & learning, injector duty, timing, knock, coolant/IAT, and wideband AFR. The schema will be designed fresh from the Stage-2 logging plan when the hardware arrives. 2005 = SSM2-over-K-line (no CAN diag until 2007+).
