# ml/curation/

The **LLM-judge** curation engine.

**Status:** not started, but its **input is ready**: the data pipeline writes gated docs to `../data-pipeline/data/corpus.sqlite` with `judgment_status='pending'`. The judge consumes `State.pending_for_judge()` (gate_status=`kept` AND pending), scores 1–5, and sets `judge_score` + `judgment_status='judged'`.

**Will contain:** the judge runner (plan: **Qwen2.5-32B-Instruct Q4** via llama.cpp/vLLM) scoring chunks 1–5 for substance/consistency, structured `(symptoms → diagnosis → change → outcome)` pair extraction (keep ≥4/5), ~5% human spot-check tooling, and embedding-based dedupe/clustering.

**Non-circular by design:** the judge is a strong **general** model (Qwen2.5-32B), **NOT trained on the corpus it filters**. It scores `community`-tier docs (forums) and **grounds them against the `reference` tier** (RomRaider defs/logger, rusEFI, MegaManual, FSM), retrieved at judging time, never baked in. `reference`-tier docs pass as trusted facts (light judging). Deferred to the **48 GB (2×3090)** setup. Full rationale in `../../decisions.md` (2026-06-26).

**Learning-priority, TEACH** (root CLAUDE.md): the LLM-judge is part of the ML stack Syed wants to learn. Explain the why, let him drive.
