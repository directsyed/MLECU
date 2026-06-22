# MLECU Bootstrap Package — How to use this

This folder contains everything Claude Code needs to initialize the **MLECU** project on your T630, loaded with full current context.

## What's here

```
MLECU-bootstrap/
  BOOTSTRAP-BRIEF.md          ← the entry point; hand this to Claude Code first
  raw-context/
    project-purpose.md        ← what MLECU is + execution methodology (soft foundation)
    hardware-state.md         ← current server/GPU/PSU/CPU state (as of June 19, 2026)
    principles.md             ← verification, testing, negotiation, flash discipline, your working style
    ARCHITECTURE.md           ← recommended structure (overridable proposal)
    open-questions.md         ← the upfront interview questions
```

## How to deploy it

1. **Get this folder onto the T630.** Easiest: copy the whole `MLECU-bootstrap/` folder into your home dir on the server (e.g. via the Samba share or scp), so it sits at something like `~/MLECU-bootstrap/`. (Keep it separate from the repo root `~/MLECU/` that Claude Code will create.)

2. **Start Claude Code in your home directory** on the T630.

3. **Point it at the brief.** Tell it something like:
   > "Read `~/MLECU-bootstrap/BOOTSTRAP-BRIEF.md` and follow it. It will tell you to read the raw-context files, then interview me, then build the MLECU project."

4. **Claude Code will then:** read the brief → read all raw-context files → (optionally skim the old June 11 files if you place them) → **interview you upfront** → build the project structure / CLAUDE.md hierarchy / decisions.md / PROGRESS.md / sessions/ (restructuring from the recommendation as it judges best) → `git init` and make an initial commit → report what it built.

## Key things baked in (so you don't have to repeat them)

- **Repo name: MLECU**, root `~/MLECU/`.
- **One repo, two domains** (infra + car) + ML bridge. Scraper stays external.
- **Option B:** Claude Code authors its own CLAUDE.md files by reading context + interviewing you — you don't pre-write them.
- **Upfront interview** before building.
- **Git repo**, frequent commits.
- **Resume/portfolio logging** is a first-class requirement (PROGRESS.md + performance numbers over time).
- **Self-written session handoffs** replace your manual .md-into-folder process.
- **Answer mode = tech-domain only** (declines non-tech).
- **The plan is a soft foundation** — Claude Code is explicitly told it may modify or replace the approach (logging reasoning), but may NOT contradict the facts or remove the safety architecture (LLM never writes ECU values; deterministic clamps execute).

## The two older files (optional)

If you want Claude Code to have the June 11 `master-context.md` and `bootstrap-architecture.md` for historical reference, drop them somewhere it can read (e.g. `~/MLECU-bootstrap/old/`). They're treated as superseded — useful for archaeology, but the raw-context files here are authoritative and current.
