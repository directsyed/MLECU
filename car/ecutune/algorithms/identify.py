"""Deterministic fault identification from MULTI-POINT observations.

WHY THIS EXISTS (E4 run, 2026-08-04). At one operating point the observable is scalar and the
state is three-dimensional:

    trim = f( injector_latency , injector_flow , maf_transfer )    # 1 equation, 3 unknowns

Any one of the three beliefs can be moved to null the trim. So the LLM's diagnosis was not
advice — it was THE MISSING CONSTRAINT that made the problem solvable at all, and the
deterministic layer had no basis on which to disagree with it. A wrong diagnosis therefore did
not merely delay convergence; it converged the loop to a different, wrong-but-self-consistent
fixed point. Measured across 42 episodes: masked episodes ended at 6.7-7.7% residual belief
error against 3.3-5.2% for correctly-diagnosed ones, 9 episodes finished with a SECOND belief
corrupted that was never faulty, and one single-iteration slip in twelve permanently bent a
table with no way to undo it.

The fix is not a better model. Three probe points make the system IDENTIFIABLE, and mvem.py
already documents exactly why — read the comments on `leak_air_g` ("its trim contribution
SHRINKS as metered airflow rises ... what multi-point logging exploits") and `latency_slope`
("a latency-belief error changes with battery voltage while a leak's trim is voltage-invariant").
The forward model already exists. This module inverts it.

    fault             vs 2x airflow           vs 12 V
    injector_flow     flat                    flat
    injector_latency  shrinks                 GROWS      <- voltage is the only leak/latency split
    vacuum_leak       halves                  flat
    maf_*             flat, and the MAF READING itself is off vs nominal

THE CONTRACT (Syed, 2026-08-05): the LLM POINTS, it does not COMMAND. This module lets the
deterministic layer reach its own conclusion from its own data, so that
`safety.clamps.clamp_diagnosis_agreement` can refuse to write when the two disagree — and hand
the human both sides of the argument instead of a silent edit.

Dependencies are numpy + stdlib only, matching the rest of ecutune (no scipy): a bounded
golden-section search over ONE free parameter per hypothesis is more than enough.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..core.models import Table, TableSet
from ..core.tables import FUEL_INJECTOR_FLOW, FUEL_INJECTOR_LATENCY, SENSOR_MAF_TRANSFER
from ..simulation.mvem import EngineParams, steady_trim

# Which believed scalar each fault hypothesis moves. Mirrors ml/eval/harness/e4_map.py; the
# test suite asserts the two agree so a rename in one cannot silently desynchronise them.
FAULT_KNOB: dict[str, str | None] = {
    "maf_low": SENSOR_MAF_TRANSFER,
    "maf_high": SENSOR_MAF_TRANSFER,
    "injector_flow_lean": FUEL_INJECTOR_FLOW,
    "injector_flow_rich": FUEL_INJECTOR_FLOW,
    "injector_latency_lean": FUEL_INJECTOR_LATENCY,
    "vacuum_leak": None,        # not a table error — unmetered air
    "healthy": None,
}

# Search bounds for each hypothesis' single free parameter, expressed as the ratio
# believed/true (or, for the leak, the unmetered air mass in grams per event).
_BOUNDS: dict[str, tuple[float, float]] = {
    "maf_low": (0.70, 0.999),
    "maf_high": (1.001, 1.40),
    "injector_flow_lean": (1.001, 1.40),
    "injector_flow_rich": (0.70, 0.999),
    "injector_latency_lean": (0.50, 0.999),
    "vacuum_leak": (1e-4, 0.10),
}

# Identifiability thresholds. Both are deliberately conservative: refusing to identify costs an
# iteration, while a confident wrong identification costs a permanently bent calibration.
MAX_ACCEPTABLE_RESIDUAL = 0.02 ** 2 * 3    # ~2% trim error across 3 points before "nothing fits"
MIN_MARGIN_RATIO = 1.5                     # best must beat runner-up by this factor


@dataclass(frozen=True)
class Observation:
    """One steady-state probe point. `air_scale` and `voltage` are the two axes that break the
    degeneracy; `maf_reading` vs `nominal_maf` is a DIRECT read on MAF belief error that needs
    no trim inference at all."""
    air_scale: float          # 1.0 = warm idle, ~2.0 = fast idle
    voltage: float            # ~14.0 charging, ~12.0 under electrical load
    trim: float               # measured steady-state trim, FRACTION (not %)
    maf_reading: float = float("nan")   # ECU-reported g/s at this point
    nominal_maf: float = float("nan")   # healthy-baseline g/s at this air_scale


@dataclass(frozen=True)
class FaultEstimate:
    """What the deterministic layer concluded, and how strongly.

    `residuals` is the whole per-hypothesis table, not just the winner — the disagreement report
    shows it to the human so they can see how close the runner-up was rather than being handed a
    bare verdict.
    """
    fault_id: str
    magnitude: float                       # fitted free parameter (ratio, or leak grams)
    residuals: dict[str, float] = field(default_factory=dict)
    margin: float = 0.0                    # runner_up_residual / best_residual
    identifiable: bool = False
    reason: str = ""                       # why not, when identifiable is False
    n_observations: int = 0
    # The exact probe points this verdict was fitted to. Carried so the disagreement report can
    # show the human the layer's INPUT as well as its conclusion — a verdict without its
    # evidence is the thing this whole exercise exists to stop producing.
    observations: tuple = ()

    def knob(self) -> str | None:
        return FAULT_KNOB.get(self.fault_id)


def _scalar_of(tables: TableSet, table_id: str) -> float:
    return float(np.asarray(tables.get(table_id).values).reshape(-1)[0])


def _believed_with(base: TableSet, table_id: str, value: float) -> TableSet:
    """A copy of `base` with one believed scalar replaced. Never mutates the input — the same
    copy-semantics the write path enforces."""
    t = base.get(table_id)
    return TableSet({**base.tables,
                     table_id: Table(t.table_id, t.kind, np.array(float(value)), units=t.units,
                                     hard_min=t.hard_min, hard_max=t.hard_max)})


def _sse(believed: TableSet, params: EngineParams, obs: list[Observation]) -> float:
    """Squared residuals of everything the hypothesis predicts: the trim at each probe point
    AND the airflow the ECU would report.

    THE MAF READING TERM IS LOAD-BEARING, not a refinement. A MAF-scaling error and an
    injector-flow error are EXACTLY degenerate in trim space — scaling `maf_b` by r and dividing
    `flow_b` by r produce an identical pulse width, so no combination of airflow and voltage
    probes can separate them. What separates them is that a wrong MAF transfer also corrupts the
    airflow the ECU REPORTS, while a wrong injector-flow belief does not.

    Found the hard way: scoring trims alone recovered 15/21 seeded faults through the real
    log->bin path, and every miss was a MAF fault scored as the corresponding flow fault, with
    the tie decided by sensor noise.
    """
    total = 0.0
    for o in obs:
        pred = steady_trim(believed, params, air_scale=o.air_scale, voltage=o.voltage)
        total += (pred - o.trim) ** 2
        if o.nominal_maf and not math.isnan(o.maf_reading) and not math.isnan(o.nominal_maf):
            # this hypothesis implies the ECU over/under-reports airflow by exactly this ratio
            pred_ratio = _scalar_of(believed, SENSOR_MAF_TRANSFER) / params.maf_scaling_true
            total += (pred_ratio - o.maf_reading / o.nominal_maf) ** 2
    return total


def _golden_min(f, lo: float, hi: float, tol: float = 1e-5, max_iter: int = 60) -> tuple[float, float]:
    """Golden-section minimisation of a unimodal 1-D function on [lo, hi] -> (x, f(x)).

    Deliberately simple and dependency-free. Each hypothesis has exactly one free parameter and
    its SSE is smooth and unimodal in that parameter, so this is sufficient — and it keeps
    ecutune importable in any venv that has numpy, which the cross-venv scoring pattern relies on.
    """
    phi = (math.sqrt(5.0) - 1.0) / 2.0
    a, b = lo, hi
    c, d = b - phi * (b - a), a + phi * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(max_iter):
        if b - a < tol:
            break
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - phi * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + phi * (b - a)
            fd = f(d)
    x = (a + b) / 2.0
    return x, f(x)


def matched_params(believed: TableSet, params: EngineParams) -> EngineParams:
    """The 'all my beliefs are correct' world: truth == belief on every knob, no leak.

    THIS IS THE REFERENCE EVERY HYPOTHESIS PERTURBS, and getting it wrong was the estimator's
    first bug. Passing a default EngineParams() instead means its OEM constants (flow 500,
    latency 1.0, maf 1.0) act as "truth" even when the believed tables differ from them — so
    every hypothesis was implicitly fitting a TWO-fault world (the belief/OEM gap, plus the
    perturbation under test) and the leak hypothesis could absorb an injector-flow error.

    By construction `steady_trim` is 0 at every probe point in this world (mvem: "at the TRUE
    calibration every believed==true and trim==0"), which is exactly the `healthy` hypothesis.
    """
    from dataclasses import replace
    return replace(params,
                   flow_true=_scalar_of(believed, FUEL_INJECTOR_FLOW),
                   latency_true=_scalar_of(believed, FUEL_INJECTOR_LATENCY),
                   maf_scaling_true=_scalar_of(believed, SENSOR_MAF_TRANSFER),
                   leak_air_g=0.0)


def _fit_hypothesis(fault_id: str, believed: TableSet, base: EngineParams,
                    obs: list[Observation]) -> tuple[float, float]:
    """(best_parameter, residual) for one single-fault hypothesis.

    `base` must be the matched world from `matched_params`. The hypothesis is always "my BELIEF
    about X is wrong by this factor" — the believed values are known (they are the current ROM),
    so what we solve for is the truth that would explain the observed trims.
    """
    from dataclasses import replace

    if fault_id == "healthy":
        return 0.0, _sse(believed, base, obs)

    lo, hi = _BOUNDS[fault_id]

    if fault_id == "vacuum_leak":
        # Every belief correct; unmetered air is the only free parameter.
        def cost(leak: float) -> float:
            return _sse(believed, replace(base, leak_air_g=float(leak)), obs)
        return _golden_min(cost, lo, hi)

    knob = FAULT_KNOB[fault_id]
    believed_val = _scalar_of(believed, knob)

    def cost(ratio: float) -> float:
        true_val = believed_val / float(ratio)          # ratio = believed / true
        if knob == SENSOR_MAF_TRANSFER:
            p = replace(base, maf_scaling_true=true_val)
        elif knob == FUEL_INJECTOR_FLOW:
            p = replace(base, flow_true=true_val)
        else:
            # latency_slope scales with belief/truth inside mvem, so only latency_true moves
            p = replace(base, latency_true=true_val)
        return _sse(believed, p, obs)

    return _golden_min(cost, lo, hi)


def maf_belief_ratio(obs: list[Observation]) -> float | None:
    """believed/true MAF scaling read DIRECTLY off the reported airflow, no trim inference.

    If the ECU's MAF transfer is wrong by a factor, the airflow it REPORTS is wrong by that same
    factor — an observation the deterministic layer already receives (maf_gs is the grid's
    x-axis) and has never used. Returns None when the logs carry no nominal baseline.
    """
    ratios = [o.maf_reading / o.nominal_maf for o in obs
              if o.nominal_maf and not math.isnan(o.maf_reading)
              and not math.isnan(o.nominal_maf) and o.nominal_maf != 0]
    return float(np.mean(ratios)) if ratios else None


def identify(believed: TableSet, obs: list[Observation],
             params: EngineParams | None = None) -> FaultEstimate:
    """Which single belief best explains these observations — the layer's OWN verdict.

    `params` supplies the non-fitted engine constants (AFR target, nominal idle air, the
    latency-vs-voltage slope). Its flow/latency/maf "true" fields are placeholders that each
    hypothesis overrides while fitting; the caller does NOT need to know ground truth.

    Refuses in two distinct ways, and the distinction matters to the operator:
      * `margin` too small     -> two hypotheses explain the data equally well. More/other probe
                                  points are needed. Not a fault report.
      * best residual too big  -> NO single-fault hypothesis fits. Multiple simultaneous faults,
                                  or something the model does not represent. Escalate.
    """
    params = params or EngineParams()
    if len(obs) < 2:
        return FaultEstimate("", 0.0, {}, 0.0, False,
                             f"need >=2 probe points to identify, got {len(obs)}",
                             len(obs), tuple(obs))

    base = matched_params(believed, params)
    residuals: dict[str, float] = {}
    fits: dict[str, float] = {}
    for fault_id in FAULT_KNOB:
        if fault_id in ("maf_low", "maf_high"):
            continue                    # handled below, using the direct MAF observation
        best_param, sse = _fit_hypothesis(fault_id, believed, base, obs)
        residuals[fault_id] = sse
        fits[fault_id] = best_param

    # MAF hypotheses: the reported airflow gives the ratio directly, so we fit nothing and just
    # score the implied world. Falls back to the generic search when no baseline is logged.
    ratio = maf_belief_ratio(obs)
    for fault_id in ("maf_low", "maf_high"):
        lo, hi = _BOUNDS[fault_id]
        if ratio is not None and lo <= ratio <= hi:
            from dataclasses import replace
            p = replace(base, maf_scaling_true=_scalar_of(believed, SENSOR_MAF_TRANSFER) / ratio)
            residuals[fault_id] = _sse(believed, p, obs)
            fits[fault_id] = ratio
        elif ratio is not None:
            residuals[fault_id] = float("inf")      # direct observation rules this one out
            fits[fault_id] = ratio
        else:
            best_param, sse = _fit_hypothesis(fault_id, believed, base, obs)
            residuals[fault_id] = sse
            fits[fault_id] = best_param

    order = sorted(residuals, key=lambda k: residuals[k])
    best = order[0]
    r_best = residuals[best]

    # The margin is measured against the best competitor that would take a DIFFERENT ACTION.
    # Two hypotheses routing to the same knob are operationally identical — `maf_low` vs
    # `maf_high` move the same table (direction comes from the measured trim, not the label),
    # and `healthy` vs `vacuum_leak` both mean "do not edit". Ranking them against each other
    # produced spurious "not identifiable" verdicts on healthy engines where BOTH candidates
    # meant the same thing. This is the same distinction E4 draws between diagnosis_accuracy
    # and knob_correct.
    rival = next((k for k in order[1:] if FAULT_KNOB.get(k) != FAULT_KNOB.get(best)), None)
    r_next = residuals[rival] if rival else float("inf")
    margin = float("inf") if r_best <= 0 else r_next / r_best

    if r_best > MAX_ACCEPTABLE_RESIDUAL:
        return FaultEstimate(best, fits[best], residuals, margin, False,
                             f"no single-fault hypothesis fits (best SSE {r_best:.2e} > "
                             f"{MAX_ACCEPTABLE_RESIDUAL:.2e}) — multiple faults or unmodelled "
                             f"behaviour; escalate", len(obs), tuple(obs))
    if best == "healthy":
        # A healthy engine has trims at ~0, so any rival is fitting sensor NOISE with a
        # negligible magnitude — it is not a competing action, it is "do nothing" wearing a
        # different label. Were a real fault present, `healthy` could not have won on residual
        # in the first place. Reporting this as "not identifiable" was technically true and
        # operationally useless.
        return FaultEstimate(best, fits[best], residuals, margin, True, "", len(obs),
                             tuple(obs))
    if margin < MIN_MARGIN_RATIO:
        return FaultEstimate(best, fits[best], residuals, margin, False,
                             f"not identifiable: {best} and {rival} imply DIFFERENT actions and "
                             f"explain the data comparably (margin {margin:.2f} < "
                             f"{MIN_MARGIN_RATIO}) — more probe points needed", len(obs), tuple(obs))
    return FaultEstimate(best, fits[best], residuals, margin, True, "", len(obs),
                         tuple(obs))
