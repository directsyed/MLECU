# MLECU: PROJECT PURPOSE & EXECUTION VISION
**Authoritative as of June 19, 2026.** This is the most important context file. It describes what the project IS and how it's intended to execute. **Per the bootstrap brief §3, the execution plan here is a SOFT FOUNDATION; you (Claude Code) may modify or replace the approach if you judge better, but you may not contradict the facts or remove the safety architecture, and you must log material divergences in decisions.md.**

---

## 1. The vision

Build an **AI-assisted ECU tuning system** where:

- **OBD2 / ECU log data** (live engine telemetry: RPM, MAF, AFR/lambda, injector duty, timing, knock feedback, boost, coolant/IAT, fuel trims, etc.) feeds into
- a **fine-tuned LLM that serves as the reasoning and diagnosis layer**: trained on engine physics, tuning forum knowledge, professional tuning write-ups, and real before/after tuning data, which interprets the data, diagnoses problems, and proposes calibration changes, but
- **all actual ECU value changes are executed by deterministic, hard-clamped, human-reviewed algorithms.** The LLM is the brain that reasons; it NEVER writes values to the ECU directly.

**Why this split (critical design rationale):** It is not that LLMs "can't do math." It's that ECU table writes are safety-critical numerical outputs where *guaranteed precision and bounded behavior* matter, a wrong fuel or timing value can destroy an engine. Deterministic algorithms with hard clamps give provable bounds; an LLM's reasoning gives flexible diagnosis. You get both: flexible diagnosis, guaranteed-safe execution. **This separation is a HARD REQUIREMENT and may not be designed away.**

## 2. Target platform & scope

- Targets **standalone ECUs with open APIs** as the eventual write surface (where the deterministic layer can safely interface), and the OEM Subaru ECU for the initial real-car work via RomRaider/ECUFlash.
- **Dataset is Subaru-first: ~70% Subaru/EJ-platform, ~30% general engine management.** Other platforms only after the Subaru loop works.
- **Commercial trajectory exists**: this could become a product, but the first proof is Syed's own car. Syed is a mechanic by trade and will test on his own vehicles first.

## 3. The test vehicle (the ground truth)

