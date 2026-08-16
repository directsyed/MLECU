# 2026-08-16 — Qwen3.8 evaluated, ROM read narrowed to ONE byte, MVEM found mis-calibrated

**READ FIRST. Supersedes 2026-08-08-forester-first-logging-toolchain.md for current state.**
Live tracker: **`docs/OPEN-CHECKLIST.md`** — that file is the source of truth for open items; this
one explains *why* and gives the narrative a cold-start agent needs.

## START HERE

1. **Nothing is blocked on the server.** GPUs idle. One llama-server still loaded on :8080 (Qwen3.8
   Q8, ctx 32768) — leave it or kill it, nothing depends on it.
2. **Syed's next physical action is a 5-value sweep at the car** (§1). Everything for it is built,
   pushed, and verified. He does not need Claude present to run it.
3. **Three things can run tonight without him** — §6.
4. **Two decisions genuinely need Syed** — §7. Do not decide them unilaterally.
5. Repo is **pushed, 0 unpushed commits**, working tree clean.

---

## §1 — THE ROM READ: narrowed from "impossible" to one byte

This was the session's main win. Prior state: read failed, cause unknown, three hypotheses alive.

**A byte-level J2534 capture settled it.** We built a pass-through shim (`car/ecu/j2534-shim/`,
Rust, GPLv3) that sits between the tuning app and the Tactrix driver and logs every byte. Capture is
in `car/logging/j2534_shim.log`:

```
27 01              → 67 01 A1 5B AD 3F     seed returned
27 02 01 B1 1E A4  → 67 02                 KEY ACCEPTED
10 85 02           → 50 85                 programming session GRANTED
34 FF 30 00 04 00 17 AC → 7F 34 10         RequestDownload → generalReject  ← ONLY failure
```

**Eliminated by hard evidence, do not re-litigate:**
- **ECU is NOT locked/married** — it returned a seed, accepted the key, granted a programming
  session. A locked ECU refuses at those steps. (This killed my own leading hypothesis; Syed
  argued against it from the start on the grounds that the car is stock with 200k miles and CELs
  present. He was right.)
- **Cable is NOT faulty** — it delivered a well-formed checksummed request and received a
  well-formed NRC *naming the rejected service*. A corrupting cable yields silence or garbage.
- **Kernel address is NOT wrong** — verified by scanning `ssmk_kline_sh7058.bin` for big-endian
  `0xFFFFxxxx` words: they cluster at `0xFFFF3000/4000/5000`, matching its configured
  `0xFFFF3000`. Same method validates the SH7055 kernel against its `0xFFFF6004`.
- **Seed/key algorithm is solved** — ported from FastECU into `car/ecu/j2534-shim/src/seedkey.rs`,
  unit-tested against **three real captures, two of which the ECU accepted**. `cargo test` = 3/3.

**Remaining hypothesis:** FastECU's `sub_ecu_denso_sh7058` profile is documented **2006-2007**;
EcuFlash's `read_sti05` covers **2005**-2007 on the same SH7058/`sti05` combination. **MY2005 sits
in the coverage gap.** Prime suspect is the hardcoded `dataFormatIdentifier` byte (`0x04`) in
`send_sid_34_request_upload()`.

### What Syed does at the car (READY, nothing left to prepare)
FastECU is cloned, **patched, built and launching** on the laptop. Patch:
`car/ecu/fastecu-patch/` (also applied in his local clone at `C:\Users\Syed\FastECU`).

```powershell
$FE = (Get-ChildItem "$HOME\FastECU" -Recurse -Filter FastECU.exe | Select-Object -First 1).FullName
Remove-Item Env:FASTECU_SID34_FORMAT -ErrorAction SilentlyContinue; & $FE   # CONTROL: must still fail 7F 34 10
$env:FASTECU_SID34_FORMAT="0x00"; & $FE
$env:FASTECU_SID34_FORMAT="0x01"; & $FE      # then 0x02, 0x03
```
Charger on. Key ON / engine OFF. **Key-cycle between attempts** — repeated failures make the ECU
refuse SSM2 init, which looks like a new fault but is the known lockout. Stop immediately on any
response that is not `7F 34 ..`; a `74` means the read is proceeding.

**Why a control run matters:** the patch is inert by default (unset ⇒ `0x04` ⇒ byte-identical to
upstream). If the control does *not* reproduce `7F 34 10`, something is wrong and no sweep result is
trustworthy.

