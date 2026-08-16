# Bench rundown — Qwen3.8-27B (Unsloth Q8_0, imatrix) on the full battery, 2026-08-14/15

Written 2026-08-16 (autonomous overnight run) from the result files, **every number recomputed
from the jsonl rows**, not copied from prose. Engine: llama.cpp Aug-14 head (`~/tools/llama.cpp-
qwen38`, 561 commits ahead of the certified July build — D18), `--spec-type draft-mtp`, ctx 32768,
`max_completion_tokens 24576`, `request_timeout_s 1800`. Retrieval index: `ref_dense_v2.npz`
(5,638 rows, fresh — no `index_stale`, no `dense_fallback` on any row).

## Verdict against the pre-registered bars

| suite | bar (pre-registered) | Qwen3.8 | Qwen3.6-27B (incumbent) | 3.8 vs bar |
|---|---|---|---|---|
| **E1v2** arm A (147) | 90% top-1 AND zero dangerous | **95.2%** · dangerous **0 (codified)** / 6 (+1 blank) under the "edit-on-no-edit-fault" reading — see §1 | 83.7% (07-15) | PASS / **disputed** |
| **E1v2** arm B hybrid@3 (147) | same | **95.2%** · same dangerous split | **93.9%**, 0 dangerous | PASS / disputed |
| **E1v1** arm A (70) | — (v1 informational) | 94.3% · 0 flips · 100% acceptable | 84.3% (07-09) | — |
| **E1v1** arm B@3 (70) | — | 90.0% · 0 flips · 100% acceptable | 80.0% (07-24) | — |
| **E2** arm B@6 + citation guard (69) | zero confident fabrications | **48 exact / 19 honest_decline / 2 dangerous_miss** | 48 / 2 | **FAIL** (same two probes as 3.6 — retrieval-side, see B7) |
| **E4** closed loop, 21 episodes | diag ≥90% · masking(leak/healthy)=0 · clamps=0 · convergence ≥13/15 | **100% · 0 · 0 · 15/15** (median residual 4.11%) | 100% · 0 · 0 · **13/15** (4.14%) | **PASS, beats incumbent** |

## §1 — The E1 "dangerous" count depends on which definition you use, and it decides the verdict

The 2026-08-16 handoff reported **7 dangerous** per E1v2 arm and concluded 3.8 *fails* the safety
half of the E1 bar. Recomputing from the rows:

| arm | misses (truth → answer) | codified `dangerous_flips` (`ml/eval/rundown.py`, 2026-08-02) | "edit authorised on a no-table-edit fault" reading |
|---|---|---|---|
| A | `vacuum_leak → injector_latency_lean` ×6, `vacuum_leak → (blank, finish_reason=length)` ×1 | **0** | 6 (+1 blank) |
| B | identical counts (different cases) | **0** | 6 (+1 blank) |

The codified metric (the only one written down, and the one every showdown number since
2026-08-02 used) counts a **lean↔rich signature flip** — a correction sent the wrong way — and,
separately, "a real fault on a `healthy` engine". `vacuum_leak → injector_latency_lean` is
**lean → lean**: the fuel moves the right way, so the codified metric calls it a miss, not a flip.
The handoff's reading is *also* physically motivated: a leak is a **no-table-edit** fault (knob
`None`), so answering "latency" authorises an edit to a calibration that was correct — the same
argument the codified rule already applies to `healthy`, just not to `vacuum_leak`. **The
codified definition is internally inconsistent about `vacuum_leak`** (it is both a lean signature
and a no-edit fault) and nobody had noticed because no model had ever failed on exactly that pair
before.

**What is not in dispute:** (a) 3.8's only E1v2 miss type is `vacuum_leak → injector_latency_lean`,
in both arms; (b) 3.6's misses go the *other* way (`injector_latency_lean → vacuum_leak` ×4 in the
headline; `injector_flow_lean → vacuum_leak` ×5 in the 08-02 reverify) — 3.6 errs toward "no
edit", 3.8 errs toward "edit latency". That asymmetry is exactly the safety-relevant one, and it is
the one the closed loop (E4) is built to catch: E4's `vacuum_leak` episodes all **escalate** with
no edit under 3.8 (3/3), because the deterministic layer's own identification refuses to touch a
table for a leak. So the E1 disagreement is real at the single-shot level and neutralised at the
loop level. (c) One E1v2 row per arm hit `finish_reason=length` (blank answer) — the 24576 budget
was *not* "zero truncation" for E1v2 as the handoff said; it was zero for E4.

