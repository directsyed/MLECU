# rubric-r2 — what changed from r1 and why (for Syed's guard review)

Every change traces to smoke-10 evidence or a Syed directive from 2026-07-04/05.

1. **Anchor 4 now REQUIRES a reported, data-backed outcome** (Syed's bar: "no outcome = it's a
   conversation"). The r1 wording collision — "unresolved thread" appearing in both anchors 3
   and 4 — caused the dense/MoE keep-flip on doc 961. r2: quantified-but-unconfirmed = 3, hard
   rule stated inline. Doc 961 is now a worked example inside anchor 3.
2. **Anchor 5 = anchor 4 + verification discipline** (controls, re-baselining) with doc 960's
   seven-run MPG experiment as the worked example. Real corpus docs as anchors make the scale
   concrete for the judge — and for future rubric revisions.
3. **Anchor 2 explicitly covers tooling-support threads** (doc 964 case) with the redundancy
   rationale: the reference tier already holds authoritative tool docs (Syed's point).
4. **Extraction policy made explicit (D3 resolved):** extract stated arcs from any chunk
   scoring ≥3; nothing from 1–2; empty legs are "" and never inferred; harvest filtering is
   downstream's job. (r1 silence caused dense=extract-always vs MoE=extract-on-keep split.)
5. **New verdict fields:** `relevance` (subaru_ej | subaru | general — corpus-composition
   metadata, explicitly firewalled from the score) and `evidence_in_images` (flags docs whose
   evidence the judge can't see; doubles as the worklist for a future VLM captioning pass).
   Both persisted to judgment table columns (migrated).
6. **Vehicle context block in system.md** — full FXT/EJ20X build facts so the judge
   *understands* what it reads (Syed directive), with an explicit instruction that platform
   match must not inflate scores.
7. **Synopsis pre-pass** (Syed's context decision, option 2): multi-chunk docs get one factual
   ≤150-word synopsis generated from the doc head, included in every chunk prompt; prompt
   forbids quality hints so it can't bias scores. Wired in runner + audited.
8. Kept unchanged (proven in testing): grounding rules (irrelevant-snippet handling was
   correct in every sampled rationale), "when torn take the LOWER", chunk-not-thread scoring,
   auto_pass source map, aggregate=min.
