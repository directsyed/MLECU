# car/algorithms/

The **deterministic tuning layer** (build-priority — Claude builds, then explains).

**Status:** not started; designed and tested against Syed's own Stage-2/3 logs once they exist.

**Will contain:** bin-log-to-cell logic, bounded-correction proposers (injector latency/scaling first, then low-range MAF), and the correction logic validated by the `../simulation/` log-replay harness.

**Hard rule:** every value this layer would write passes through `../safety/`. The LLM *proposes*; this layer + the safety clamps *execute*. The LLM never writes ECU values directly.
