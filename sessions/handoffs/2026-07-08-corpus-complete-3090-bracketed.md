# 2026-07-08 (evening) — CORPUS 100% JUDGED; 3090 threshold bracketed; eval harness next (DELTA)

Read this FIRST on session start. Supersedes the 2026-07-08 morning handoff. Forward plan:
`docs/ROADMAP.md` (unchanged).

## Current live state
- **Corpus: FULLY JUDGED under rubric-r2.** 5,691 docs / 5,796 chunks, keep>=4 = 3,790, 2
  honest-fails (5781 + parked; manual queue). Final harvest: **82 pairs** (61 subaru_ej), in
  `ml/curation/data/pairs/pairs-rubric-r2.jsonl`. Verdict: RAG-rich, pair-poor — arms C/D of
  the eval gate blocked on the Phase-D pair-synthesis bridge (design discussion is Syed-owned).
- **GPU config (deployed + committed): tensor-split 3.5,1 + 3090 core locked 800 MHz.**
  Ti = 49 layers / 21.9 GiB / ~296 W; convicted 3090 = 15 layers / 7.5 GiB / **~152 W decode**
  (pinned-mem idle floor is ~115 W). ~54 t/s retained. Crashes #10/#11 (SEL Slot 7 Bus Fatal,
  Syed-confirmed) killed the old 1005 MHz/1,1 config during PLAIN DECODE (~230 W, <65 °C, 0
  AER, config drift ruled out by boot-journal diff). **Threshold bracketed: 152 W < fail <
  230 W steady decode → power-delivery signature; teardown starts at backside cap groups.**
  DO NOT raise the 3090's split share or clocks. DB snapshot ritual before risky runs:
  `data-backups/corpus-2026-07-08-pre-crashrun.sqlite` exists (.backup API, never cp).
- **watch-judge cockpit FIXED + verified live** (middle pane was hardcoded to the ref-tier
  log; now globs newest `*run*.log` at launch — restart the cockpit after starting a new run).

## In progress / NEXT (priority order)
1. **Eval harness build (`ml/eval/harness/`) — authorized, started, interrupted by the GPU
   crisis.** Design locked by ROADMAP protocol: arms A (base) + B (RAG over ref_fts BM25),
   E1 runner vs `sim_cases_v1.jsonl` scored via `car/ecutune/evals/scoring.py` loaded by
   file-path import (identical scoring to the 85.7%/100% rules baseline), E2 probe generator
   from reference keeps (provenance-tagged, Syed spot-check before use), dangerous-near-miss
   scorer, CLI mirroring judge.cli. LLM client pattern: copy of `judge/llm.py` against the
   same llama-server :8080. Bars pre-registered in DB meta BEFORE arms run (Syed locks them).
2. **NASIOC cookie ritual due** (canary caught expiry at the 04:48 poll; Syed has the
   command). New threads → small judge batch → re-harvest.
3. r3 rubric backlog (unchanged from morning handoff); pair-synthesis design talk (Phase D).
4. Teardown prep: dossier now has 11 SEL convictions + the power bracket. Provoked-crash
   verify test after any repair: unlock clocks, real inference, sick card dies <1 min.
5. `mlecu-corpus.timer` bug: inline comment on `Persistent=true` → systemd ignores it (parse
   warning in journal); move comment to its own line, redeploy user unit.

## Standing gotchas (carry forward)
- Commands to Syed: full explanation, every new flag (HARD). Narrate ALL actions live (HARD,
  new 2026-07-08 — in memory/narrate-all-actions.md).
- `pkill -f "judge.cli --run"` self-matches the calling shell AND any watcher containing the
  string — use `pgrep/pkill -f "judge[.]cli"` bracket trick.
- Runner marks docs FAILED when llama-server is unreachable — STOP the runner before any
  llama-judge restart (kill runner → restart service → relaunch; doc-atomic, nothing lost).
- Background Bash: `cd X && cmd & tail relative-path` runs the tail in the OLD cwd — use
  absolute paths after backgrounding.
