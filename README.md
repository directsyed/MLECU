# MLECU

An AI-assisted ECU tuning system for a Subaru engine swap, built on a self-hosted ML stack.

A fine-tuned LLM reads OBD2 telemetry, diagnoses what the engine is doing, and proposes
calibration changes. It never writes a single ECU value. Every change is executed by
deterministic algorithms with hard bounds, checked against a stock ROM, and reviewed by a human
before anything reaches the car. Flexible diagnosis, provable execution.

The test vehicle is a 2005 Subaru Forester XT running a JDM EJ20X on an ECU calibrated for the
2.5-litre EJ255 it replaced. Higher compression, smaller displacement, wrong map. The first
milestone is making it idle and drive correctly. The compute half, a Dell PowerEdge T630 with
RTX 3090-class GPUs, exists to serve the automotive half: corpus curation, fine-tuning, and
inference.

## Where it stands

The pipeline has tuned the car. Three ROM writes so far, each verified byte-exact against the
image the tooling intended to produce.

| | |
|---|---|
| Fuel | Solved. Fuel trim went from roughly +30% to under 3% across every measured airflow band. |
| Root cause | The MAF transfer curve under-reports airflow, progressively, peaking around +37%. One fault, three symptoms: lean fuelling, a mis-indexed ignition map, and open-loop enrichment that never triggered. |
| Ignition | A retard map is built and audited, waiting on hardware. The engine had spent its entire knock-adaptation budget: IAM sat at zero for 52 seconds on the last drive. |
| Blocked on | The J2534 flash interface failed at the start of a write. The ECU was untouched and the car runs. |

Performance history, with dates and conditions, is in [PROGRESS.md](PROGRESS.md).

## The safety architecture

This is the part that matters, and it is not a convention that can be relaxed under deadline.

The LLM proposes. It cannot write. Every proposal passes through a clamp pipeline that bounds
each edit against limits held in reviewed configuration: per-iteration rate limits, absolute
ceilings, cumulative envelopes measured against the archived stock ROM, and a hard abort on
knock. Clamps are pure functions with property-based tests, so the bounds are provable rather
than asserted. Anything a clamp modifies or refuses is recorded, because an audit trail is itself
a safety property.

Two rules have survived contact with the car. Nothing may relax a bound based on a claim the
proposal makes about itself, since a future model is just another proposal producer; exemptions
are verified against live table values instead. And an in-memory guarantee that does not survive
storage encoding is not a guarantee, a lesson learned when a float32 rounding boundary quietly
broke a monotonicity promise on its way into the ROM.

Details in [car/CLAUDE.md](car/CLAUDE.md) and `car/ecutune/safety/`.

## Layout

| Path | Contents |
|---|---|
| `car/` | The ECU project: log parsing, tuning algorithms, the safety clamps, the ROM write path |
| `ml/` | Corpus pipeline, LLM-judge curation, fine-tuning, inference, eval harness |
| `infrastructure/` | Server, GPUs, power, networking, thermal monitoring |
| `context/` | Vision and methodology, live hardware state, operating principles |
| `docs/` | Roadmap, open checklist, design and plan documents |
| `sessions/handoffs/` | Session-to-session continuity notes |
| `PROGRESS.md` | Reverse-chronological progress with recorded performance numbers |
| `decisions.md` | Append-only decision log, including the ones that turned out wrong |

## Notes on reading this repo

`decisions.md` keeps failed predictions rather than deleting them. A prediction that the MAF
correction would reduce knock is recorded alongside the drive data showing it did not. Withdrawn
hypotheses stay withdrawn in place. That is deliberate: the reasoning trail is worth more than a
clean record, and a project that only documents its successes teaches nothing.

The `CLAUDE.md` files are working context for the AI agent that assists on this project. They are
part of how the repo is built, not documentation of it.
