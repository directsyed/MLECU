EXECUTING: bench-integrity plan (started 2026-08-02, autonomous)
 [x] P1a snippet extraction  evidence-hit 29/69 -> 59/69, cap honoured
 [x] P1b scorer v2           rescore of 28 files: dangerous 265 -> 201
 [x] P1c guard v2            A3/A4/A8/A9 + infix-minus fix (found, not in audit)
 [x] P1d provenance+index    index v2 = 5638 rows, freshness stamp, built on Ti in 6min
 [x] P2  probe file v2       69 probes, 0 drops, 1 question fix; 3 audit claims refuted
 [>] P3  E2-v2 RERUN LIVE    17 cells, ~17h; order = 27B, gpt-oss (finalists), 35B, 80B, mistral
 [ ] P4  final rundown       generator built + smoke-tested, waiting on P3 data
 [x] P5  E4 design+skeleton  dry-run 7/7 -> BARS AWAIT SYED (docs/E4-DESIGN.md)
 tests: 121 green

 NEEDS SYED:
  1. E4 pre-registered bars              docs/E4-DESIGN.md sec.8
  2. E1 dangerous-flip definition ruling  (touches the zero-veto bar; see rundown note)
  3. top_k mode-switching discussion      (deferred from last session at his request)
