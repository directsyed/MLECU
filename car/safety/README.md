# car/safety/ — THE WRITE-PATH GUARD

**This is the hard safety boundary of the entire project.** The LLM never writes ECU values; everything that changes an ECU value passes through codified, **testable** clamps defined here.

**Status:** ✅ **BUILT (offline)** — implemented as pure, fuzz-tested clamps in `../ecutune/safety/` (`clamps.py` + `pipeline.py`). `apply_proposal()` is the only function that writes a Table; a source-scan meta-test enforces it. hypothesis property tests prove the ±3% bound (sign-preserving), idempotency, knock⇒empty, and the AFR floor at boost.

**Will contain — clamps as testable code, not prose:**
- max **±3% VE per iteration**
- **per-row timing ceilings**
- **knock auto-abort** (knock feedback active → stop)
- **fuel-before-timing** ordering
- **steady-state-before-transients**
- a hard **AFR floor** (back out if leaner than ~11.5:1 / λ ≈ 0.78 at full boost)
- **boost gated** until trims within ±5%, wideband tracking commanded AFR, and boost control verified against the VF48

**Rule:** no proposal — LLM *or* human — bypasses these clamps. Improving *how* they're enforced is allowed; removing the LLM-proposes / deterministic-executes separation is **not**. See `../CLAUDE.md`.
