# Doc-collapse re-check — did 3.6's ratified `base+RAG@3` headline retrieve real evidence?

**Date:** 2026-08-16 (autonomous overnight run). **Tool:** `ml/eval/doc_collapse.py` (committed;
reproduce with the command at the bottom). **Question (checklist B2 / runbook Track B):** the 3.8
E1 runs retrieved only 4 distinct documents across 70 cases, two on 100% of queries. Does the
**ratified 3.6 headline** — E1v2 arm B, hybrid@3, **93.9% top-1 / 0 dangerous** (2026-07-24) — show
the same collapse?

## Answer: yes — worse. Three documents, each on 100% of all 147 queries.

| cell (file in `results/`) | n | model tag | top-1 | k | **distinct docs** | distinct id-tuples | docs @100% coverage |
|---|---|---|---|---|---|---|---|
| **3.6 headline** `e1-armB-run1-20260724-184006` | 147 | `qwen3.6-27b-q8_0\|e1k3-e2k6` | **93.9** | 3 | **3** | 2 (×136 dominant) | 5714 · 621 · 5502 |
| 3.6 sibling `…20260724-212620` | 147 | `…\|k3-all` | 93.2 | 3 | 3 | 2 (×136) | same three |
| 3.6 re-baseline `…20260729-114805` | 147 | `qwen27b-dense\|noise-mtp-1` | 93.9 | 3 | 3 | 2 (×136) | same three |
| 3.6 re-baseline `…20260729-160743` | 147 | `qwen27b-dense\|noise-mtp-2` | 93.9 | 3 | 3 | 2 (×136) | same three |
| 3.6 post-fix reverify `…20260802-215442` | 147 | `…\|e1v2-armB-k3-reverify` | 92.5 | 3 | 3 | 2 (×87) | same three |
| **3.8** `…20260815-025914` | 147 | `qwen3.8-27b-q8_0\|armB-k3-e1v2` | **95.2** | 3 | **3** | 2 (×87) | same three |
| 3.6 E1v1 `…20260724-204315` | 70 | `qwen3.6…\|e1k3-e2k6` | 80.0 | 3 | 4 | 4 | 5714 100 · 621 100 · 721 91.4 · 5443 8.6 |
| 3.8 E1v1 `…20260814-194125` | 70 | `qwen3.8…\|armB-k3` | 90.0 | 3 | 4 | 4 | 5714 100 · 621 100 · 721 82.9 · 5443 17.1 |
| 3.6 E1v2 **k=6** `…20260724-123032` | 147 | `qwen3.6-27b-q8_0` | 83.7 | 6 | 6 | 4 (×117) | 1835 · 621 · 721 · 5714 · 5715 (all 100%) |

The three constant documents (all `kind=theory`, `tier=reference`, generic fuel/idle prose):

| id | what it is |
|---|---|
| 5714 | Greg Banish, *Engine Management: Advanced Tuning* — a page of ch. 1 |
| 621 | rusEFI wiki `Fuel-Overview.md` |
| 5502 | Jeff Hartman, *How to Tune and Modify Automotive Engine Management Systems* — a page |

(E1v1's fourth doc 721 = rusEFI `MAF.md`; 5443 = another Hartman page; the k=6 set adds 5715 = the
adjacent Banish page and 1835 = a Heywood page.)

**Control — E2 does *not* collapse:** arm B@6 over 69 probes → 3.6 **325** distinct docs
(max per-doc coverage 7.2%), 3.8 **323**, same top-5. E2 prompts are questions *about* things the
corpus contains; E1 prompts are simulated log data that nothing in a corpus of engine prose is
"about", so every E1 query lands on the same generic pages. Corpus/query-type mismatch, not an
index bug (index was verified healthy: no stale flag, no dense fallback, 5,638 = 5,638).

## What this means (stated plainly)

1. **Retrieval is a pure function of (case prompt, index).** 3.6 and 3.8 were fed **byte-for-byte
   the same evidence** on every E1v2 case. The 93.9/0-dangerous vs 95.2/7-dangerous difference is
   **entirely model-side**; retrieval contributed no case-specific information to either.
2. **The ratified "+RAG@3" was, in effect, a constant three-page preamble.** For 3.6 that preamble
   moved top-1 from **83.7% (arm A, 2026-07-15) to 93.9%** and six constant pages moved it back to
   83.7% ("distraction is dose-dependent", PROGRESS 2026-07-24). So the effect was real but it was a
   *prompt-prefix* effect — three specific fixed pages of fuel theory nudging the diagnosis — not
   retrieval doing its job. For 3.8 the same preamble did **nothing** (95.2 both arms).
   *Confound to disclose:* the 83.7 arm-A cell predates the 07-25 harness fixes; the arm-B cells
   were re-verified after them (92.5–93.9). The direction is not in doubt; the exact delta is.
3. **The ratification therefore measured "base model + fixed prefix", not "base + RAG".** The
   decision to run arm B is not *wrong* — the prefix helped 3.6 and cost nothing — but the claim
   "retrieval passes the E1 bar" is not supported by these files. Nothing in this analysis changes
   E2 (where retrieval demonstrably works) or E4.
4. **Nothing will change this without changing the corpus or the query representation.** Judging
   more forum threads into the reference index (tonight's C2) does *not* by itself fix E1
   retrieval, because `ref_fts` is reference-tier by construction and E1 queries are log-shaped.
   The B4/Track-D community index and, more importantly, a *log-pattern → diagnosis* query
   representation are the levers. That is a design question for Syed, not tonight's work.

## Reproduce

```bash
cd ml/eval && ../../car/.venv/bin/python -m doc_collapse \
  results/e1-armB-run1-20260724-184006.jsonl results/e1-armB-run1-20260815-025914.jsonl \
  results/e1-armB-run1-20260724-204315.jsonl results/e1-armB-run1-20260814-194125.jsonl \
  results/e1-armB-run1-20260724-123032.jsonl \
  results/e2-armB-run1-20260725-045805.jsonl results/e2-armB-run1-20260814-212406.jsonl
```
Field: `retrieved_doc_ids` per row (present in every E1/E2 arm-B file back to 2026-07-08; July rows
lack the later `top_k`/`retrieval_mode`/`index_stale` provenance keys, so k is inferred from row
length).
