# 2026-08-17 - MORNING REPORT: autonomous overnight run (Syed asleep)

**READ FIRST.** Supersedes the 2026-08-16 runbook for current state. Process detail (every command,
why, how it wires in): `2026-08-17-overnight-process.md`. Live tracker: `docs/OPEN-CHECKLIST.md`.
Plan that was approved: `~/.claude/plans/read-the-newest-checklist-bright-sunbeam.md`.

**Nothing was pushed** (your call, review the commits). **Nothing entered any retrieval index.**
`document.tier` untouched. `ref_fts` = 5638 and `ref_dense_v2.npz` sha unchanged. Backups:
`data-backups/corpus-pre-overnight-20260816.sqlite`, `data-backups/ref_dense_v2-20260816.npz`
(+ `corpus-pre-c2-*.sqlite` before the judge run wrote).

## The runbook's seven questions

### 1. Calibration verdict: **3.8 FAILS; judge NOT swapped (stays 3.6)**

`ml/eval/results/recal-qwen3.8-20260816.json`: n=100 (all adjudicated `calibration-100` labels:
54×2 / 37×3 / 9×4), rubric r2, 24576-token budget, 0 errors, 4.0 h GPU, served
`unsloth/Qwen3.8-27B-Q8_0` on the Aug-14 build.

| metric | Qwen3.8 | pre-registered bar (DB meta, 2026-07-05) | 3.6 achieved July (n=87) | 3.6 like-for-like tonight |
|---|---|---|---|---|
| keep/drop @≥4 | **91.0 %** | ≥ 90 ✓ | 93.1 | **90.0 %** (exactly on the bar) |
| within ±1 | **98.0 %** | ≥ 90 ✓ | 97.7 | **98.0 %** |
| **dangerous** (truth ≤2, judged ≥4) | **1**: doc 1081 "Dyno sheets" (subaruforester) | **= 0 ✗** | 0 | **0** |
| exact / Spearman | 69.0 % / 0.564 | - |, | 70.0 % / 0.583 |

(3.6 like-for-like: `recal-qwen3.6-newengine-20260816.json`, same 100 docs, same rubric, same
budget, Aug-14 build, 2.55 h GPU, 0 errors.)

Verdict under your ratified rule (pre-reg AND match-or-beat 3.6 like-for-like AND dangerous 0):
**3.8 FAILS on the hard bar** (1 dangerous). Head-to-head it actually *edges* 3.6 on keep/drop
(91.0 vs 90.0) and ties within±1, the single promotion of junk is what fails it, and that is the bar
that protects the corpus. Nothing to negotiate; `ml/curation/config.yaml` stays `qwen3.6-27b-q8_0`
and C2 ran on 3.6.

**Two things you should not gloss over:**
- **The incumbent cleared the pre-registration with ZERO margin** (90.0 on a ≥90 bar) on the engine
  it now runs on, and is 3 pp below its July 93.1 (n=87 → n=100, and the 4 reference docs are fully
  judged in this harness rather than auto-passed, same treatment for both models, but different from
  July). Not a failure, but not the comfortable margin the July number implied.
- **Both judges recall only 4 of the 9 adjudicated 4s**: the same four (1085, 1099, 1114, 2285),
  and both push 960 / 1031 / 1088 / 5773 down to 3 (or 2) and 1127 to 2. Keep/drop looks fine
  because 54 of 100 truth labels are 2s and both judges are good at *dropping*; on *keeping* they
  agree with the humans 44 % of the time. That is the premise of the whole community-corpus effort
  ("forums hold content the judge will promote") wearing thin, and it is exactly why the C4 review
  found value at score 3 (960, 1088, 5773 are C4 keeps).
- The two judges disagree on 28/100 docs; where they differ 3.8 is higher on 21 (a slightly more
  generous judge, hence the one dangerous cell, not a harsher one as I first wrote in the process doc).

**Two corrections to what the runbook said about the bars:** the DB pre-registration is 90/90/0;
"93.1/97.7" were 3.6's *achieved* numbers, and the "111 labels / 58-43-10" figure was
`calibration-100` + `smoke-10` combined, recalibrate reads calibration-100 only (n=100, 54/37/9).

### 2. Yield from the 314 (was "310"): **DONE 19:40 UTC: 2 × 206 · 3 × 93 · 4 × 15 (4.8 % ≥ 4)**

C2 ran 13:20–19:40 UTC on 3.6 / Aug-14 build, `--no-reindex`, `--sources
forum_romraider,forum_legacygt,forum_msextra,forum_subaruforester`: **314 judged, 0 failed, 391 chunks**.
By source: legacygt 114 (7 fours) · msextra 73 (7) · **romraider 125 (1)** · forester 2 (0). Prior state
was 19 × 4 / 95 × 3 / 213 × 2 (5.8 % ≥ 4); the community tier is now **fully judged: 641 docs, 34 ≥ 4,
188 at 3**. Reproduce: `cd ml/curation && .venv/bin/python -m judge.yield_report --since 2026-08-16T13:00`.

