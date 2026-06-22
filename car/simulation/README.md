# car/simulation/

Offline test harnesses for the algorithm layer (Stage 4 — after Stage 2/3 logs exist).

**Status:** not started.

**Will contain:**
- the **log-replay harness** — retroactively test algorithms against Syed's own Stage-2/3 logs ("would the algorithm have proposed what I actually did?"),
- a **mean-value engine model (MVEM)** fit to the logs for convergence testing,
- **rusEFI software-in-the-loop** for exercising the write path safely.
