"""The MAF baseline carries provenance, and the estimator refuses to lean on an unvalidated one.

WHY (2026-08-16): the sim seed `NOMINAL_MAF_IDLE = 2.50 g/s @850` was compared against the first
real warm-idle log — 3.493 g/s @709 rpm, +40% — and `maf_belief_ratio()` returned 1.397: a
confident "MAF +39.7%" verdict on a car whose total fuel trim was +0.31%. That term is the ONLY
thing separating a MAF fault from an injector-flow fault, so the layer was primed to invent a MAF
fault on a healthy engine. These tests pin the fix: (a) real-log-shaped observations against the
unvalidated baseline produce a REFUSAL, not a MAF verdict; (b) the same observations against a
validated baseline behave exactly as before; (c) `MafBaseline` interpolates/clamps and only
`from_capture` sets validated. NOT ONE TEST HERE HARDCODES 3.49 AS A BASELINE.
"""
from __future__ import annotations

import numpy as np
import pytest

from ecutune.algorithms.identify import (Observation, baseline_validated, identify,
                                         maf_belief_ratio)
from ecutune.evals.faults import FAULTS_V2, build_case_world
from ecutune.simulation.mvem import (FAST_AIR_SCALE, FAST_IDLE_RPM, IDLE_RPM, LOW_VOLTAGE,
                                     NOMINAL_MAF_IDLE, SIM_MAF_BASELINE, EngineParams,
                                     MafBaseline, OperatingPoint, steady_trim)

# What the real car measured on 2026-08-11 (romraiderlog_20260811_213908.csv, warm idle):
# 3.493 g/s at 709 rpm, total trim +0.31%. Used here as a MEASUREMENT to feed the estimator,
# never as a baseline.
REAL_MAF_GS = 3.493
REAL_TRIM = 0.0031


def _healthy_world(seed: int = 0):
    spec = next(s for s in FAULTS_V2 if s.fault_id == "healthy")
    return build_case_world(spec, np.random.default_rng(seed))


def _real_log_shaped(validated: bool) -> list[Observation]:
    """Three holds with the REAL car's warm-idle numbers, healthy trims at the other two,
    all compared against the SIM baseline (2.50 * air_scale)."""
    pts = ((1.0, 14.0), (FAST_AIR_SCALE, 14.0), (1.0, LOW_VOLTAGE))
    return [Observation(air_scale=a, voltage=v, trim=REAL_TRIM,
                        maf_reading=REAL_MAF_GS * a,
                        nominal_maf=SIM_MAF_BASELINE.at(IDLE_RPM) * a,
                        nominal_validated=validated)
            for a, v in pts]


# ------------------------------------------------------------------ the guard

def test_real_log_values_against_the_sim_baseline_are_REFUSED_not_a_maf_verdict():
    believed, _truth, _ = _healthy_world()
    obs = _real_log_shaped(validated=False)
    assert abs(maf_belief_ratio(obs) - REAL_MAF_GS / NOMINAL_MAF_IDLE) < 1e-9   # 1.397
    est = identify(believed, obs)
    assert est.identifiable is False
    assert "UNVALIDATED" in est.reason and "MAF verdict withheld" in est.reason
    assert "1.397" in est.reason                      # the ratio is REPORTED, not hidden
    assert "maf_high" in est.reason                    # ...and which band it would have hit
    assert "CAPTURE-PROTOCOL" in est.reason           # tells the operator what to do
    # a refusal blocks the write path via clamp_diagnosis_agreement; it must NOT be silent
    assert est.knob() is None or est.identifiable is False


def test_the_same_values_against_a_VALIDATED_baseline_behave_as_before():
    """Validation is the switch. If the baseline had been measured and really were 2.50 g/s, a
    3.49 g/s reading with flat trims IS anomalous — the estimator may say so. What matters
    here is that the guard is not firing (reason does not mention the baseline)."""
    believed, _truth, _ = _healthy_world()
    est = identify(believed, _real_log_shaped(validated=True))
    assert "UNVALIDATED" not in est.reason
    assert "MAF verdict withheld" not in est.reason


