"""Mean-Value Engine Model — a cycle-averaged (not crank-resolved) idle fuel model.

The right fidelity for proving idle FUEL convergence: we model how much fuel the ECU actually
delivers given its believed injector/airflow calibration vs the engine's true parameters, and the
steady-state closed-loop trim that results. We do NOT model combustion, knock physics, or
transients — knock in the harness is a scripted state for testing the abort clamp, not physics.

Fuel path (all masses per intake event; only ratios matter, so units are nominal):
  A_est   = A_true * (maf_believed / maf_true)         # ECU's airflow estimate
  m_target= A_est / AFR_target                          # open-loop fuel the ECU wants
  pw      = m_target / (flow_believed*K) + latency_believed   # pulsewidth it computes
  m_deliv = (pw - latency_true) * flow_true * K          # fuel actually injected
  trim    = m_required / m_deliv - 1                     # closed loop makes up the difference
where m_required = A_true / AFR_target and K converts cc/min*ms -> mass. At the TRUE calibration
every believed==true and trim==0; any mismatch shows up as a non-zero steady-state trim — exactly
the bad-idle symptom.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.models import TableSet
from ..core.tables import FUEL_INJECTOR_FLOW, FUEL_INJECTOR_LATENCY, SENSOR_MAF_TRANSFER


@dataclass
class EngineParams:
    """Ground truth — what the engine actually is. The ECU's tables start out NOT matching these."""
    displacement_l: float = 2.0      # EJ20X
    afr_target: float = 14.7
    fuel_density: float = 0.74       # g/cc
    idle_air_g: float = 0.10         # true METERED air mass per event at idle (nominal)
    flow_true: float = 500.0         # OEM 2005 FXT side-feed injectors (~500 cc/min) — matched to the ROM
    latency_true: float = 1.0        # true injector dead time, ms
    maf_scaling_true: float = 1.0    # the MAF scaling that would make A_est == A_true
    leak_air_g: float = 0.0          # UNMETERED air per event (vacuum leak downstream of the MAF).
                                     # Constant absolute — so its trim contribution SHRINKS as metered
                                     # airflow rises, unlike a %-type MAF/flow error. That signature
                                     # difference is what multi-point logging exploits.
    latency_slope: float = 0.12      # ms of EXTRA true dead time per volt below v_ref — injectors
                                     # open slower at low voltage (why ROMs carry a latency-vs-voltage
                                     # table). A latency-belief error therefore CHANGES with battery
                                     # voltage while a leak's trim is voltage-invariant: the v2 eval's
                                     # discriminating signal (sim analog of the real-car voltage sweep).
    v_ref: float = 14.0              # charging-system voltage the scalar latencies are quoted at

    @property
    def k(self) -> float:
        """cc/min * ms -> grams of fuel."""
        return self.fuel_density / 60000.0


# --- the multi-point probe protocol -------------------------------------------------------
# CANONICAL HOME for these (2026-08-05). They were defined in evals/cases.py, which made them
# look like an eval detail; they are not. They are the operating points that make the fault
# IDENTIFIABLE, and both the deterministic estimator and the real-car capture protocol are
# built around them. evals/cases.py now re-exports these so existing imports keep working and
# there is one source of truth.
IDLE_RPM = 850.0
FAST_AIR_SCALE = 2.0         # "fast idle" probe (~1500 rpm): separates LEAK (trim halves)
                             # from flow/MAF errors (trim flat)
FAST_IDLE_RPM = 1500.0
LOW_VOLTAGE = 12.0           # electrical-load probe: separates LATENCY (trim grows) from
                             # LEAK (trim flat). The only thing that splits those two.

# (air_scale, voltage_or_None) — voltage None means "at v_ref".
PROBE_POINTS = ((1.0, None), (FAST_AIR_SCALE, None), (1.0, LOW_VOLTAGE))


