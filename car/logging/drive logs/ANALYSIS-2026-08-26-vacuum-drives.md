# Vacuum drives 1–3 — analysis (Opus 5 re-analysis, 2026-08-26)

Supersedes the initial pass recorded in commit `7e52502`, which was produced by
`claude-fable-5` (data scripts) and `claude-opus-4-8` (write-up) after a mid-session
model swap. Direction was right; three material errors are corrected below.

## Filtering actually applied here (the first pass applied none of this)

- **Closed loop only** (`CL/OL Fueling* == 8`). Def decode: `8 = CL (normal)`,
  `10 = OL (normal)`, `7 = OL insufficient ECT`, `14 = OL system failure`.
  In OL, `A/F Correction #1` is frozen (sd 0.04 vs 9.75 in CL) and carries no signal.
  OL turns out to sit at LOW load (7–11 % of samples at 0.2–0.4 g/rev = overrun),
  not high load — so the first pass's headline survived by luck, not by method.
- **Steady state**: |drpm/dt| < 150 rpm/s, |dTPS/dt| < 8 %/s.
- **drive1 restricted to t < 115 s** for anything AFR-derived (wideband failed ~120 s).

## Finding 1 — the fuelling error is real, monotonic, and NOT converged

| load g/rev | n | A/F Correction | A/F Learning | TOTAL | wideband |
|---|---|---|---|---|---|
| 0.7–0.8 | 67 | +20.70 % | +13.37 % | **+34.07 %** | 14.49 |
| 0.6–0.7 | 419 | +18.63 % | +9.68 % | +28.31 % | 14.68 |
| 0.5–0.6 | 1412 | +15.94 % | +4.91 % | +20.85 % | 14.62 |
| 0.4–0.5 | 2876 | +4.07 % | +2.18 % | +6.25 % | 14.61 |
| 0.3–0.4 | 6263 | −0.42 % | +1.92 % | +1.50 % | 14.65 |
| 0.2–0.3 | 3045 | −2.13 % | +1.88 % | −0.24 % | 14.69 |

The 2.0 L-on-a-2.5 L-map VE error, measured. Wideband holds 14.5–14.7 throughout,
so the ECU **is** delivering target mixture — it just needs up to a third more fuel
than the map predicts to do it.

**+34 % is a LOWER BOUND.** Run 2 (2026-08-25) showed stored learning cells B/C/D at
exactly 0.000. Across these drives learning ranges 1–3 were all exercised and
`A/F Learning #1` reached **+14.84 %** in drive 3, still climbing. The ECU was
discovering this same bias while we recorded it, so the split between correction and
learning is mid-adaptation and the total has not settled. More cruise time in ranges
2–3 will raise it further before it converges.

## Finding 2 — knock is a TIMING problem, not a fuelling problem

The first pass claimed under-fuelling and knock were "the same root cause". They are not.

**Wideband AFR at every one of the 31 knock onsets: 14.28–15.34.** At or near
stoichiometric. The engine is not lean when it knocks — closed loop is holding target.

Knock is therefore attributable to ignition advance, not mixture: an EJ255 timing
calibration on an EJ20X (different chamber/compression), on an engine whose
`IAM` already sits at **0.500**. Correcting the VE tables will not fix it; the timing
tables (and the already-halved IAM) are the relevant surface.

## Finding 3 — 31 knock onsets, not 5 events

The first pass grouped samples by a >10-sample gap and reported "5 events". Counting
true **onsets** (a step down of ≥1.5° between consecutive samples, which separates
detection from the slow ramp-back) gives **9 in drive2 and 22 in drive3 = 31**.
Worst single retard −12°. All in closed loop, 0.58–0.79 g/rev, 1864–2548 rpm.

The `Feedback Knock Correction` channel is **VALIDATED** by this — it sat at neutral
zero across every idle/cold log, then moved with correlated `Ignition Total Timing`
drops and `Knock Sum` increments. That is the live-knock proof the gate required.

The single `-32.0` sample in drive3 (t=952.01, neighbours −8.12/−7.94) is a log spike,
excluded.

## Coverage — closed-loop steady-state cells

24 usable cells (≥20 samples), 750–2500 rpm × 0.2–0.8 g/rev. Holes: **nothing above
2500 rpm**, nothing above 0.8 g/rev (correct — that is boost), thin at 1500–2500 rpm
in the 0.2–0.4 band.

## Consequences

- VE proposer (D19) has a usable cruise-region dataset, with the caveat that learning
  has not converged — propose against the measured surface but expect it to move.
- Timing work is a separate arc from VE work here, and is gated behind understanding
  the IAM 0.5 / EJ255-map-on-EJ20X question.
- Next capture: 2500–3500 rpm mid-load, vacuum only, same Run 3 parameter list.