def test_unvalidated_baseline_with_ratio_near_one_still_diagnoses_from_trims():
    """The guard fires only when the verdict would REST on the MAF term. Ratio ~1.0 (outside
    both MAF bands) with an unvalidated baseline: the trims alone decide, and a healthy world
    is still called healthy."""
    believed, truth, _ = _healthy_world()
    pts = ((1.0, truth.v_ref), (FAST_AIR_SCALE, truth.v_ref), (1.0, LOW_VOLTAGE))
    obs = [Observation(air_scale=a, voltage=v,
                       trim=steady_trim(believed, truth, air_scale=a, voltage=v),
                       maf_reading=NOMINAL_MAF_IDLE * a * 1.0000,
                       nominal_maf=NOMINAL_MAF_IDLE * a, nominal_validated=False)
           for a, v in pts]
    est = identify(believed, obs)
    assert est.fault_id == "healthy" and est.identifiable


@pytest.mark.parametrize("fault", ["maf_low", "maf_high"])
def test_seeded_maf_faults_are_REFUSED_under_an_unvalidated_baseline(fault):
    """Capability is not lost — it is WITHHELD until the baseline is measured. With a validated
    baseline the same world identifies (test_identify.py proves that across seeds)."""
    spec = next(s for s in FAULTS_V2 if s.fault_id == fault)
    believed, truth, _ = build_case_world(spec, np.random.default_rng(1))
    maf_ratio = float(np.asarray(believed.get("sensor.maf_transfer").values).reshape(-1)[0]) \
        / truth.maf_scaling_true
    pts = ((1.0, truth.v_ref), (FAST_AIR_SCALE, truth.v_ref), (1.0, LOW_VOLTAGE))

    def obs(validated):
        return [Observation(air_scale=a, voltage=v,
                            trim=steady_trim(believed, truth, air_scale=a, voltage=v),
                            maf_reading=NOMINAL_MAF_IDLE * a * maf_ratio,
                            nominal_maf=NOMINAL_MAF_IDLE * a, nominal_validated=validated)
                for a, v in pts]

    unvalidated = identify(believed, obs(False))
    assert unvalidated.identifiable is False and "UNVALIDATED" in unvalidated.reason
    validated = identify(believed, obs(True))
    assert validated.identifiable and validated.fault_id == fault


def test_observation_defaults_to_unvalidated():
    """Safe by default: an Observation built without thinking about provenance is untrusted."""
    o = Observation(air_scale=1.0, voltage=14.0, trim=0.0, maf_reading=2.5, nominal_maf=2.5)
    assert o.nominal_validated is False
    assert baseline_validated([o]) is False
    # observations WITHOUT a baseline do not vote
    bare = Observation(air_scale=1.0, voltage=14.0, trim=0.0)
    assert baseline_validated([bare]) is True


# ------------------------------------------------------------------ MafBaseline itself

def test_sim_baseline_is_seeded_but_unvalidated_and_the_scalar_still_reads_2_50():
    assert SIM_MAF_BASELINE.validated is False
    assert "sim" in SIM_MAF_BASELINE.provenance.lower()
    assert SIM_MAF_BASELINE.at(IDLE_RPM) == pytest.approx(2.50)
    assert NOMINAL_MAF_IDLE == pytest.approx(2.50)              # sim/eval consumers unchanged
    assert OperatingPoint().maf_gs == pytest.approx(NOMINAL_MAF_IDLE)   # one source of truth
    assert SIM_MAF_BASELINE.at(FAST_IDLE_RPM) == pytest.approx(2.50 * FAST_AIR_SCALE)


def test_baseline_interpolates_and_clamps():
    b = MafBaseline(points=((700.0, 3.0), (900.0, 4.0)), validated=False, provenance="t")
    assert b.at(800.0) == pytest.approx(3.5)
    assert b.at(500.0) == pytest.approx(3.0)      # clamped, never extrapolated
    assert b.at(1500.0) == pytest.approx(4.0)


def test_from_capture_is_the_only_validated_constructor_and_sorts_points():
    b = MafBaseline.from_capture([(1500, 6.9), (850, 3.4)], provenance="three-hold capture, date")
    assert b.validated is True
    assert b.points == ((850.0, 3.4), (1500.0, 6.9))
    with pytest.raises(ValueError):
        MafBaseline(points=(), validated=False, provenance="empty")
    with pytest.raises(ValueError):
        MafBaseline(points=((900.0, 1.0), (800.0, 1.0)), validated=False, provenance="unsorted")


def test_engineparams_default_idle_air_is_independent_of_the_baseline():
    """MVEM's forward model never reads the baseline — the guard changes what the ESTIMATOR
    trusts, not what the sim simulates."""
    assert EngineParams().idle_air_g == 0.10