@dataclass(frozen=True)
class MafBaseline:
    """Healthy-engine MAF reading (g/s) as a function of rpm — the reference the estimator's
    MAF-vs-nominal term is judged against.

    WHY THIS IS A CLASS AND NOT A NUMBER (2026-08-16). The old scalar `NOMINAL_MAF_IDLE = 2.50`
    was a simulation seed that had never been measured on the car. The first real warm-idle log
    read 3.49 g/s at 709 rpm (+40%, worse normalised for rpm — TGV + exhaust-AVCS deletes raise
    idle airflow), and `identify.maf_belief_ratio()` turned that into a confident "MAF +39.7%"
    verdict on an engine whose total fuel trim was +0.31%. The number was wrong AND nothing
    recorded that it was unverified.

    So the baseline now carries its own PROVENANCE. `validated` is True ONLY when the points come
    from a real capture on a known-healthy engine (`from_capture`); the seeded sim baseline says
    False, and `identify()` refuses to issue a MAF verdict against an unvalidated baseline.
    Do NOT paste a single measured value in here — one log, one operating point, an engine that
    idles poorly, and rpm mismatch against the constant's own assumption is not a baseline.
    Populate it from the three-hold capture (`car/logging/CAPTURE-PROTOCOL.md`).
    """
    points: tuple[tuple[float, float], ...]      # (rpm, g/s), ascending rpm, >= 1 point
    validated: bool                              # provenance flag — see class docstring
    provenance: str

    def __post_init__(self) -> None:
        if not self.points:
            raise ValueError("MafBaseline needs at least one (rpm, g/s) point")
        rpms = [p[0] for p in self.points]
        if rpms != sorted(rpms) or len(set(rpms)) != len(rpms):
            raise ValueError("MafBaseline points must be strictly ascending in rpm")

    def at(self, rpm: float) -> float:
        """Nominal g/s at `rpm`: linear interpolation, clamped to the end points (no
        extrapolation — a baseline should never invent airflow it never saw)."""
        rpms = [p[0] for p in self.points]
        gs = [p[1] for p in self.points]
        return float(np.interp(rpm, rpms, gs))

    @classmethod
    def from_capture(cls, points, provenance: str) -> "MafBaseline":
        """A VALIDATED baseline — only ever built from real, healthy-engine measurements."""
        return cls(points=tuple(sorted((float(r), float(g)) for r, g in points)),
                   validated=True, provenance=provenance)


# The SIMULATION's healthy baseline. Consistent with the sim world (synth_log builds maf_gs from
# it, `harness.collect_observations` compares against it), so inside the sim it IS the truth —
# but it has never been measured on this engine, hence `validated=False`.
SIM_MAF_BASELINE = MafBaseline(
    points=((IDLE_RPM, 2.50), (FAST_IDLE_RPM, 2.50 * FAST_AIR_SCALE)),
    validated=False,
    provenance="simulation seed (2026-08-05); never measured on the EJ20X — see MafBaseline")

# Scalar kept for the sim/eval consumers that import it (evals/cases.py, ml/eval/harness/e4.py,
# tests). It is the sim baseline at warm idle; its provenance is SIM_MAF_BASELINE.provenance.
NOMINAL_MAF_IDLE = SIM_MAF_BASELINE.at(IDLE_RPM)      # == 2.50 g/s