**Dead ends — do NOT retry:**
- EcuFlash cannot be made to load the shim. Tried registry (`PassThruSupport.04.04` — EcuFlash
  ignores it), DLL-in-app-folder (not loaded), SysWOW64 proxy (not loaded). EcuFlash 1.44 is a 2013
  closed-source binary that hardcodes its driver path. **The "merge EcuFlash's kernel upload with
  FastECU's key" plan is therefore dead.** Note we never verified EcuFlash's kernel upload works
  either — that was an inference, not evidence.
- All six EcuFlash K-line seed/key algorithms (SSMK0–5) tried; all fail.
- ECU hard reset (30 min battery disconnect) — no change. Kills the transient-lockout idea.
- SysWOW64 is confirmed **clean** (vendor DLL, 473 KB, 2014). Nothing to revert.

---

## §2 — Qwen3.8-27B: full battery run, SPLIT VERDICT

Model released ~2026-08-14. Downloaded `unsloth/Qwen3.8-27B-Q8_0.gguf` (29.05 GB) — Unsloth
deliberately, because the **3.6 baseline is Unsloth-quantised with an imatrix**, and mixing
quantisers would confound model-version with quantiser. Verified 3.8's file carries an imatrix too,
and is **866 tensors / 65 blocks — structurally identical to the 3.6 baseline**, MTP embedded.

**llama.cpp was 561 commits behind and could not load the model.** Built a *separate* copy at the
Aug-14 head in a git worktree (`/home/syed/tools/llama.cpp-qwen38`), leaving the certified July
build untouched as rollback insurance. **See D18** — Syed corrected my framing here: I had justified
this on comparability grounds; the objective is performance, and comparability is secondary.

| Eval | Result | vs 3.6 |
|---|---|---|
| E4 (closed loop, 4 ratified bars) | diagnosis 100% · masking 0 · clamps 0 · **convergence 15/15** | **BEATS** 3.6 (13/15) |
| E1v2 (147 cases, the headline set) | **95.2%** top-1 both arms, **7 dangerous** | top-1 beats 93.9%, **but 3.6 had ZERO dangerous** |
| E2 (arm B@6 + guard) | 48 exact / 2 dangerous, gate **FAIL** | same as 3.6 |
| E1v1 (70 cases) | arm A 94.3% · arm B 90.0% | — |

**The split is the point.** E4 says adopt 3.8; E1v2 says don't. The ratified E1 bar is
*90% + zero dangerous*, and 3.8 fails the safety half. **All 14 dangerous misses across both arms
are the same confusion: `vacuum_leak` → `injector_latency_lean`** — which is exactly the pair
`CAPTURE-PROTOCOL.md` says is under-determined without the low-voltage hold. **Hold 3 on the real
car directly tests whether that is a model weakness or a genuinely unsolvable-from-the-data problem.**

**Config changes made (kept):** `ml/eval/harness/config.py` `max_completion_tokens` 8192 → **24576**
and `request_timeout_s` 600 → **1800**. Non-negotiable for a thinking model: 3.8 reasons at
`xhigh` by default, and the CLI's own help documents that 8192 truncated thinking-models and
"understated them by up to 14pp", while 600s "died mid-cell". E4's `main()` takes **no** CLI
override, so it would have silently inherited both. Verified after: `finish_reason` = `stop` on
100% of rows, zero truncation, worst case used 4.5% of budget.

---

## §3 — RETRIEVAL IS DEGENERATE (bigger than the model result)

**Only 4 distinct documents were returned across all 70 E1 cases. Two appear on 100% of queries.**
Index is *healthy* — no stale flag, no dense fallback, 5,638 vectors matching 5,638 FTS rows. This
is a **corpus/query-type mismatch**, not a bug: E1 prompts are simulated *log data*, and nothing in
a corpus of engine prose is "about" a log pattern, so every query lands on the same generic
fuel/idle documents.

**Root cause found:** `ref_fts` is **reference-tier by construction**
(`state.py:235 WHERE tier='reference'`). All **637 forum threads are excluded from retrieval** — and
they hold **4× more vacuum-leak** and **2.5× more smoke-test** content than everything indexed.

Consequence: **arm B's numbers measure our corpus, not the model.** Arm A ≈ arm B throughout.

**E2's 2 gate failures were traced to source and are DIFFERENT failures wearing one label:**
- `e2-2097-0` — the genuine D16 blind spot. Source doc **was** retrieved with the truth
  (`20° crank-angle BTC`), but an adjacent chunk of the *same Heywood book* supplied `64° BTC`.
  Guard said `cited` — **correctly**, that number is in evidence.
