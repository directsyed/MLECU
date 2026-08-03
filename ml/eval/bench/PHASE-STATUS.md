BENCH-INTEGRITY PLAN — P1-P4 COMPLETE (2026-08-03)
 [x] P1 instrumentation  evidence-hit 29/69 -> 59/69; 12 defects fixed
 [x] P2 probes v2        0 drops, 1 question fix, 3 audit claims refuted
 [x] P3 rerun            17/17 cells done
 [x] P4 rundown          ml/eval/results/RUNDOWN-2026-08-03.md
 [x] P5 E4 built         dry-run 7/7 -> BARS AWAIT SYED
 tests 129 green | GPUs idle | driver drained+stopped

VERDICT: NO MODEL PASSES BOTH PRE-REGISTERED BARS.
  27B dense   E1 92.5% PASS | E2 47ex/2dg FAIL
  gpt-oss     E1 78.9% FAIL | E2 48ex/0dg PASS  <- only gate pass
  They fail in OPPOSITE directions. E4 is the tiebreaker and is
  blocked on Syed ratifying its bars.

The 27B's old E2 "PASS" was an artifact: 19 exact at 27.5% coverage,
because our snippet bug starved the evidence. Fixed -> 47 exact at
72.5% coverage, and the cost becomes visible.

NEEDS SYED (in priority order):
 1. E4 pre-registered bars        docs/E4-DESIGN.md sec.8  <- critical path
 2. E1 dangerous-flip ruling      (0 vs 3 on the 27B; see rundown)
 3. top_k mode-switching          k6 > k3 in ALL 5 models, every axis
 4. adjudicate unit_mismatch rows (AFR vs equivalence ratio)
