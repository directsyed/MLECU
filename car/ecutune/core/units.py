"""Pure AFR / lambda / fueling math shared by the clamps and algorithms.

No table mutation, no I/O, just conversions. Stoichiometric AFR for pump gasoline is
14.7:1 (mass air:fuel). The EJ20X runs 93 oct always (car/CLAUDE.md); octane is the margin,
it does not change stoich.
"""
from __future__ import annotations

STOICH_GASOLINE = 14.7  # mass AFR at lambda = 1


def afr_to_lambda(afr: float, stoich: float = STOICH_GASOLINE) -> float:
    """lambda = AFR / stoich.  lambda < 1 = rich, lambda > 1 = lean."""
    return afr / stoich


def lambda_to_afr(lam: float, stoich: float = STOICH_GASOLINE) -> float:
    return lam * stoich


def fuel_scale_for_afr_error(measured_afr: float, target_afr: float) -> float:
    """Signed fractional fuel change to drive measured AFR toward target.

    Lean (measured > target) needs MORE fuel -> positive scale.
    Rich (measured < target) needs LESS fuel -> negative scale.
    e.g. measured 15.4, target 14.7 -> +0.0476 (add ~4.8% fuel).
    """
    if target_afr <= 0:
        return 0.0
    return measured_afr / target_afr - 1.0
