# rom read/ — images READ OFF THE CAR

Only two files live at this level, and the rule is: **what the car is running, and what it
shipped with.** Everything superseded moves to `superseded/`.

| file | what it is |
|---|---|
| `3B12504206_2026-08-16_16h51m01s.bin` | **THE STOCK ROM. Sacred.** The original read, validated byte-identical to a harvested known-stock reference. Every cumulative safety bound (`sensor_envelope`, `max_timing_retard`) is measured against this file. It is the `--baseline-rom` argument in every command. Never overwrite, never move. |
| `POSTFLASH3_3B12504206_maf_2026-08-30.bin` | **WHAT IS ON THE CAR RIGHT NOW.** MAF iterations 1–3. The `--rom` argument — the image any new candidate is patched from. |

`superseded/` holds earlier post-flash reads (POSTFLASH, POSTFLASH2). Kept for the record and
for reproducing an old result; never used as a base for new work.

**Replace `POSTFLASH3` in this folder only after a NEW read off the car has been verified.** Move
the old one to `superseded/` at the same time, and regenerate `SHA256SUMS.txt` in both folders —
`--verify-flash` checks the base image against it, and a stale list turns into a NO-GO.

Two things depend on this layout, so check them if you reorganise further:
`tests/test_romwrite.py` and `tests/test_timing_retard.py` both glob `ecu/rom read/*.bin` and
take the first alphabetically, which is the stock ROM. The glob is non-recursive, so files in
`superseded/` are invisible to it — that is deliberate.
