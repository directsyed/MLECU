# MLECU — OPEN QUESTIONS FOR THE UPFRONT INTERVIEW
**Per the bootstrap brief §10, conduct this interview with Syed BEFORE building the project structure.** Read all other raw-context files first so your questions are informed. Add your own questions as they surface — this list is a floor, not a ceiling. Group and prioritize as you see fit; don't dump all of them at once if a more natural flow exists.

---

## A. Project structure & your own setup
1. Confirm the repo root: `~/MLECU/` on the T630 — correct? (Bootstrap assumes this.)
2. Are you (Claude Code) running on the T630 itself right now, with the repo to be created locally there? (Expected yes.)
3. Should the two superseded June 11 files (`master-context.md`, `bootstrap-architecture.md`) be placed into an `archive/` dir for history, or left out of the repo entirely?
4. Any preference on git remote (push to GitHub/GitLab for the portfolio, or local-only for now)? If remote, public or private? (Portfolio visibility may favor a public repo eventually — but the repo contains hardware/network specifics; consider what's exposed.)

## B. Immediate hardware bring-up (in progress — may already be resolved by the time you read this)
5. Did the 3090 enumerate in the T630? (`lspci | grep -i nvidia`, then driver install, then `nvidia-smi`.) What does `nvidia-smi` show?
6. Were the fans quieted via ipmitool? What fan % / mode are you running?
7. Has the in-T630 gpu-burn + memtest_vulkan soak run yet, and what was the **memory-junction temp**? (This settles the repad decision for the OEM 3090.)
8. **Confirm the installed PSUs are the 1100W pair**, not the old 495W units.
9. Is the OEM 3090 the same card as the "$1,100 HP OEM 3090" in prior context, or a distinct second card? (Affects GPU count + dual-GPU planning.)

## C. Hardware roadmap decisions
10. Dual-CPU: proceeding with **2× E5-2660 v4 + standard heatsinks** (the revised pick), or sticking with 2680 v4? And has the BIOS update (off the v3) happened yet — since v4 needs it first?
11. 3090 Ti path: waiting for CPU2 (→ slot 6) to bench it, or getting a PCIe riser to float it past the SW RAID header in slot 3? Or benching it some other way?
12. Storage: when does the ZFS pool get stood up (H730 → HBA), and what's the first drive set? Is the Z800-data rsync backup a near-term task?

## D. ML pipeline & priorities
13. What's the **first ML task** you want stood up on the server — the LLM-judge curation engine (Qwen2.5-32B Q4 via llama.cpp/vLLM), or something else first?
14. Is there any existing scraped/curated data yet, or does the corpus start from zero?
15. Model/framework preferences for fine-tuning (the plan floats QLoRA on 7B–14B pilots) — any specific base models you favor, or leave it to be decided at pilot time?
16. Inference serving preference: llama.cpp vs vLLM vs something else, or evaluate when you get there?

## E. The car
17. Current real-world status of the car beyond "idles poorly" — any logging done yet, wideband installed, KKL/Openport in hand? (Hardware-state lists these as planned/ordered — what's actually arrived?)
18. ROM ID from a first FreeSSM/RomRaider connection — captured yet? (Locks the ECU definitions + flash-tool choice.)
19. The carried-forward design question: stay RomRaider/ECUFlash (OEM ECU) long-term, or plan a standalone (rusEFI) swap? This shapes how the deterministic write-layer interface is designed. (Was a ~month-3 decision — your call when to force it.)
20. Telemetry schema: do you have a preferred set of logged channels / format, or should the schema be designed fresh from the Stage 2 logging plan?

## F. Workflow & cadence
21. How do you want field decisions (made via the chat assistant on your phone — Marketplace finds, garage moments) folded back in? (Prior model: a one-line update at the next Claude Code session start. Keep that?)
22. Cadence for PROGRESS.md / portfolio updates — every session, weekly, milestone-based?
23. Anything about the answer-mode scope you want to tighten or loosen beyond "tech-domain only, decline non-tech"?

---

After the interview, build the structure, author your CLAUDE.md hierarchy + decisions.md + PROGRESS.md + README + sessions/, restructuring from the recommendation as you judge best (logging divergences), then `git init` and make a clear initial commit. Confirm to Syed what you built and why.