**Honest read.** The ≥4 yield (4.8 %) is at this judge's normal rate, and the calibration says this
judge accepts under half of what humans call a 4. So the number is what *this judge* yields, not proof
the forums are empty: the review pass (§3) found 74 keep-worthy docs across the 3s and 4s, 18 of them
high-value, most of them scored 3. The premise "forums hold diagnostic content the reference corpus
lacks" holds; the premise "the ≥4 bar will surface it" does not. Romraider in particular is 105/125
twos, mostly definition requests and file swaps.

### 3. The review: DONE for the whole community tier: **222 docs, 74 keep** (both parts in
`ml/curation/docs/community-3s-review-2026-08-16.md`, raw JSONL alongside)

- **Part 1** (95 pre-existing 3s): 28 keep / 67 drop.
- **Part 2** (93 new 3s + all 34 fours): 46 keep / 81 drop. Of the 34 fours, **17 recommended NOT to
  index**, labelled honestly: mostly need-fit (MegaSquirt threads that are rubric-correct 4s but useless
  to this car), 6 flagged as genuine arc-missing over-promotions (the doc-1081 pattern).
- **Part 2 is where the value is, 16 high-value keeps vs 2 in part 1:** 884 + 944 (EJ20X/Y swapped
  into an LGT running the EJ255 ECU, the closest real-world analogues of your car), **5793 (a 2005
  Forester ROM read that failed on Openport until the `sti05` method + green test connectors, read
  this before the next sweep)**, 5818 (05 FXT / VF48 / TGV-delete: AVCS transitions, knock-control load
  floor, per-injector comps), 891 (EJ255 vacuum/boost-leak location guide + DIY smoke tester with
  before/after trims), 5891 (first EJ255 healthy-idle MAF datum in the corpus: **4 g/s @ 850 rpm,
  2.05 ms IPW**, new OEM Denso MAF, a *reference point*, not a baseline: 2.5 L, TGVs intact, one
  poster), 5777 / 1085 / 5873 (trims → MAF vs injector vs latency separation on Subaru ROMs), 886
  (a 299-post knock-control primer), 5910 (higher-CR JDM block on a stock USDM cal, how it shows in
  knock feedback / IAM). Reviewer subagents ran on **Fable 5** (verified from transcripts); 35 of 222
  verdicts spot-checked against source text by me, all held.
- **Waiting on your sign-off; nothing indexed.**

### 4. MVEM: guard + rpm-indexed baseline built; car suite 91 → 101 (commit `58c8ec2`, D20)
`mvem.MafBaseline` (points, `validated`, `provenance`, `.at(rpm)`, `from_capture()`), sim seed marked
UNVALIDATED, `NOMINAL_MAF_IDLE` unchanged for the sim/evals. `identify()` refuses MAF verdicts against
an unvalidated baseline with the ratio + trims-only ranking in the reason; the sim harness declares
its baseline validated so E4 is unchanged (18/18). Nothing hardcodes 3.49.

### 5. 3.6 doc-collapse: COLLAPSED, worse than 3.8 (commit `5636759`)
The ratified 93.9% headline retrieved **exactly 3 documents on 100% of 147 queries** (5714 Banish,
621 rusEFI Fuel-Overview, 5502 Hartman), the same three 3.8 got. Both models saw byte-identical
evidence; the "+RAG@3" was a constant preamble (+10 pp for 3.6, 0 for 3.8; six pages → back to 83.7).
E2 does not collapse (325 distinct). `ml/eval/results/DOC-COLLAPSE-2026-08-16.md`, tool
`ml/eval/doc_collapse.py`.

### 6. Decisions I made that you may reverse: see the list below (nothing hidden in it).

### 7. Checklist + commits: `docs/OPEN-CHECKLIST.md` updated (A2/A3/B1/B2/B3/B4/D); commits, oldest first (none pushed):

| commit | what |
|---|---|
| `70d9da9` | recalibrate.py: load config.yaml (was r1/1500 tok), checkpoint/--resume, --doc-ids, both bar sets |
| `58c8ec2` | mvem/identify: MafBaseline + unvalidated-baseline refusal guard (D20), car 91→101 |
| `5636759` | doc_collapse.py + 3.6 headline retrieved 3 constant docs, writeup |
| `7e0c5d5` | judge runner: gone-policy propagated, --no-reindex, dead-server STOP |
| `806ce68` | retrieval: community index + per-parent cap machinery, all off; tier on snippets |
| `33bb379` | 95 score-3 docs reviewed (28 keep / 67 drop); Qwen3.8 RUNDOWN |
| `34b6571` | decisions D20 + gone-policy + E1-dangerous finding; checklist |
| `321166b` | 3.8 calibration result (FAIL, 1 dangerous) |
| `ab42f8f` | 3.6 like-for-like calibration (90.0/98.0/0) |
| `949c29b` | judge.yield_report; process-doc timestamps |
| `211625a` | PROGRESS entry + metric rows |
| `3360094` | decisions: calibration verdict; checklist B3 |
| (later) | this report's final refresh + process doc |

