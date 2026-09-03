# MLECU: Project Context & Status
_Last updated 2026-06-26. The canonical "where things stand + what's next" report; also the session handoff._

## Snapshot
MLECU = AI-assisted automotive ECU-tuning system on a self-hosted ML stack (Dell PowerEdge T630 `syedlab` + RTX 3090). A fine-tuned LLM reasons/diagnoses; **deterministic, hard-clamped, human-reviewed algorithms make every actual ECU change, the LLM never writes ECU values directly** (the safety invariant). Test car: 2005 Forester XT, JDM EJ20X swap, idles poorly. Repo: `~/Shared/Computing Projects/MLECU/`, private remote `directsyed/MLECU`.

---

## ✅ DONE (timeline)

**Bootstrap (Jun 22)**: repo structure, layered `CLAUDE.md`, `context/` (purpose, hardware-state, principles), `decisions.md`, `PROGRESS.md`, `sessions/`. Domains: `infrastructure/`, `ml/`, `car/`.

**GPU / server bring-up (Jun 22), synthetic side closed out**
- 1× HP-OEM RTX 3090 live (driver 580 / CUDA 13). 2nd card (Zotac 3090 Ti) blocked on power/clearance + CPU2.
- Closed-loop **fan controller** (`infrastructure/server/gpu-fan-control.sh` + systemd, deployed, validated under load).
- In-chassis **thermal soak**: VRAM peaked **100 °C** (vs 106 in the Omen) → **repad deferred**. Mem-junction via `gputemps` (BAR0 reader; `iomem=relaxed` set). Tools in `~/gpu-tools/`.

**Data pipeline (Stage A), LIVE + accumulating nightly (Jun 23–26)**
- Config-driven corpus pipeline (`ml/data-pipeline/`), mirrors the Hardware Parser conventions. **~910 docs** in `data/corpus.sqlite`.
- Sources: `romraider_defs` (333 ECU defs) · `romraider_logger` (219 SSM2 telemetry params) · `rusefi_docs` (327 theory) · `forum_legacygt` (27 threads + bounded auto-discovery) · `ecu_docs` (MegaSquirt MegaManual fundamentals) · `local_pdf` (ready for owner FSMs/books).
- **`tier`**: 883 `reference` (trusted) + 27 `community` (noisy), the split that keeps the judge non-circular.
- **Daily systemd timer** (`mlecu-corpus`, 04:30) + **Discord notifier** (per-run summary).

**Decisions locked (`decisions.md`)**
- RAG-vs-fine-tune deferred to a held-out eval; corpus serves both. FT-set sizing **500–2k**, quality > quantity.
- **Judge: non-circular**, a strong *general* model grounds `community` docs against the `reference` tier; never trained on what it filters; **deferred to the 48 GB (2×3090) setup** (~32B Q5/Q6).
- Algorithm layer = deterministic + hard-clamped; PID note recorded (idle = feedforward, iterative loop = bounded-integral, boost Stage-3 = real PID).
- Flash tool = Washinglee Openport 2.0 Rev-E clone; wideband target = AEM 30-0300 (controller-in-gauge; logs into RomRaider as one synced log).

---

## 🔄 NOW: passively accumulating (no action needed)
Corpus grows nightly: forum discovery finds new EJ/tuning threads, git sources auto-pull, Discord reports each run. Drop owner FSM/book PDFs into `data/raw/pdfs/{fsm,books}/` anytime → auto-ingested next run.

---

## ⏭️ NEXT: buildable NOW (NOT gated on the 2nd GPU or wideband)
1. **★ Deterministic algorithm + safety + sim layer (`car/`)**: the prime next build, fully data-independent:
   - `car/safety/`: the hard clamps (±3% VE/iter, timing ceilings, knock auto-abort, fuel-before-timing, AFR floor, boost gating) as pure, fuzz-tested functions.
   - `car/logging/`: RomRaider-CSV parser + (airflow/load × rpm) binning (schema known from the 219 ingested logger params).
   - `car/algorithms/`: the idle global-scalar algorithm (injector-latency → global scale → MAF rescale).
   - `car/simulation/`: a synthetic **MVEM** seeded with the known EJ20X/EJ255 mismatch + a convergence harness proving the loop drives trims → ±5% with **zero clamp violations**, all offline.
   - Real car logs slot into the same harness for *validation* later. Design in `car/{algorithms,safety,simulation}/README.md` + `decisions.md`.
2. **Corpus breadth (optional/passive)**: NASIOC forum source; more MegaManual pages; owner PDFs when acquired.
3. **Judge design (no GPU)**: draft the scoring rubric + reference-tier grounding/retrieval; actual judging waits for 48 GB.

---

## ⛔ BLOCKED: waiting on hardware (you)
- **2nd GPU** (3090 Ti via CPU2 + power, or another 3090) → **48 GB** → stand up the **LLM judge** (Qwen-32B), then the pilot **QLoRA fine-tune** + the **RAG-vs-fine-tune eval**.
- **Wideband (AEM 30-0300) + Openport clone** → Stage 1–2 **car logging** → real tuning data → *validates* the algorithm layer + becomes the highest-value training data.
- **Chassis fans** (being sourced) → re-soak → settle the repad question.

---

## Where things live / how to run
- **Corpus pipeline:** `ml/data-pipeline/`: `PYTHONPATH=. .venv/bin/python -m corpus_pipeline.cli --once` (or `--status`). Config: `config.yaml`; secrets (Discord webhook): `secrets.env`. Daily timer: `systemctl --user list-timers mlecu-corpus.timer`.
- **Algorithm layer (pending):** `car/{logging,algorithms,safety,simulation}/` scaffolds.
- **Tools:** `~/gpu-tools/` (gputemps, memtest_vulkan). **Fan service:** `gpu-fan-control` (system unit).
- **Docs:** `decisions.md` (the why) · `PROGRESS.md` (perf numbers over time) · `context/` (vision, live hardware state, principles) · `sessions/handoffs/`.

## External note
The **Hardware Parser** deal-scraper (separate project) had a stale `Computing Work` path in its systemd units (a pre-existing folder-rename mismatch, unrelated to MLECU), fixed this session; its hourly Discord alerts are back. Its `CLAUDE.md` still references the old path, worth fixing when next in there.