- `e2-5668-0` — **a retrieval miss, not a fabrication.** Source doc was **never retrieved**; the
  model read a neighbouring spec table faithfully, qualifiers intact, and was scored dangerous for
  answering correctly from the evidence it had.

Both leaks had **4–6 adjacent chunks of one book** filling top-k. Ideas (NOT commitments, per Syed)
are in `docs/OPEN-CHECKLIST.md` §B7 — headline: fixing retrieval halves the gate failure, and **a
fine-tune fixes neither and likely worsens it** (arm C's recorded failure was an E2 fabrication
explosion, 45/69 confident-wrong, because pairs taught *register, not values*).

---

## §4 — ⚠ MVEM IS MIS-CALIBRATED (the most consequential finding)

First validation of MVEM against real vehicle data:

```
NOMINAL_MAF_IDLE (sim) = 2.50 g/s @ 850 rpm
real car, warm idle    = 3.493 g/s @ 709 rpm      → +40%, worse normalised for rpm
identify.maf_belief_ratio() = 1.397 → "MAF believed +39.7% off"
…on a car whose total fuel trim is +0.31%
```

**The deterministic layer would today invent a MAF fault on a healthy engine.** That term is the
only thing separating a MAF fault from an injector-flow fault. Cause is almost certainly the TGV
deletes raising idle airflow — exactly what `CAPTURE-PROTOCOL.md` predicted.

**Do NOT hardcode 3.49.** One log, one operating point, a car that idles poorly, rpm mismatch
against the constant's own assumption. The baseline must come from the three-hold capture at a
known-healthy state, and may need to be a *function of rpm* rather than a scalar.

**This reframes every eval number.** E4's own status string says
`"sim-calibrated-pending (MVEM not yet validated against the real engine)"`. We now have evidence
the sim's healthy baseline is 40% off. Chasing eval scores has unproven transfer until MVEM is
re-grounded. **Syed asked directly whether the RAG fixes are "benchmark maxxing" — partly yes**, and
that exchange is why this section exists.

---

## §5 — D19: the layer needs VE + timing axes

MVEM's docstring: *"a cycle-averaged idle **FUEL** model … we do NOT model combustion, knock
physics, or transients."* No VE table, no ignition, no compression, no boost, no backpressure.

**So E1/E2/E4 prove something narrower than they appear to.** They show the loop can identify idle
*fuel* faults in simulation. The actual job is a 2.0 L at 9.5:1 running an EJ255 calibration for
2.5 L at 8.4:1, with a VF48 and catless exhaust — all VE/timing mismatches with no axis in the model.

**Why the idle data looks deceptively good** (Syed's insight, and it's correct): closed loop drives
trim to ~0 *regardless* of how wrong the airflow model is. `af_learning` is **0.00 in every cell**
because the car has only ever idled — one learned operating point, and the one place feedback can
rescue. Under load the ECU runs **open loop** and the mismatch appears undisguised.

**The asymmetry that makes this tractable:** `safety/clamps.py` already implements six VE/timing
guardrails (`knock_auto_abort`, `fuel_before_timing`, `timing_row_ceiling`, `ve_rate_limit` ±3%,
`boost_gate`, `steady_before_transient`). `algorithms/` proposes only three scalar fuel beliefs.
**The guardrails exist; nothing generates proposals for them to guard.**

Rulings in `decisions.md` D19: VE correction is **measured from real logs, not simulated**; knock is
**never simulated**; and **timing is a RETREAT mechanism, not an optimiser** — the layer may remove
timing autonomously on knock feedback, but *adding* timing requires human review. Blocked on real
data; do not build a speculative VE model (that is exactly how `NOMINAL_MAF_IDLE = 2.50` happened).

---

## §6 — WHAT CAN RUN TONIGHT WITHOUT SYED

1. **3.6 doc-collapse re-check** — free, no GPU, archived result files. Does 3.6's ratified
   `base+RAG@3` headline suffer the same 4-document collapse? **If it does, that ratification rests
   on noise.** Highest value-per-effort item open.
