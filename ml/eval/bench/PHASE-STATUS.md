STATE 2026-08-05 — deterministic-layer hardening COMPLETE. Nothing running.
 [x] bench-integrity P1-P4   17/17 cells; RUNDOWN-2026-08-04.md
 [x] scorer v3               exact-ratio unit conversion (ratified)
 [x] E4 bars RATIFIED 08-04  ledger meta `e4_bars`
 [x] DL hardening P1-4,6     estimator + gate + report + envelope
 [!] P5 guard context check  REJECTED by its own retro-test, reverted
 tests: 136 eval + 90 car green | GPUs idle | driver inactive

E4 vs the ratified bars (re-run 08-05, cross-check live):
  27B dense  diag 100%  mask 0  clamp 0  conv 13/15   ALL FOUR PASS
  gpt-oss    diag 77.8% mask 0  clamp 0  conv 11/15   safety pass,
                                                      capability fail

E2 fabrication gate: FAILED BY EVERY MODEL (since unit conversion —
  it un-shielded a 7.4%-wrong answer that was hiding in unit_mismatch).

THE FINDING: the two defences catch DIFFERENT faults.
  27B     stability blocked 52, gate refused 0   (isolated slips)
  gpt-oss stability blocked 54, gate refused 8   (thrashing)
  Neither alone sufficed for gpt-oss.

NEEDS SYED:
 1. STABILITY_N — conv is EXACTLY at the bar (13/15), no headroom.
    N=2 likely restores it for 27B; gpt-oss needs N=3 -> per-model?
 2. belief_envelope % in SafetyCfg (flow 25/lat 30/maf 20) — starting
    points, not measurements
 3. E2 gate still failed by all; blind spot understood, not closable
    inside the guard's contract (see decisions D16)
 4. Qwen 3.8 27B when it lands (6-8h). DeepSeek V4 Flash: NOT advised
    (~4-8 t/s vs a 10 t/s floor, ~35h/battery)

Read first: sessions/handoffs/2026-08-05-deterministic-layer-hardening.md