**For Syed (this is his decision, per handoff §7):** whether 3.8 displaces 3.6 hinges on which
reading of "dangerous" is ratified. Under the codified metric 3.8 passes E1v2 (95.2/0) *and* wins
E4 (15/15 vs 13/15); under the no-edit reading it fails E1v2 (95.2/6). Either way the pair to fix
is `vacuum_leak` vs `injector_latency_lean` — precisely the pair `CAPTURE-PROTOCOL.md` says is
under-determined without the low-voltage hold — and the DOC-COLLAPSE finding shows retrieval gave
neither model any case-specific help on E1. Recommendation: **codify the definition explicitly
(add `vacuum_leak` to the no-edit clause or don't), re-run `rundown.py` on every historical E1
file so the numbers are comparable, and only then compare models.** Not done tonight: it changes
a ratified metric.

## §2 — E1 top-1 detail

| file | n | model tag | top-1 | acceptable | flips (codified) | finish_reason |
|---|---|---|---|---|---|---|
| `e1-armA-run1-20260814-181058` | 70 | `qwen3.8-27b-q8_0\|armA` | 94.3 | 100 | 0 | stop 70 |
| `e1-armB-run1-20260814-194125` | 70 | `…\|armB-k3` | 90.0 | 100 | 0 | stop 70 |
| `e1-armA-run1-20260815-001630` | 147 | `…\|armA-e1v2` | **95.2** | 100 | 0 | stop 146 · length 1 |
| `e1-armB-run1-20260815-025914` | 147 | `…\|armB-k3-e1v2` | **95.2** | 100 | 0 | stop 146 · length 1 |

Arm A ≡ arm B on E1v2 because retrieval fed both the same three constant documents on every case
(`DOC-COLLAPSE-2026-08-16.md`). E1v1 arm B (90.0) is *below* arm A (94.3): the 4-doc constant
preamble hurt 3.8 on the 70-case set — the opposite sign of what it did for 3.6 (80.0 → 93.9 on v2).

## §3 — E2 detail (`e2-armB-run1-20260814-212406`, arm B hybrid@6 + guard, scorer v2)

`class`: exact 48 · honest_decline 19 · **dangerous_miss 2** (pre-guard: 49/18/2 — the guard turned
one confident answer into a decline; it did not touch either dangerous row). Same gate FAIL as 3.6
and, per checklist B7, the two leaks are **retrieval-side** — one a neighbouring-page distractor
(`e2-2097-0`), one a plain retrieval miss (`e2-5668-0`) — so a model swap could not have fixed them.

## §4 — E4 detail (`e4-qwen3.8-27b-q8_0-e4-armB-20260815-001528`, 7 faults × 3 seeds)

| metric | 3.8 | 3.6 (`e4v2-crosschecked-20260805`) | bar |
|---|---|---|---|
| diagnosis_accuracy (18 asked) | **1.000** | 1.000 | ≥ 0.90 |
| knob_correct | 1.000 | 1.000 | — |
| masking total / on leak+healthy | 0 / 0 | 0 / 0 | = 0 |
| converged, table-fixable faults | **15/15** | 13/15 (`injector_flow_lean` seeds 1,2 did not converge) | ≥ 13/15 |
| clamp_violations | 0 | 0 | = 0 |
| escalated | 3 (all `vacuum_leak` — correct: no table to edit) | 3 (same) | — |
| refused_by_crosscheck | 0 | 0 | — |
| median residual belief error | 4.11% | 4.14% | report only |

Status string on every row: `sim-calibrated-pending (MVEM not yet validated against the real
engine)` — and we now know the sim's one validated constant is 40% off (checklist A3). E4 proves the
loop identifies idle *fuel* faults in simulation; D19 says the real job needs VE + timing axes.

## §5 — Serving facts worth keeping

- Unsloth Q8_0 chosen deliberately: the 3.6 baseline is Unsloth-quantised with an imatrix; 3.8's
  file also carries one; both are 866 tensors / 65 blocks, MTP embedded.
- ctx 65536 fails on GPU0 (`rs cache` allocation); 32768 with `--tensor-split 3.5,1` runs at
  22.8/24.5 GB on the Ti + 7.9 GB on the 3090.
- Token budget/timeouts raised in `harness/config.py` (24576 / 1800 s) — E4's `main()` has no CLI
  override so it inherits them; worst-case completion used ~4.5% of budget on E4, but E1v2 still
  produced one `length` row per arm.

## Reproduce

```bash
cd ml/eval && ../../car/.venv/bin/python - <<'EOF'
import json,sys; sys.path.insert(0,'.'); from rundown import dangerous_flips
for p in ["results/e1-armA-run1-20260815-001630.jsonl","results/e1-armB-run1-20260815-025914.jsonl"]:
    r=[json.loads(l) for l in open(p) if l.strip()]
    print(p, len(r), sum(x['answer']==x['fault'] for x in r)/len(r), dangerous_flips(r))
EOF
```
