# car/ecu/

ECU flash + definition tooling.

**Status:** not started; ROM ID not yet captured. **Flash tool acquired: Washinglee Openport 2.0 "Rev E" clone** — the community-proven Rev-E path from `principles.md` §8 (genuine Openports are $500+/out of production). Brick risk is **flash-only**; all Stage-1/2 *logging* is read-only and safe on it. De-risk before any write: cross-check identical ROM ID + logs against a cheap KKL/FTDI cable, archive the stock ROM in multiple places, stable power. **Test the clone's analog input** (A/D port) — that's the integrated-wideband-logging path (AEM 0–5 V → Openport A/D → RomRaider); clones vary, fall back to the AEM serial plugin if absent.

**Will contain:** RomRaider/ECUFlash notes, ROM definitions (32-bit, 05–06 FXT family), and the flash-tool interface — KKL/FTDI (genuine FT232RL; reject CH340/PL2303 and any ELM327) for logging; Openport 2.0 or a proven "Rev-E" clone for flashing.

**Flash discipline:** stock ROM read + archived in multiple places **before any write** — the original ROM is sacred. Battery charger on the car, laptop on AC, hours of stable logging before any flash. Raw ROM binaries are gitignored — back them up separately.
