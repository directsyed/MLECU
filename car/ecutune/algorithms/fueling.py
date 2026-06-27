"""Fuel math: turn a trim error into per-scalar table corrections, with the right SIGN.

The three idle global scalars all move delivered fuel, but not in the same direction:
  * Injector Flow Scaling (cc/min the ECU believes): INVERSE. If the ECU thinks the injectors
    flow more, it commands a shorter pulse -> less fuel. So to ADD fuel, LOWER this number.
  * Injector Latency (dead time): DIRECT. More dead time -> longer total pulse -> more fuel.
  * MAF Sensor Scaling (airflow estimate): DIRECT. Higher airflow estimate -> more commanded fuel.

A trim of +N% means the ECU is ADDING N% fuel to hold stoich because the base map is N% lean —
so the feedforward correction we want is to add that same fraction.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScalarSplit:
    """How the per-iteration fuel correction is shared across the three global scalars. Weights
    sum to ~1 so the NET feedforward fuel change is the controller's bounded output. Flow scaling
    carries most of it (the cleanest whole-map lever); latency/MAF are honest refinements. The
    latency-first framing from the docs lives in these weights; they are config, not physics."""
    w_latency: float = 0.2
    w_flow: float = 0.7
    w_maf: float = 0.1


def trim_to_fuel_fraction(trim_pct: float) -> float:
    """+6% trim -> +0.06 fuel fraction to bake in."""
    return trim_pct / 100.0


def corrected_flow_scaling(current: float, fuel_frac: float) -> float:
    """INVERSE: to add `fuel_frac` fuel, lower the believed injector flow."""
    return current / (1.0 + fuel_frac)


def corrected_latency(current: float, fuel_frac: float) -> float:
    """DIRECT: more dead time delivers more fuel."""
    return current * (1.0 + fuel_frac)


def corrected_maf(current: float, fuel_frac: float) -> float:
    """DIRECT: a higher airflow estimate commands more fuel."""
    return current * (1.0 + fuel_frac)
