# car/simulation/

Offline test harnesses for the algorithm layer (Stage 4 — after Stage 2/3 logs exist).

**Status:** ✅ **MVEM + convergence harness BUILT (offline)** in `../ecutune/simulation/` — a mean-value engine model seeded with the EJ20X-vs-EJ255 mismatch + the full sim→log→bin→propose→clamp→apply loop, asserting zero clamp violations, ±5% convergence, and determinism. The log-replay-on-real-logs and rusEFI SIL pieces remain for later.

**Will contain:**
- the **log-replay harness** — retroactively test algorithms against Syed's own Stage-2/3 logs ("would the algorithm have proposed what I actually did?"),
- a **mean-value engine model (MVEM)** fit to the logs for convergence testing,
- **rusEFI software-in-the-loop** for exercising the write path safely.
