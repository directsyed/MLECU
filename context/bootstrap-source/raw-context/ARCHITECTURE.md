# MLECU — RECOMMENDED ARCHITECTURE (a starting proposal)
**This is a PROPOSAL, not a spec.** Per the bootstrap brief, you (Claude Code) may restructure freely if you judge a better layout — log material divergences in decisions.md. The *ideas* below matter more than the exact tree.

---

## Core principles to preserve (even if you restructure)

1. **One repo, domain-partitioned.** Not multiple projects, not one flat blob.
2. **Layered CLAUDE.md.** A lean, always-loaded root `CLAUDE.md` that orients you and carries behavior rules + routing; heavier domain-specific `CLAUDE.md` files loaded only when working in that domain. This is what prevents context clutter — routine work in one domain shouldn't drag the whole project into context.
3. **Two real domains + a connective ML layer:** infrastructure/compute and the car ECU project, with ML bridging them (compute serves fine-tuning serves the car).
4. **Self-written session handoffs** in a `sessions/` directory.
5. **Append-only `decisions.md`** for traceable choices.
6. **`PROGRESS.md`** as a first-class portfolio/resume artifact (see bootstrap brief §6).
7. **The scraper is external** — referenced, not absorbed.

## Proposed tree

```
~/MLECU/
  CLAUDE.md                 # lean root: what MLECU is, how it's organized, behavior rules
                            #   (tech-only answer scope), routing to domains, the
                            #   read-latest-handoff / write-handoff instruction, the
                            #   "plan is soft foundation, you may change it" reminder,
                            #   and the safety-architecture hard constraint.
  PROGRESS.md               # reverse-chron portfolio log: built/improved, milestones,
                            #   performance numbers (evals, throughput, thermals, corpus stats)
  decisions.md              # append-only: decision + date + rationale (esp. divergences from plan)
  README.md                 # human-facing overview (also serves the portfolio)

  context/                  # cross-domain reference (the raw-context material, refined by you)
    project-purpose.md      # the vision + execution methodology (soft foundation)
    hardware-state.md       # live server/GPU/PSU/CPU/storage/network state (changes often)
    principles.md           # verification, testing, negotiation, flash discipline, working style
    market-intelligence.md  # pricing baselines, sourcing notes (optional split from principles)

  infrastructure/           # DOMAIN 1 — compute + server
    CLAUDE.md               # infra-domain context, loaded when working here
    server/                 # T630 configs, ipmitool fan control, BIOS notes, ZFS/HBA setup
    networking/             # WireGuard, Tailscale, netplan, DuckDNS, remote access
    monitoring/             # nvidia-smi logging, HWiNFO-equivalent, health/thermal capture

  ml/                       # CONNECTIVE LAYER — the ML stack
    CLAUDE.md
    data-pipeline/          # scraping-consumer? curation, LLM-judge, embeddings, dedupe
    curation/               # LLM-judge scoring, structured-pair extraction
    finetuning/             # QLoRA configs, dataset prep, training runs
    inference/              # serving (llama.cpp/vLLM), quantization
    eval/                   # held-out eval set, RAG-vs-finetune comparison harness

  car/                      # DOMAIN 2 — the ECU project (most isolated domain)
    CLAUDE.md               # ECU-domain context + the SAFETY constraints front-and-center
    ecu/                    # flash tooling interface, ROM defs, RomRaider/ECUFlash notes
    logging/                # SSM2 log capture, parsing, the telemetry schema
    dataset/                # the Subaru-first tuning corpus, the 70/30 split, archived tuning iterations
    algorithms/             # the DETERMINISTIC tuning layer — bin-to-cell, bounded corrections
    safety/                 # the hard clamps: ±3% VE/iter, timing ceilings, knock auto-abort,
                            #   fuel-before-timing, steady-before-transient. THE write-path guard.
    simulation/             # log-replay harness, MVEM, rusEFI software-in-the-loop

  sessions/
    handoffs/               # YYYY-MM-DD-<topic>.md — you write these (read latest at session start)

  archive/                  # (optional) the superseded June 11 master-context.md +
                            #   bootstrap-architecture.md, kept for history only
```

## Notes on the proposal

- **The `car/safety/` + `car/algorithms/` separation is deliberate** and reflects the hard architectural requirement: the LLM reasons (its outputs are proposals), the deterministic algorithms with codified clamps execute. Keep this separation no matter how else you restructure. The safety clamps should be testable code, not prose.
- **`ml/eval/` is strategically important** — the RAG-vs-finetune comparison on a held-out eval is the gate that authorizes the expensive EPYC hardware build. Treat eval infrastructure as first-class, not an afterthought.
- **`context/hardware-state.md` will change the most** — it's the live state of an evolving build. Keep it current; it's what lets you reason correctly about what GPU/PSU/CPU reality you're actually working with.
- You may prefer to **split `principles.md`** (operational lessons) from a `market-intelligence.md` (pricing/sourcing) — minor, your call.
- If you decide a different top-level partition serves better (e.g., separating "operations" from "research," or pulling `ml/` apart differently), do it — just preserve the always-loaded-lean-root + domain-CLAUDE.md pattern and the safety separation, and log the change.

## What the root CLAUDE.md must contain (regardless of structure)

- **Identity:** you are the MLECU agent; what MLECU is (one paragraph).
- **Answer-mode behavior:** answer technology-domain questions using project context; **decline/redirect non-tech topics** (health/fitness, drugs, general life, legal/financial advice).
- **Routing:** pointers to domain CLAUDE.md files; read the relevant one when working in that domain.
- **Continuity:** read the latest `sessions/handoffs/` at session start; write a dated delta handoff at session end.
- **Portfolio:** maintain `PROGRESS.md`; record performance numbers as they arise; commit frequently with good messages.
- **The soft-foundation reminder:** the plan in `context/project-purpose.md` is scaffolding you may change (with logged reasoning) — but the facts and the safety architecture are fixed.
- **The safety hard constraint:** the LLM never writes ECU values directly; deterministic clamped algorithms execute all changes.