## Decisions I made that you may reverse (running list)
- **Gate rule applied:** pre-registered 90/90/0 (from DB meta) AND match-or-beat 3.6's like-for-like
  recalibration AND dangerous == 0; you ratified this at 06:2x; the runbook's "93.1/97.7 pre-registered"
  wording was wrong and is corrected in `recalibrate.py`.
- **`pending_for_judge()` no longer excludes gone docs** (ratified NARROW policy, never propagated).
  Behaviour change for every future judge run: the 303 gone community docs and any gone reference
  docs are now candidates. `calibrate.py`/`pairgen`/`e2gen` still filter `gone_at`: not touched.
- **`--no-reindex` used for the judge run**: `ref_fts` stays at 5638 although 5649 reference docs
  are kept. Reindex deliberately: `cd ml/curation && .venv/bin/python -m judge.cli --reindex`, then
  rebuild `ref_dense_v2.npz` (`python -m harness.embed_index --device cuda` when the GPU is free, ~4 min).
- **A1 refusal bluntness:** with the seeded baseline, any real log whose MAF ratio is outside
  0.999–1.001 refuses a MAF verdict. Widen a tolerance around 1.0 if you want partial trust.
- **E1 "dangerous" definition:** I did NOT change the codified metric; I reported both readings.
  Under the codified one 3.8's E1v2 is 95.2% / 0 dangerous (passes the bar); under the handoff's
  reading it is 95.2% / 6 (+1 blank). Your call which is ratified, then re-run `rundown.py` on
  every historical E1 file before comparing models.
- **Engine for 3.6 / C2:** the Aug-14 llama.cpp build (`/tmp/start_q36_newbuild.sh` = the 3.8 script
  with the GGUF swapped; ctx 32768, split 3.5,1, draft-mtp). D18 says use the better engine and
  re-baseline; the re-baseline is the 90.0/98.0/0 row. `config.yaml` tag unchanged (`qwen3.6-27b-q8_0`).
  The old certified July build was NOT used. If you want C2's verdicts on the July engine instead,
  restore `data-backups/corpus-pre-c2-20260816-1320.sqlite` and re-run.
- **Sequencing:** I ran the 3.6 recalibration BEFORE C2 (2.5 h of GPU) rather than after, because C2
  writes 314 verdicts with that judge on that engine and I wanted its like-for-like number first. It
  cost C2 those hours; C2 is resumable, nothing lost.
- **Token budget:** unchanged (24576). No context-size errors occurred on either recal (the 330 kB
  doc 960 = 15 chunks went through both times). Cost: runaway-thinking outliers (one 3-chunk doc took
  1643 s on 3.8); the budget was used, not exceeded.
- **`recalibrate` scores the 4 reference-tier docs in the calibration set under full policy** (the
  runner would auto-pass e.g. doc 332). Same for both models tonight; different from July. Noted, not
  changed.

## Final state (20:xx UTC) - nothing running

- **C2 finished 19:40** (0 failed). **llama-server killed** (PID 2049185) at 19:43 on your instruction;
  GPUs at 0 MiB. No background processes of mine remain.
- Verified at the end: `ref_fts` = 5638 (meta 5638), `community_fts` does not exist,
  `ref_dense_v2.npz` sha `9ad0c5a4…` unchanged, `document` tiers 641 community / 5649 reference.
- Test suites, final: **car 101 · ml/eval 124 (+1 gated heavy) · ml/curation 38 · data-pipeline 37**: all
  green from the right venvs. `git status` clean, **0 pushed**.
- Yield history: 60/314 @15:25 (37/19/4) → 160 @17:23 (93/58/9) → 314 @19:40 (206/93/15).

**First decisions for you, in order:** (1) sign off / edit the **74 keeps** (both parts of the review
file), and read 5793 before the next ROM-read attempt; (2) rule on the E1 "dangerous" definition
(codified lean/rich flip → 3.8 is 95.2 %/0; "edit on a no-edit fault" → 95.2 %/6); it decides 3.8's E1
verdict; (3) `judge.cli --reindex` (+11 reference docs) and rebuild the dense npz, or not; (4) whether /
when to build the community index (machinery ready, off) and how the reviewed keeps get in without
rewriting `tier`/`judge_score` (proposal in the review file: a `human_label` row the predicate ORs into);
(5) whether the ≥4 bar is still the right promotion gate for community docs given both judges recall
4/9 adjudicated 4s, a rubric conversation, not a bar-lowering one.
