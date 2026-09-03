# ml/eval/

Evaluation, **the gate that authorizes the expensive EPYC build.**

**Status:** the **sim-generated diagnostic eval is LIVE** (v1, 2026-07-03); the forum-derived
held-out set comes later (post-judge, so curated pairs exist to hold out).

## Sim-generated eval (contamination-free, universal)

Known faults are seeded in the `car/ecutune` MVEM (MAF transfer error, injector flow/latency
mismatch, vacuum leak, healthy), rendered as a **two-operating-point datalog summary** in the
universal channel vocabulary (MAF g/s, fuel trim %, wideband AFR; no platform names), and the
evaluee must name the root cause. Because the fault is *seeded*, ground truth is exact, the set is
infinitely regenerable (new seed = new set; no fine-tune can have memorized it), and the two-point
design encodes the multi-condition-logging doctrine: constant-fraction trim = scaling fault;
trim that shrinks with airflow = constant-absolute fault (leak/dead-time). Leak-vs-dead-time stays
degenerate without a battery-voltage sweep (true on the real car too), scored via acceptable-sets.

- **Cases:** `data/sim_cases_v1.jsonl` (70 = 10/fault × 7 faults, seed 0). Contract per case:
  `prompt` in → one fault id from `choices` out; `fault`/`acceptable`/`magnitude_pct` for the scorer.
- **Generate:** `cd car && PYTHONPATH=. .venv/bin/python -m ecutune.cli --generate-eval-cases 10`
- **Score a baseline:** `... -m ecutune.cli --score-sim-eval ../ml/eval/data/sim_cases_v1.jsonl --baseline rules`
- **v1 baseline numbers (bracket the eval):** rules **85.7% top1 / 100% acceptable**;
  random **18.6% / 25.7%**. The LLM evaluee must at least match rules; beating it means
  reasoning past the two-point signatures.

Implementation lives in `car/ecutune/evals/` (fault taxonomy, generation, scoring, tested there);
this directory owns the **artifacts** + the future **LLM evaluee runner** (serve the model, feed
`prompt`, parse the id, `score()`), plus the RAG-vs-fine-tune comparison when both exist.

**Will also contain:** the forum-derived held-out eval (real `(symptoms → diagnosis)` pairs held
out of training), and the **RAG-vs-fine-tune comparison harness**: a pilot fine-tune must **beat a
RAG baseline** here before any big hardware spend. Treat as first-class infrastructure.

**Learning-priority, TEACH** (root CLAUDE.md): metric choices, pass thresholds, fault-taxonomy
extensions, and the RAG-vs-fine-tune design are Syed's calls; the deterministic generator/scorer is
build-priority scaffolding.
