EXECUTING bench-integrity plan (2026-08-02, autonomous)
 [x] P1a snippets   evidence-hit 29/69 -> 59/69
 [x] P1b scorer v2  rescore 28 files: dang 265 -> 201
 [x] P1c guard v2   A3/A4/A8/A9 + infix-minus (not in audit)
 [x] P1d index v2   5638 rows + freshness stamp
 [x] P2  probes v2  0 drops, 1 question fix, 3 audit claims refuted
 [>] P3  RERUN LIVE 17 cells; 27B, oss120 first (finalists)
 [ ] P4  rundown    generator ready, waiting on P3
 [x] P5  E4         dry-run 7/7 -> BARS AWAIT SYED
 tests 121 green

 HEADLINE SO FAR: the 27B's E2 gate PASS reverses.
   old 19 exact / 0 dang was at 27.5% coverage (our snippet bug
   starved the evidence). Fixed: 39/3 at 62.3% (k3), 46/2 at
   71.0% (k6). All 3 leaks = guard's NAMED blind spot
   (cited-but-wrong-quantity). k6 beats k3 on every axis.

 NEEDS SYED:
  1. E4 pre-registered bars   docs/E4-DESIGN.md sec.8
  2. E1 dangerous-flip ruling (touches the zero-veto bar)
  3. top_k mode-switching     (k6 > k3 on all axes so far)
  4. adjudicate unit_mismatch rows (AFR vs equivalence ratio)
