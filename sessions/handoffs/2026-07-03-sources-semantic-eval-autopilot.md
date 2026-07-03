# 2026-07-03 — Build spec, source expansion, semantic layer, sim-eval (autopilot run)

Delta since the 2026-06-27 handoff. Syed directives this stretch: (1) lock the real Forester build
spec; (2) **never pre-prioritize a tuning lever — the data sets priorities**; (3) **universal-first**:
the framework foundation is the universal channel/table vocabulary, Subaru layers on top; (4) add
every corpus source; (5) autopilot through the queue, **stopping before the judge design session**
(his learning thread).

## What changed
- **Build sheet locked** (`car/build-sheet.md`): OEM 2005 FXT manifold+injectors(+harness) on the
  FXT ECU (injectors ~500cc side-feed, NOMINALLY matched — a prior, not a verified fact), TGV
  deleted, intake-AVCS live / exhaust deleted, fully catless 3" (04-21 STI up-pipe, no EGT sensor
  → codes), 9.5:1 EJ20X on the 8.4:1 EJ255 ROM, **4EAT**, 93 oct. Sim re-seeded: all fuel levers
  live, neutral split (0.34/0.33/0.33) — idle-point degeneracy means idle data can't separate them.
- **Corpus expansion** (`ml/data-pipeline`): 6 forum boards live — legacygt + **speeduino, msextra,
  romraider.com** (one generic phpBB engine; romraider seeded with the 2005 FXT 4EAT stock-ROM
  thread) + **subaruforester.org, iwsti.com** (one generic XenForo engine; VerticalScope ~25s/page →
  tight caps, nightly accumulation). **NASIOC built but cookie-gated** — its CF managed challenge is
  headless-proof (verified hard); drop a home-browser cf_clearance into
  `data/raw/.cf-cookies/nasioc.json` (same public IP ⇒ valid) and the timer auto-activates it.
  Plus: **tunerstudio_ini** (55 cross-platform defs), OBD-II PIDs page, AEM 30-0300/0310 manuals.
  Corpus ~1,026+ docs. 27 pipeline tests green.
- **Semantic table layer** (`car/ecutune`): algorithms/clamps speak only semantic IDs
  (`fuel.injector_flow`, `sensor.maf_transfer`, ...); `ecutune/platforms/` adapters own platform
  names — `subaru_ecuflash` (A2WC400x names + VARIANTS for per-def drift) + `tunerstudio` (proof of
  the seam). Future ROM reader resolves via `semantic_id()`, write bridge via `platform_name()`.
- **Sim-generated eval** (`ecutune/evals/` + `ml/eval/data/sim_cases_v1.jsonl`): MVEM extended
  (leak_air_g, air_scale) → 7 seeded faults → two-point datalog prompts (universal vocabulary) →
  scored vs seeded truth with acceptable-sets for the honest leak-vs-latency degeneracy.
  **v1: rules 85.7% top1 / 100% acceptable; random 18.6% / 25.7%.** LLM evaluee plugs into the
  same JSONL contract. 40 car tests green.
- **Model policy** (decisions.md): re-verify the latest model AT EXECUTION TIME (Qwen2.5-32B plan
  was stale; Syed's catch). As of 2026-07: judge = **Qwen3.6-35B-A3B @ Q8** (MoE offload fits the
  single 3090 + 32GB TODAY); fine-tune pilot base = Qwen3.6-27B. **Q6 min / Q8 preferred** (Syed).
  RAM spec for his parser: **32GB DDR4-2400 ECC RDIMM 2Rx4 PC4-19200** (prices rose; opportunistic).

## Open / waiting on Syed
- **ROM read** (Openport, read-only) → ROM ID + real calibration → reseed sim + pre-flight analysis.
- **NASIOC cf_clearance cookie** (home browser export). **Books** → `data/raw/pdfs/books/`.
  **ROM/log attachments** (need forum accounts) → `data/raw/roms/`.
- Hardware: BIOS 2.5.4→≥2.5.7 (before CPU2), chassis fans, wideband + FT232RL cable, RAM watch.

## Next (queue head)
- **Judge design session — Syed's learning thread, deliberately NOT auto-built.** Rubric,
  reference-grounding/retrieval, extraction schema, calibration labels; then the judge harness with
  a stub scorer; Qwen3.6-35B-A3B @ Q8 serving on the 3090 when ready. Chunking is a prerequisite
  (largest community doc = 82.5k tokens).
- Then: LLM-evaluee runner for the sim-eval; XenForo node expansion; pre-flight plan execution
  (already drafted, pending his ROM read).
