"""RAG-vs-fine-tune eval harness — the gate that authorizes the EPYC spend (ROADMAP Phase D).

Arms (same base model, same quant, temp 0, grammar-constrained JSON, 2 runs for determinism):
  A = base model alone            B = base + RAG (BM25 over judge-kept reference chunks)
  C = fine-tuned (pairs-gated)    D = fine-tuned + RAG
This package currently implements A and B + the E1 diagnostic eval. E2 (exact-value probes)
lands next; C/D activate when the pair corpus exists.

Eval DESIGN decisions (bars, margins, metrics) are Syed-owned and pre-registered in DB meta
before any arm runs for the record — this code is scaffolding, not policy.
"""
