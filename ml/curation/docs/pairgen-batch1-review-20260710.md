# Claude editorial review — synthetic pair draft (2026-07-10, overnight)

Per the local-LLM-review rule. **DRAFT status unchanged** — nothing enters a training mix
until Syed's C3 pass (10% ≈ 28 pairs, subaru_ej-weighted), guided by these findings.

## Stats
- **279 pairs from 400 docs** (0.70/doc). Schema/provenance: all rows complete.
- **Number-grounding: 254/279 (91%)** — every multi-digit number in change+outcome traceable
  to the source doc (canonical match). 25 flagged (ids in `REVIEW-flagged.txt`).

## Findings (systematic — feed the next prompt/filter iteration, don't hand-patch)
1. **Flagged-25 splits into two classes.** (a) *Benign derived values* — model computed
   R=V/I or narrated a plausible post-fix measurement; acceptable reasoning-training content
   but note outcomes are sometimes invented beyond the source. (b) *Near-miss exact
   identifiers* — ECUIDs / table counts reproduced slightly wrong from def-file-adjacent
   docs. **Class (b) is training poison for exact values — recommend dropping every flagged
   pair whose numbers are identifiers rather than measurements.**
2. **Sampling skew (same bug Syed caught in E2, my miss in pairgen):** candidate query is
   still `ORDER BY id` → the 400 docs are the earliest-ingested (defs/rusEFI/early books);
   Heywood/Bosch/FSM ranges untouched. Fix = same Knuth-hash ordering as e2gen, then a
   second batch (supply: 2,536 candidates). ~30-line fix + overnight run.
3. **Degenerate outcomes** in a minority (outcome restates the change, no result) — same
   "qualitative-outcome rule" already in the r3 rubric backlog; add to pairgen prompt next
   iteration ("outcome must state what CHANGED as a result, not repeat the action").
4. **Off-domain drift** smaller than E2's (books are tuning books) but present (hood-scoop
   sizing, firmware-GUI howto). Recommend C3 drops these on sight; not worth a filter yet.

## Recommendation
Usable core is strong (AEM wideband procedures, Vizard intake/turbo scenarios, real
diagnostic arcs). After C3 + dropping class-(b) and degenerate-outcome pairs, expect
~220-240 usable — combined with 82 organic ≈ 300+, still short of the ~400 pilot mix →
run batch 2 with the hash-ordering fix over the unsampled doc range.

---

# Batch 2 review (2026-07-10, hash-scattered sampling + outcome rule)

- **446 pairs from 400 docs (1.1/doc, +57% yield)** — the rich book ranges finally sampled
  (Bosch 149, Heywood 107, Hartman 56, Pulkrabek 51). Zero doc overlap with batch 1
  (exclusion worked). **Grounding-flagged: 4%** (vs 9% b1; ids in REVIEW-flagged-b2.txt).
  **Degenerate outcomes ~3%** (13/446, vs a notable minority in b1) — the outcome prompt
  rule worked.
- **New systematic finding: academic drift.** Heywood/Pulkrabek pairs often dress textbook
  derivations as tuning scenarios ("update the fuel representation $C_nH_mO_r$…") — a
  researcher's arc, not a tuner's. Not fabricated, just off-register. Recommendation for
  assembly (matches the standing 70/30 composition doctrine): **stratify by source** —
  Hartman (engine-management tuning, likely the best set) and practical Bosch content
  weighted up; pure-theory derivations capped, not banned.
- **Combined supply: 725 synthetic drafts + 82 organic.** After C3 curation this clears the
  ~400-pair pilot mix with room to be choosy. The pair problem is now fully a CURATION
  problem — supply is solved.
