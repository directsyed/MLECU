# car/logging/

Live ECU telemetry capture (SSM2-over-K-line) + the telemetry schema.

**Status:** **DORMANT — wideband not acquired.** The wideband is the ground-truth instrument; nothing proceeds without it, so no logging is possible yet.

**Will contain:** SSM2 capture (FreeSSM / RomRaider Logger), parsing, and the logged-channel schema — RPM, MAF g/s, AFR correction & learning, injector duty, timing, knock, coolant/IAT, and wideband AFR. The schema will be designed fresh from the Stage-2 logging plan when the hardware arrives. 2005 = SSM2-over-K-line (no CAN diag until 2007+).
