# 2026-07-04 — Context report for the next agent (GPU2 validated; next = cookies → judge)

Session ended on context budget. This is the handoff. Read `context/` + the recent handoffs to
restore full state; below is the delta + the exact next steps Syed named.

## Where the project is (built + working)
- **Corpus pipeline** (`ml/data-pipeline/`): 6 forum boards live (legacygt, speeduino, msextra,
  romraider, subaruforester, iwsti) + cross-platform defs (romraider_defs, tunerstudio_ini) + OBD-II
  PIDs + wideband manuals. **`local_pdf` now ingests PDFs AND EPUBs** (added this session). ~1,026+
  docs, growing nightly via systemd timer. Tests green.
- **car/ecutune/** (offline deterministic tuning layer): safety clamps (property-tested), RomRaider
  log parser + binning, bounded-integral idle algorithm, MVEM + convergence harness, **semantic
  table layer** (universal IDs + platform adapters), **sim-generated diagnostic eval** (v1, 70 cases,
  rules 85.7% / random 18.6%). 40 tests green. Convergence PASS.
- **Hardware Parser** fully recovered this session to `~/Shared/Computing Projects/Hardware
  Parser_RECOVERED/` (44 files from Claude transcripts) + `ARCHITECTURE.md`.

## This session's hardware work — 2nd GPU IN + VALIDATED
- **Zotac RTX 3090 Ti (450W) installed** alongside the OEM 3090. GPU0 = 3090 @04:00.0, GPU1 = 3090 Ti
  @83:00.0. Both enumerate.
- **Tooling made multi-GPU** (was single-GPU — a real safety gap): `gpu-fan-control.sh` drives off
  MAX core across both cards; `soak-logger.py` logs per-GPU columns (compact ≤80-col console) + aborts
  on the hottest card. **DEPLOY GOTCHA: the fan service runs `/usr/local/sbin/gpu-fan-control.sh`, a
  COPY — repo edits must be `sudo cp`'d there + service restarted.** Same for the new powerlimit unit.
- **Thermals (all in-spec):** Ti solo 30-min = 92–94 °C VRAM @446W, no throttle, no repad needed. **Dual-card
  20-min = 3090 VRAM 100–102 °C, Ti 92–94 °C**, fans near max (~4680 RPM), inlet 21 °C. The chassis
  handles ~780W fine (dual only added ~2 °C to the 3090); the **3090's OEM pads are the limiter**.
- **Undervolt-by-power-cap:** `nvidia-smi -pm 1` (persistence — REQUIRED or the cap silently resets on
  idle) then `-pl 300` (3090) / `-pl 400` (Ti). Built **`infrastructure/server/gpu-powerlimit.service`**
  (boot-time pm+pl; deploy to `/etc/systemd/system/`, `enable --now`). Syed installed it.
  - **Result:** 3090 VRAM 102→98 °C. BUT the 300W cap **cut the 3090's memtest bandwidth ~800→~600 GB/s
    (~20%)** — GDDR6X draws fixed power the core cap can't touch, so it throttles memory. Ti @400W barely
    lost perf. **Repad the 3090 → then raise its PL back to ~340 to recover bandwidth.** For the batch
    judge workload the 300W hit is fine (overnight; the Ti carries the 32B model anyway).
- **OPEN: repad the 3090.** In-spec now but it's the 24/7 limiter; repad decouples temp from power so
  it can run full PL. Syed leaning yes. If he pulls it, get the AMP/FE GDDR6X pad-thickness map first.

## NEXT (in order, per Syed)
1. **NASIOC forum + RomRaider ROM harvester — BOTH BUILT, BOTH COOKIE-GATED (operational step).**
   - `forum_nasioc` (enabled, `require_cf_cookies`): needs a `cf_clearance` cookie from Syed's HOME
     browser (same public IP as the T630) at `data/raw/.cf-cookies/nasioc.json`. Confirmed the CF
     managed challenge is unbeatable headless — the cookie is the only path. Auto-activates once present.
   - **ROM binaries** (`--harvest-roms`, `rom_harvest.py`): RomRaider thread text is public but the
     `download/file.php` attachment 403s guests. Needs a phpBB session cookie at
     `data/raw/.cookies/romraider.txt` (see `ROM_HARVEST.md`). **The 2005 FXT 4EAT stock ROM
     (3B12504206) is attached to the seeded thread** — Syed's exact platform, one cookie away.
   - So step 1 is really: Syed provides the two cookies → run both. Next agent should confirm they work.
2. **The JUDGE (learning-priority — Syed drives, TEACH, don't auto-build).** The design session we've
   queued: 1–5 scoring rubric, reference-tier grounding/retrieval, `(symptoms→diagnosis→change→outcome)`
   extraction schema, calibration labels (Syed hand-labels ~50–100, measure agreement). Then the judge
   harness (`ml/curation/`): `State.pending_for_judge()` → score → `mark_judged()`; chunker first
   (largest community doc ~82k tokens). **Model (re-verify at run time): Qwen3.6-35B-A3B @ Q8** — MoE
   3B-active runs on the single 3090 + 32GB via llama.cpp expert offload; now that the 48GB (2×3090) is
   live it fits with headroom. Quantization floor: **Q6 min / Q8 preferred** (Syed).

## Open items / waiting on Syed
- Two cookies (NASIOC cf_clearance + RomRaider phpBB session). · ROM read of his own ECU (Openport,
  read-only) for the real sim seed. · Repad decision on the 3090. · RAM (32GB DDR4-2400 ECC RDIMM,
  opportunistic). · A book ingest was running at session end (`--sources local_pdf`) — verify it
  finished and check `--status` (EPUBs: Banish/Kirkpatrick/Cramer now supported).

## Key state / policy
- **Model choices re-verified at execution time**, never from training memory (Qwen2.5 plan was stale).
- **Don't pre-prioritize tuning levers — the data decides** (sim keeps all fuel levers live, neutral split).
- **Universal-first**: semantic vocabulary is the foundation; Subaru is adapter #1.
- Deploy gotchas: `/usr/local/sbin/` for the fan + powerlimit scripts (repo is source, must cp).
- Commit frequently to main (portfolio). Git history IS the resume.
