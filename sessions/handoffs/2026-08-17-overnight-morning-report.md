# 2026-08-17 — MORNING REPORT: autonomous overnight run (Syed asleep)

**READ FIRST.** Supersedes the 2026-08-16 runbook for current state. Process detail (every command,
why, how it wires in): `2026-08-17-overnight-process.md`. Live tracker: `docs/OPEN-CHECKLIST.md`.
Plan that was approved: `~/.claude/plans/read-the-newest-checklist-bright-sunbeam.md`.

**Nothing was pushed** (your call — review the commits). **Nothing entered any retrieval index.**
`document.tier` untouched. `ref_fts` = 5638 and `ref_dense_v2.npz` sha unchanged. Backups:
`data-backups/corpus-pre-overnight-20260816.sqlite`, `data-backups/ref_dense_v2-20260816.npz`
(+ `corpus-pre-c2-*.sqlite` before the judge run wrote).

## The runbook's seven questions

### 1. Calibration verdict — **3.8 FAILS; judge NOT swapped (stays 3.6)**

`ml/eval/results/recal-qwen3.8-20260816.json` — n=100 (all adjudicated `calibration-100` labels:
54×2 / 37×3 / 9×4), rubric r2, 24576-token budget, 0 errors, 4.0 h GPU, served
`unsloth/Qwen3.8-27B-Q8_0` on the Aug-14 build.

| metric | Qwen3.8 | pre-registered bar (DB meta, 2026-07-05) | 3.6 achieved July (n=87) | 3.6 like-for-like tonight |
|---|---|---|---|---|
| keep/drop @≥4 | **91.0 %** | ≥ 90 ✓ | 93.1 | **90.0 %** (exactly on the bar) |
| within ±1 | **98.0 %** | ≥ 90 ✓ | 97.7 | **98.0 %** |
| **dangerous** (truth ≤2, judged ≥4) | **1** — doc 1081 "Dyno sheets" (subaruforester) | **= 0 ✗** | 0 | **0** |
| exact / Spearman | 69.0 % / 0.564 | — | — | 70.0 % / 0.583 |

(3.6 like-for-like: `recal-qwen3.6-newengine-20260816.json`, same 100 docs, same rubric, same
budget, Aug-14 build, 2.55 h GPU, 0 errors.)

Verdict under your ratified rule (pre-reg AND match-or-beat 3.6 like-for-like AND dangerous 0):
**3.8 FAILS on the hard bar** (1 dangerous). Head-to-head it actually *edges* 3.6 on keep/drop
(91.0 vs 90.0) and ties within±1 — the single promotion of junk is what fails it, and that is the bar
that protects the corpus. Nothing to negotiate; `ml/curation/config.yaml` stays `qwen3.6-27b-q8_0`
and C2 ran on 3.6.

**Two things you should not gloss over:**
- **The incumbent cleared the pre-registration with ZERO margin** (90.0 on a ≥90 bar) on the engine
  it now runs on, and is 3 pp below its July 93.1 (n=87 → n=100, and the 4 reference docs are fully
  judged in this harness rather than auto-passed — same treatment for both models, but different from
  July). Not a failure, but not the comfortable margin the July number implied.
- **Both judges recall only 4 of the 9 adjudicated 4s** — the same four (1085, 1099, 1114, 2285) —
  and both push 960 / 1031 / 1088 / 5773 down to 3 (or 2) and 1127 to 2. Keep/drop looks fine
  because 54 of 100 truth labels are 2s and both judges are good at *dropping*; on *keeping* they
  agree with the humans 44 % of the time. That is the premise of the whole community-corpus effort
  ("forums hold content the judge will promote") wearing thin — and it is exactly why the C4 review
  found value at score 3 (960, 1088, 5773 are C4 keeps).
- The two judges disagree on 28/100 docs; where they differ 3.8 is higher on 21 (a slightly more
  generous judge — hence the one dangerous cell — not a harsher one as I first wrote in the process doc).

