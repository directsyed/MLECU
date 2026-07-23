# Learning Queue — walkthroughs Syed will take, in full, when time allows

Standing rule: anything flagged "good learning opportunity" lands HERE, not just in chat.
Each entry = what it is, why it matters, where the code lives. Teaching pattern that works:
scaffold + TODO comments + acceptance-test file + Java/C idiom translations + REPL (see
memory: syed-rag-learning-progress). Check items off as they're actually walked through.

- [ ] **RAG piece 2+3 walkthrough** — `retrieve()` + arm-B injection in
  `ml/eval/harness/retrieval.py` / `arms.py`. Syed built `query_terms` solo; Claude finished
  the rest overnight 2026-07-08. Walk line-by-line: dataclass, ro-connection, FTS5 MATCH,
  bm25() lower-is-better, snippet(), the single-variable arm discipline.
- [ ] **BM25 → embeddings upgrade** — when dedupe/embeddings land: what vectors are, cosine
  similarity, why semantic beats lexical for paraphrase, the swap behind the same seam.
- [ ] **E1v2 design: breaking the leak/dead-time degeneracy** — MVEM sim, why a battery-
  voltage sweep separates injector-latency faults from vacuum leaks physically, how the case
  generator encodes multi-condition-logging doctrine. `car/ecutune/evals/`. (Being built
  autonomously 2026-07-09 night — walkthrough of what was built + the physics.)
- [ ] **Synthesis prompt iteration** — why "never invent" produced 0 pairs on wiki text and
  1.8/doc on manuals; grounding vs hallucination tension; how the editorial review loop
  (Claude over Qwen drafts) tightens the prompt.
- [ ] **Eval harness architecture end-to-end** — arms/grammar-pinned enums/crash-safe JSONL/
  file-path scoring import/determinism checks. Why each choice defends the experiment.
- [ ] **Thinking-budget starvation postmortem** — why case 43 crashed the overnight run:
  reasoning + answer share one token budget; tolerant-parse-as-miss semantics.
- [ ] **QLoRA fine-tune (upcoming)** — when arms C/D train: what LoRA adapters are, why
  4-bit quantization, hyperparameters. LEARNING-PRIORITY: Syed drives this one live.
- [ ] **Single-token roadmap through a transformer** (requested 2026-07-22, QLoRA night):
  trace ONE token end-to-end — tokenizer ID -> embedding row lookup -> per-layer journey
  (attention Q/K/V mixing vs per-token MLP, residual stream, dims expanding 4096->14336->4096)
  -> final logits matrix -> softmax -> sampling -> KV cache role in the next pass. Builds on
  the neurons/weights/matrix-shapes groundwork laid in the 07-22 session.
- [ ] **E2 sampling-skew postmortem** — Syed's own catch (2026-07-09): ORDER BY id sampled
  first-ingested docs; deterministic-hash scattering; why probe MIX matters as much as
  probe accuracy.
- [ ] **prepare.py walkthrough** (built by Claude on 07-22 delegation): the structural
  gate, stratified split internals (dict grouping, seeded shuffle, per-stratum rounding),
  chat-transcript format, why train-shape == serve-shape.
- [ ] **Embeddings retrieval pipeline (retrieval-v2)**: BGE-M3, contrastive training,
  cosine similarity as normalized dot product, the RRF fusion math, why the index is 23MB,
  hybrid-vs-BM25 failure modes. Code: ml/eval/harness/embed_index.py + retrieval.py.
- [ ] **QLoRA train.py line-by-line**: BitsAndBytesConfig knobs, LoraConfig targets,
  gradient checkpointing, paged 8-bit Adam, the smoke gate, reading loss curves.
- [ ] **DISCUSSION: on-vehicle context sizing** (Syed, 07-22): long raw context vs rolling
  summarized session file for iteration memory; 68 KiB/token KV math; design at Stage C.
