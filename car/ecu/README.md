# car/ecu/

ECU flash + definition tooling.

**Status:** not started; ROM ID not yet captured (first FreeSSM/RomRaider connection locks the definitions + flash-tool choice).

**Will contain:** RomRaider/ECUFlash notes, ROM definitions (32-bit, 05–06 FXT family), and the flash-tool interface — KKL/FTDI (genuine FT232RL; reject CH340/PL2303 and any ELM327) for logging; Openport 2.0 or a proven "Rev-E" clone for flashing.

**Flash discipline:** stock ROM read + archived in multiple places **before any write** — the original ROM is sacred. Battery charger on the car, laptop on AC, hours of stable logging before any flash. Raw ROM binaries are gitignored — back them up separately.
