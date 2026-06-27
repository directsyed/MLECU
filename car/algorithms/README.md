# car/algorithms/

The **deterministic tuning layer** (build-priority — Claude builds, then explains).

**Status:** ✅ **BUILT (offline, idle Stage-2)** — `../ecutune/algorithms/` (bounded-integral controller + idle global-scalar corrector). Validated by the `../ecutune/simulation/` convergence harness (seeded idle trim +14.8% → <5% in 4 iters, zero clamp violations). Tested against Syed's own Stage-2/3 logs once they exist; Stage-3 boost PID still to come.

**Will contain:** bin-log-to-cell logic, bounded-correction proposers (injector latency/scaling first, then low-range MAF), and the correction logic validated by the `../simulation/` log-replay harness.

**Hard rule:** every value this layer would write passes through `../safety/`. The LLM *proposes*; this layer + the safety clamps *execute*. The LLM never writes ECU values directly.

**Control-theory note (PID).** Idle Stage-2 is *feedforward* — correct injector/MAF/VE tables; the ECU's own closed-loop fuel PI tracks AFR live, so we just fix the feedforward. The iterative `log → correct → reflash → re-log` loop is a **bounded-integral controller**: accumulate trim error, correct a fraction, the ±3% clamp = rate-limit / anti-windup; design as a damped PI to avoid overshoot ("small steps"). **Boost control (Stage 3) is a real PID we tune** (base-duty feedforward + PID on boost error), informed by the rusEFI/ECUMaster boost-PID docs in the corpus.
