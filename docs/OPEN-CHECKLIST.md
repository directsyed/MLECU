# MLECU — open checklist

Live tracker of every open thread, both halves of the project. Updated 2026-08-15.
Ordered by **what blocks the car**, because that is the actual objective.

---

## A. CAR / PHYSICAL — the critical path

The ROM read gates the write path, and a tune must be **written to be tested**. Deadline ~2 weeks
from 2026-08-14; target = **safe daily driving** (correct idle, no stumble, safe AFR under load,
no knock). Conservative, not a power tune.

### A1. ROM read — BLOCKED at kernel upload  ← highest priority
Settled by byte-level J2534 capture (`car/logging/j2534_shim.log`):
**the ECU is NOT locked** (seed returned, key accepted, programming session granted) and
**the cable is NOT faulty** (clean checksummed NRC returned). Failure is isolated to
`RequestDownload` → `7F 34 10 generalReject`.

- [ ] **Build the key-substituting shim on Windows** — code written, tested, pushed.
      `cargo +stable-i686-pc-windows-gnu build --release` in `car/ecu/j2534-shim/`
- [ ] **Verify the shim loads in EcuFlash** (copy into EcuFlash's own folder as `op20pt32.dll`).
      **Untested — everything in Track A depends on it.** Success = `==== shim init:` in DebugView.
- [ ] Enable `TACTRIX_SHIM_FIXKEY=1`, attempt read. EcuFlash's key is replaced with FastECU's
      (proven-accepted) key → EcuFlash proceeds into its own sti05 kernel upload.
- [ ] Fallback: FastECU rebuild with the hardcoded `dataFormatIdentifier` (0x04) parameterised.
      Plan: `~/.claude/plans/rebuild-the-fastecu-plan-velvety-anchor.md`
- [ ] File the upstream bug report — `car/ecu/FASTECU-SH7058-KLINE-BUG.md` is written and ready.
      **Do this in parallel from day one**, not as a last resort.
- [ ] Last resort only (Syed's call): bench `shbootmode` (Renesas boot mode bypasses OBD security).

### A2. Data capture — UNBLOCKED, do in parallel
- [ ] **Stage 0 smoke/leak test** — non-negotiable, precedes all logging. Do we have a smoke tester?
- [ ] Read stored DTCs. TGV / catless / exhaust-AVCS deletes should all set codes; their presence
      argues the ROM is unmodified, their absence argues someone suppressed monitors.
- [ ] **Rebuild the DB9 shell** against the molded pin numbers. Dupont jumpers are fine for a
      stationary test, not for a real capture. (Original crimp landed on the wrong pin.)
- [ ] Run the **three-hold capture** (`car/logging/CAPTURE-PROTOCOL.md`) — warm idle / fast idle /
      loaded idle. Channels per `car/logging/IDLE-LOG-PROFILE.md`.
- [ ] **Measure `NOMINAL_MAF_IDLE` on THIS engine.** The 2.50 g/s in `mvem.py` is a sim value and
      this car has TGV + exhaust-AVCS deletes. Until measured, MAF verdicts are provisional.
- [ ] Ground-loop remedy stays in force: DB9 **pin 5 omitted**, signal wire only.

---

## B. ML / EVAL

### B1. Qwen3.8-27B evaluation — E1/E2/E4 done, E1v2 running
- [x] E1v1 arm A **94.3%** top-1, 100% acceptable
- [x] E1v1 arm B@3 **90.0%** — *measures our retrieval, not the model* (see B2)
- [x] E2 arm B@6+guard — 48 exact / 2 dangerous, **hard gate FAIL** (unchanged vs 3.6)
- [x] **E4 — passes all four ratified bars, and beats 3.6 on convergence (15/15 vs 13/15)**
- [ ] E1v2 (147 cases) — running; this is the set matching 3.6's headline
- [ ] Write the RUNDOWN + PROGRESS entry with metric rows

### B2. Retrieval is degenerate — the real finding
Only **4 distinct documents** returned across all 70 E1 cases; two appear on **100%** of queries.
Index is healthy (no stale, no fallback) — this is a **corpus/query-type mismatch**, not a bug.
- [ ] Re-check whether **3.6's ratified `base+RAG@3` headline** suffers the same doc-collapse.
      Free — archived result files, no GPU. **If it does, that ratification rests on noise.**
- [ ] Corpus lacks *differential-diagnosis* content (what separates leak from latency). The
      discriminating fact is in our own `CAPTURE-PROTOCOL.md` but not in the retrieval corpus.

### B3. Judge — calibration-gated, NOT swapped
Config reverted to **3.6, the calibrated judge** (2026-07-05: keep/drop 93.1%, ±1 97.7%, dangerous 0).
- [x] Raise judge `max_completion_tokens` 8192 → 24576 (model-agnostic truncation fix)
- [ ] **Calibrate 3.8 against the EXISTING 100 adjudicated labels** (`calibration-100`).
      **No new human labelling required** — the labels exist (58×2, 43×3, 10×4).
      Metric: exact / ±1 / Spearman / keep-drop @≥4 / **dangerous (truth≤2 judged≥4)**.
- [ ] Swap the judge **only if 3.8 beats 3.6 on that set**. Nothing else is evidence for the
      judging role — E1/E2/E4 measure diagnosis and value lookup, not judging.
- [ ] Then judge the **310 pending** community docs (romraider 122, legacygt 114, msextra 72, forester 2)

### B4. Community corpus — 637 forum docs invisible to retrieval
`ref_fts` is **reference-tier by construction**; all forum threads are excluded. They hold 4× more
vacuum-leak and 2.5× more smoke-test content than everything currently indexed.
- [ ] **Keep the ≥4 bar unchanged** (Syed). Do NOT lower it.
- [ ] **Review the 95 threes with Claude** to recover value without moving the bar.
- [ ] Review ALL docs before anything enters the corpus (Syed) — nothing indexed unreviewed.
- [ ] **Then** fix the index-coverage gap so promoted community docs are actually reachable.
      (Scoring them ≥4 achieves nothing if `ref_fts` still excludes them.)

### B5. Fine-tune pairs as RAG content — viable, sequenced second
242 train + 28 val pairs, format `symptom → diagnosis → change → expected result`.
- Contamination: **E1 0/217 clean**, E2 3/69 need a manual look.
- Coverage gap: **0 pairs mention injector latency, 3 mention vacuum leak** — will NOT fix the
  failures we found. The 27 forum docs discussing leaks are the better target.
- [ ] Add **provenance** before indexing. Pairs carry no source link, and mean 3.4 numbers per
      answer would enter the grounding path unsourced — the exact fabrication surface E2 polices.

### B6. Honest limit on "judging for retrieval value"
**A text judge cannot know whether a fix actually worked.** A confidently wrong forum post is
indistinguishable from a correct one. A judge can only assess *markers of verifiability* —
outcome reported, causal chain present, numbers with units and conditions, thread resolved,
corroboration. Correctness would require cross-checking claims against MVEM / the deterministic
layer (narrow and expensive), which is the only path that does not reduce to one model grading
another's confidence.

---

## C. STANDING RULES EARNED THE HARD WAY
- **D18 — performance beats comparability** when they conflict; disclose confounds, don't preserve
  stale configs to protect a historical number.
- Any reboot **silently disarms** the Openport driver-signature bypass. Check it first on every
  "logging stopped working."
- Never use **Shut down** on the tuning laptop — Fast Startup preserves wedged driver state. Restart.
- `ml/eval/.venv` has no numpy; the harness runs from **`car/.venv`**.
- `pgrep`/`pkill -f` match **your own shell** — kill by PID.
- Token budget and timeout must rise **together**; 8192/600s truncated thinking-models and
  understated them by up to 14pp.
