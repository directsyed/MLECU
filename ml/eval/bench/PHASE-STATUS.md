EXECUTING bench-integrity plan (2026-08-02, autonomous)
 [x] P1a snippets   evidence-hit 29/69 -> 59/69
 [x] P1b scorer v2  rescore 28 files: dang 265 -> 201
 [x] P1c guard v2   A3/A4/A8/A9 + infix-minus (not in audit)
 [x] P1d index v2   5638 rows + freshness stamp
 [x] P2  probes v2  0 drops, 1 question fix, 3 audit claims refuted
 [>] P3  RERUN LIVE 27B done (4/4); oss120 next
 [ ] P4  rundown    generator ready, waiting on P3
 [x] P5  E4         dry-run 7/7 -> BARS AWAIT SYED
 tests 121 green

TWO HEADLINES (27B, the working model):

1. E2 gate PASS REVERSES. Old 19 exact / 0 dang was at 27.5%
   coverage -- our snippet bug starved the evidence, and a model
   that rarely commits rarely fabricates. Fixed: k3 39/3 @62.3%,
   k6 46/2 @71.0%. All leaks = the guard's NAMED blind spot
   (cited-but-wrong-quantity). k6 beats k3 on EVERY axis.

2. E1 diagnosis is UNCHANGED: 92.5% vs 93.2%, i.e. -0.7pp, exactly
   the measured noise band; 0 blanks, 0 truncation, 0 dangerous.
   The snippet bug hit VALUE LOOKUP only, not diagnosis. The
   showdown's E1 verdicts stand.

NEEDS SYED:
 1. E4 pre-registered bars       docs/E4-DESIGN.md sec.8
 2. E1 dangerous-flip ruling -- CONSEQUENTIAL: this cell scores
    0 dangerous under the codified (direction) rule and 3 under
    the historical treatment of flow_rich->maf_high. 0 => PASS
    at 92.5%; 3 => FAIL the zero-veto bar. My reading: that case
    is a MASKING risk (right direction, wrong knob), which is
    E4's job, not E1's. Recommend the codified rule.
 3. top_k mode-switching -- k6 > k3 on all E2 axes
 4. adjudicate unit_mismatch rows (AFR vs equivalence ratio)