**Two corrections to what the runbook said about the bars:** the DB pre-registration is 90/90/0;
"93.1/97.7" were 3.6's *achieved* numbers, and the "111 labels / 58-43-10" figure was
`calibration-100` + `smoke-10` combined — recalibrate reads calibration-100 only (n=100, 54/37/9).

### 2. Yield from the 314 (was "310") — <FILL: distribution, honest characterisation, partial?>

### 3. The 3s review — DONE for the 95 existing: **28 keep / 67 drop**
`ml/curation/docs/community-3s-review-2026-08-16.md` (+ rubric + raw JSONL). Judged on retrieval
usefulness for the current gaps, markers of verifiability only. Needs census: MegaSquirt/generic
dominate; **no doc supplies a healthy-idle MAF baseline**. New 3s from the C2 run need the same pass.
**Waiting on your sign-off — nothing indexed.**

### 4. MVEM — guard + rpm-indexed baseline built; car suite 91 → 101 (commit `58c8ec2`, D20)
`mvem.MafBaseline` (points, `validated`, `provenance`, `.at(rpm)`, `from_capture()`), sim seed marked
UNVALIDATED, `NOMINAL_MAF_IDLE` unchanged for the sim/evals. `identify()` refuses MAF verdicts against
an unvalidated baseline with the ratio + trims-only ranking in the reason; the sim harness declares
its baseline validated so E4 is unchanged (18/18). Nothing hardcodes 3.49.

### 5. 3.6 doc-collapse — COLLAPSED, worse than 3.8 (commit `5636759`)
The ratified 93.9% headline retrieved **exactly 3 documents on 100% of 147 queries** (5714 Banish,
621 rusEFI Fuel-Overview, 5502 Hartman) — the same three 3.8 got. Both models saw byte-identical
evidence; the "+RAG@3" was a constant preamble (+10 pp for 3.6, 0 for 3.8; six pages → back to 83.7).
E2 does not collapse (325 distinct). `ml/eval/results/DOC-COLLAPSE-2026-08-16.md`, tool
`ml/eval/doc_collapse.py`.

### 6. Decisions I made that you may reverse
<FILL — see the running list below>

### 7. Checklist + commits — <FILL: commit list>

## Decisions I made that you may reverse (running list)
- **Gate rule applied:** pre-registered 90/90/0 (from DB meta) AND match-or-beat 3.6's like-for-like
  recalibration AND dangerous == 0 — you ratified this at 06:2x; the runbook's "93.1/97.7 pre-registered"
  wording was wrong and is corrected in `recalibrate.py`.
- **`pending_for_judge()` no longer excludes gone docs** (ratified NARROW policy, never propagated).
  Behaviour change for every future judge run: the 303 gone community docs and any gone reference
  docs are now candidates. `calibrate.py`/`pairgen`/`e2gen` still filter `gone_at` — not touched.
- **`--no-reindex` used for the judge run**: `ref_fts` stays at 5638 although 5649 reference docs
  are kept. Reindex deliberately: `cd ml/curation && .venv/bin/python -m judge.cli --reindex`, then
  rebuild `ref_dense_v2.npz` (`python -m harness.embed_index --device cuda` when the GPU is free, ~4 min).
- **A1 refusal bluntness:** with the seeded baseline, any real log whose MAF ratio is outside
  0.999–1.001 refuses a MAF verdict. Widen a tolerance around 1.0 if you want partial trust.
- **E1 "dangerous" definition:** I did NOT change the codified metric; I reported both readings.
  Under the codified one 3.8's E1v2 is 95.2% / 0 dangerous (passes the bar); under the handoff's
  reading it is 95.2% / 6 (+1 blank). Your call which is ratified — then re-run `rundown.py` on
  every historical E1 file before comparing models.
- <FILL: anything from T3/T4 — engine used for 3.6, token budget changes, reordering>

## What is still running / what to do first
<FILL>