# --- MEASURED baseline from the real car (2026-08-16 three-hold capture) ---------------------
# First real, validated MAF baseline for THIS engine. Two same-voltage steady holds where the
# closed-loop fuel trim was ~0 and the wideband tracked the 14.7 target — i.e. the airflow the
# ECU reports when it is fuelling correctly. `validated=True`: measured, not seeded.
#   warm idle  709 rpm -> 3.08 g/s (trim -0.86%, wb 14.74)   \  logs: car/logging/idle/idle-20260816-01-warm.csv
#   fast idle 1637 rpm -> 6.55 g/s (trim -5.12%, wb 14.55)   /         car/logging/idle/idle-20260816-02-fast.csv
# CAUTION carried in the provenance: the warm-idle point read 3.49 g/s on 2026-08-11 vs 3.08 here
# — a ~12% cross-session swing (atmospheric/warm-up; the MAF's low-voltage end wanders day to day,
# cf. reviewed forum doc 6224). So this is a baseline with real variance, not an exact constant;
# a MAF verdict inside ~+/-12% of nominal is inside the noise floor and must not be called a fault.
# Consumed by the real-log->Observation bridge (`logparse/observe.py`, `cli.py --diagnose`), which
# sets Observation.nominal_validated from this baseline's flag. NOTE it is self-referential for the
# capture that DEFINED it — the bridge's `maf_term=False` mode drops the (tautological) MAF term
# there; it becomes informative for a re-log compared against this stored baseline.
# See car/logging/CAPTURE-PROTOCOL.md.
MEASURED_MAF_BASELINE_20260816 = MafBaseline.from_capture(
    [(708.65, 3.08), (1637.14, 6.55)],
    provenance="three-hold capture 2026-08-16 (warm+fast idle, trim~0, wb on target); "
               "~12% cross-session variance vs 2026-08-11 (3.49 g/s @709) — treat +/-12% as noise")


@dataclass(frozen=True)
class OperatingPoint:
    rpm: float = IDLE_RPM
    maf_gs: float = NOMINAL_MAF_IDLE     # one source of truth for the sim's idle airflow
    load_grev: float = 0.30


def _scalar(tables: TableSet, table_id: str) -> float:
    return float(np.asarray(tables.get(table_id).values).reshape(-1)[0])


def open_loop_fuel(tables: TableSet, params: EngineParams,
                   air_scale: float = 1.0, voltage: float | None = None) -> tuple[float, float]:
    """(delivered, required) fuel mass per event at `air_scale` x idle airflow.

    The MAF only sees METERED air; a leak adds unmetered air the ECU must fuel via trim. The
    burned charge is metered + leak, so `required` uses both while the ECU's open-loop target
    is computed from its (possibly mis-scaled) estimate of the metered flow alone.

    `voltage` (default v_ref — exact v1 behavior): both the TRUE dead time and the ECU's
    BELIEVED dead time grow as voltage drops. The believed curve scales with the believed
    scalar (wrong injector data is wrong across the whole voltage table), so a latency-belief
    error grows at low voltage; every other fault's voltage terms cancel exactly.
    """
    flow_b = _scalar(tables, FUEL_INJECTOR_FLOW)
    lat_b = _scalar(tables, FUEL_INJECTOR_LATENCY)
    maf_b = _scalar(tables, SENSOR_MAF_TRANSFER)
    v = params.v_ref if voltage is None else voltage
    dv = max(0.0, params.v_ref - v)
    lat_true_eff = params.latency_true + params.latency_slope * dv
    slope_b = params.latency_slope * (lat_b / params.latency_true if params.latency_true else 1.0)
    lat_b_eff = lat_b + slope_b * dv
    a_metered = params.idle_air_g * air_scale
    a_burned = a_metered + params.leak_air_g
    a_est = a_metered * (maf_b / params.maf_scaling_true)
    m_target = a_est / params.afr_target
    pw = m_target / (flow_b * params.k) + lat_b_eff       # ms
    delivered = max(0.0, pw - lat_true_eff) * params.flow_true * params.k
    required = a_burned / params.afr_target
    return delivered, required


def steady_trim(tables: TableSet, params: EngineParams, air_scale: float = 1.0,
                voltage: float | None = None) -> float:
    """Steady-state closed-loop fuel trim (fraction). +ve = ECU adding fuel (base map lean)."""
    delivered, required = open_loop_fuel(tables, params, air_scale, voltage)
    if delivered <= 0.0:
        return 1.0
    return required / delivered - 1.0