**2005 Subaru Forester XT with a JDM EJ20X engine swap.** (NOTE: older project docs say "2004"; that is WRONG, it's a 2005.)

Key facts:
- **EJ20X**: 2.0L, JDM. Different displacement / VE / compression than the EJ255 the chassis ECU expects.
- **Factory drive-by-wire (DBW)**: the FXT was DBW from 2004 onward. The EJ20X's DBW throttle body is a natural fit; pedal commands the blade normally. (Older docs assumed cable throttle, WRONG.)
- VF48 turbo, 04–08 STI top-mount intercooler, catless, aftermarket downpipe with an unidentified unconnected O2 sensor/bung.
- **Exhaust AVCS deleted, oil ports blocked; cam timing mechanically retarded at the gears** to match the ECU's expectations (done by hand, documented swap procedure, NOT flashed).
- **ROM presumed bone stock** (the timing fix was mechanical, not flashed; no aftermarket tune suspected).
- **The car has never been driven by Syed. It idles, and idles poorly.** This is the starting problem.

**The ECU is 32-bit** (2005–2006 Subaru DBW family). EcuFlash has a dedicated read method for 05–06 FXT. RomRaider logging needs NO green-connector jumper on these. (Older "16-bit / Openport 1.3" discussion is DEAD, the 32-bit facts override it. 32-bit ECUs are regarded as reliable to flash with standard precautions.)

## 4. Why the car idles badly (current working theory)

A fresh swap idling badly is a **vacuum/boost leak until proven otherwise**: no tune fixes a leak, and a leak poisons every log. Beyond that, the dominant causes are **global scalars, not map cells**:
- **Injector scaling/latency** (the EJ20X injectors / the ECU's expectations mismatch)
- **Low-range MAF calibration** (the intake configuration differs from what the ROM expects)
- **The EJ20X throttle body is not the EJ255 part**, so airflow-per-degree differs from the FXT ECU's idle tables, a candidate global mismatch.

The legitimate insight: idle visits ~one cell of the map, so you can't "extrapolate a basemap from idle" cell-by-cell, BUT closed-loop fuel trims at idle expose the *global scalars*, and fixing those shifts the whole map toward sane. That's step one of every remote-tune workflow.

## 5. The staged execution methodology (SOFT FOUNDATION, refine freely)

This staged approach was designed to get the car safely from "idles badly" to "drives, with the algorithm layer running." **You may restructure this methodology if you judge a better engineering path, log your reasoning.**

**Stage 0. Mechanical truth (before any tuning).** Smoke/spray-test the entire intake tract (manifold gaskets, IC couplers, bypass plumbing, brake booster line, PCV). Confirm MAF matches housing. Verify base timing/cam marks after heat cycles. Compression/leakdown if convenient. **93 octane only, always** (the JDM EJ20X assumes 100 RON; octane is the safety margin under unknown fueling).

**Stage 1. Instrument + read.** Install a **wideband** (the project's ground-truth instrument; nothing proceeds without it). Get logging via the FTDI KKL cable (SSM2 over K-line). Read and archive the **stock ROM** (sacred, multiple backups before any write).

**Stage 2. Idle calibration loop (stationary).** Log idle + free-rev (no load): RPM, MAF g/s, AFR correction & learning, injector duty, timing, knock, coolant/IAT, wideband AFR. Combined trims beyond ±10% → correct **injector latency/scaling first, then low-range MAF**, reflash, re-log. Iterate until idle trims sit within ±5% and wideband agrees with commanded AFR. **Steal known-good scalar starting points from documented EJ20X-on-USDM-ECU swap threads** (legacygt.com, RomRaider forums) rather than deriving from scratch. **Every iteration (trims → change → result) is archived; these are literally training examples in the exact form the model needs.**

**Stage 3. Staged driving (only after Stage 2 converges).** Driving is eventually mandatory (you can't calibrate cells you never visit; no simulator substitutes for real VE), but incremental: closed-loop light cruise first (near-zero danger, ECU self-correcting) → progressively higher part-throttle load rows with wideband watched live → **boost is gated** (no boost until trims ±5%, wideband tracking, and boost control verified against the VF48; cap targets conservatively, overboost is the #1 way this combo grenades). Hard rules forever: knock feedback active = stop; AFR leaner than ~11.5:1 (λ≈0.78) at full boost = back out; fuel before timing; small steps.

**Stage 4. The algorithms take over (the actual product).** By Stage 3, Syed has manually done exactly what the deterministic layer will automate: read logs → bin to cells → propose bounded corrections → verify. Build:
- a **log-replay harness** to retroactively test algorithms against Syed's own Stage 2–3 logs ("would the algorithm have proposed what I did?"),
- a **mean-value engine model (MVEM)** fit to the logs for convergence testing,
- software-in-the-loop for the write path (e.g. rusEFI PC simulator).
- **Safety clamps codified from day one:** max ±3% VE/iteration, per-row timing ceilings, auto-abort on knock, fuel-before-timing, steady-state-before-transients. THIS is the deterministic execution layer the whole architecture is built around.

## 6. The data pipeline (SOFT FOUNDATION, refine freely)

Feeds the fine-tuned model. **You may redesign this; it's squarely in your domain.**

- **LLM-judge curation on the server's GPU:** a quantized ~30B model (the plan floated Qwen2.5-32B-Instruct Q4 via llama.cpp or vLLM) scores scraped tuning content 1–5 for substance/consistency and extracts structured pairs (symptoms → diagnosis → change → outcome). Keep ≥4; human spot-check ~5%. Runs continuously as a background workload.
- **Embeddings** for corpus dedupe/clustering (re-quoted posts bias toward popularity, not correctness).
- **Source whitelist (priority):** tuning books (Banish *Engine Management: Advanced Tuning*; Bell *Maximum Boost*; Heywood *IC Engine Fundamentals*); FSMs (2005 Forester FSM + JDM Legacy GT FSM for the EJ20X); the complete RomRaider wiki/definitions; forums (RomRaider, NASIOC engine management, legacygt.com, EJ20X swap goldmine, IWSTI, MegaSquirt/rusEFI for platform-agnostic theory); data artifacts (posted RomRaider logs, before/after ROM diffs, dyno threads with numbers).
- **Curation rules:** whitelist-only ingestion; per-chunk gates (contains numbers/tables/logs? author tenure? thread resolved? pure opinion → discard).
- **Target corpus: 10k–50k curated pairs / ~100–500MB clean text.** Pollution costs more than scale pays.

## 7. The fine-tuning + validation plan (SOFT FOUNDATION)

- **Pilot QLoRA fine-tunes (7B–14B)** once ~2–5k curated pairs exist, validates the full pipeline before any bigger spend.
- Build a **held-out eval set** and run the **RAG-vs-fine-tune comparison**: this sizes the final hardware. Endgame compute (the EPYC build, see hardware-state.md) is triggered ONLY when (a) a pilot fine-tune beats a RAG baseline on the held-out eval, AND (b) ambitions exceed 24GB VRAM. Don't scale hardware on faith; scale it on a passed eval.
- Longer-term ambitions reference 70B+ QLoRA and larger inference, but the pilot-beats-RAG gate comes first.

## 8. Open design question carried forward

Which open-source path for the eventual write layer: stay RomRaider/ECUFlash (OEM ECU) long-term, or plan a standalone (rusEFI) swap later? This affects how the deterministic layer's flash interface is designed. (Was flagged as a ~month-3 decision, not urgent, but it's yours to resolve as the architecture matures.)

---

## Reminder
The methodology, pipeline, and tooling above are scaffolding. The **facts** (vehicle config, ECU type, hardware, what's verified) are fixed. The **safety architecture** (LLM reasons, deterministic clamps execute, LLM never writes ECU values) is fixed. Everything else is yours to finalize, improve, or replace, with reasoning logged in decisions.md.
