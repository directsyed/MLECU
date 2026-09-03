"""The bounded-integral controller, the reusable control primitive behind every tuning stage.

The iterative loop `log -> propose -> clamp -> apply -> re-log` IS a discrete PI controller:
  * input  = the fuel trim error (how far the ECU is having to correct to hold AFR)
  * output = the fractional change to bake into the feedforward tables this iteration
  * the +/-3% safety clamp is simultaneously the controller's SATURATION limit and its anti-windup.

Anti-windup via conditional integration: while the output is saturated at the clamp, we FREEZE
the integral instead of letting it accumulate the part we couldn't apply. Without this, a big
initial error would wind the integral up and then overshoot (blow past target) once the error
finally shrank. Damping < 1 makes the steps deliberately small; it creeps to target rather than
ringing. That is why the loop is provably stable, not just "usually fine".
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BoundedIntegralState:
    integral: float = 0.0


@dataclass
class PIConfig:
    kp: float                 # proportional gain (fraction of error corrected per step)
    ki: float                 # integral gain (kills steady-state error)
    step_clamp: float = 0.03  # per-iteration saturation == SafetyCfg.max_ve_step
    damping: float = 0.6      # <1 => under-correct: small steps, no overshoot


def step(error: float, st: BoundedIntegralState, cfg: PIConfig) -> tuple[float, BoundedIntegralState]:
    """One control iteration. Returns (bounded fractional correction, new state)."""
    trial_integral = st.integral + error
    out = cfg.damping * (cfg.kp * error + cfg.ki * trial_integral)
    clamped = max(-cfg.step_clamp, min(cfg.step_clamp, out))
    # Conditional integration: only accept the integral if we did NOT saturate (anti-windup).
    integral = st.integral if clamped != out else trial_integral
    return clamped, BoundedIntegralState(integral)