2. **Judge calibration of 3.8** — GPU idle, no human needed until the review step.
   **Uses the EXISTING 100 adjudicated labels (`calibration-100`, 58×2 / 43×3 / 10×4) — Syed does
   NOT re-label anything.** Method: run the candidate judge over those docs, compare to truth via
   `judge/calibrate.py` (exact / ±1 / Spearman / keep-drop @≥4 / **dangerous**).
   **Mechanical blocker not yet solved:** the runner skips docs already marked `judged`, so
   re-scoring needs a force path or a status reset for those 100 doc-ids. Corpus is backed up at
   `data-backups/corpus-pre-3.8-judge-20260815.sqlite`. **Solve this before running, don't fire a
   silent no-op.**
3. **File the FastECU upstream bug report** — `car/ecu/FASTECU-SH7058-KLINE-BUG.md` is written and
   ready. Costs nothing, answer may arrive mid-sweep.

**Judge config is currently 3.6 (correct).** I prematurely swapped it to 3.8 with no basis and Syed
caught it; reverted in commit `b6ed448`. **Do not swap until 3.8 beats 3.6 on the calibration set.**
E1/E2/E4 are not evidence for the judging role.

---

## §7 — DECISIONS THAT NEED SYED (do not decide these)

1. **Does 3.8 displace 3.6 as the working model?** E4 says yes (convergence 15/15 vs 13/15); E1v2
   says no (7 dangerous vs 0). The ratified rule is *90% + zero dangerous*.
2. **Whether to retrain QLoRA on 3.8.** Arms C/D cannot run against 3.8 — the adapter is welded to
   `base_model_name_or_path: …/Qwen3.6-27B`. The pilot's failure was diagnosed as a **data** problem
   (real-car arcs, which don't exist yet), so my read is *not yet* — but a better base arguably
   changes the calculus, and it's his call.

Already ruled by Syed this session, treat as settled: keep the **≥4 judge bar** unchanged; review
the **95 threes** with Claude rather than discarding; **review everything before indexing**; do
**not** re-run 3.6 ("waste of time"); **performance beats comparability** (D18).

---

## §8 — SYSTEM STATE

- GPUs idle. `llama-server` still loaded on :8080 (Qwen3.8 Q8, ctx 32768) — harmless, kill freely.
- **ctx is capped at 32768**, not higher — 65536 fails with `failed to allocate buffer for rs cache`
  (the DeltaNet *recurrent state* cache; GPU0 is the binding constraint at 22.8/24.5 GB).
- New models on disk: `unsloth/Qwen3.8-27B-Q8_0.gguf` (29.05 GB, **primary**),
  `Qwen3.8-27B-Q8_0.gguf` (ggml-org, 28.6 GB, fallback — deletable),
  `mtp-Qwen3.8-27B-Q8_0.gguf` (3.16 GB, redundant, Unsloth embeds MTP). ~343 GB free.
- **A user-space Rust toolchain was installed on the server** (`~/.cargo`, `~/.rustup`) so shim code
  is compile-verified before shipping. `cargo check --target i686-pc-windows-gnu` works.
- Repo pushed, clean, 0 unpushed.

## §9 — GOTCHAS ADDED THIS SESSION (all cost real time)

- **`ml/eval/.venv` has no numpy** — the harness runs from **`car/.venv`**. This is in the old
  handoff and I walked into it anyway.
- **E1 defaults to `sim_cases_v1.jsonl` (70 cases)**; 3.6's headline is **E1v2** (147). Pass
  `--cases data/sim_cases_v2.jsonl` explicitly.
- **E4 is not reachable via `harness.cli`** — it is `python -m harness.e4`, and its `main()` takes
  no `--max-tokens`/`--timeout`.
- **`pgrep`/`pkill -f` match your own shell.** Cost ~20 minutes chasing a "hung" process that was
  the monitoring command itself.
- **A watcher that writes to a log file does not notify.** Use a backgrounded wait that the harness
  reports on, or the user finds a finished run hours later. Syed called this out.
- Windows: admin PowerShell opens in `system32` — relative paths fail; `setx` only reaches
  processes started *afterwards*; `aqt` module `qtwebsockets` does not exist for 5.15.2 (it is in
  base), and the matching compiler is `qt.tools.win32_mingw810`.

## §10 — HONEST NOTE FOR THE NEXT AGENT

Syed corrected me four times this session and was right every time: the premature judge swap, the
"parked, not on the critical path" framing of the ROM read, preserving a stale engine for
comparability, and the missing watcher. He also drove two of the biggest findings — suspecting the
retrieval database rather than the model, and asking whether the fixes were benchmark-maxxing.
**Take his pushback seriously; do not defend a position because you already stated it.**
