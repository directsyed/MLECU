"""Parser + schema-mapping + binning tests."""
from __future__ import annotations

import pathlib

import numpy as np

from ecutune.logparse.binning import GridSpec, bin_log, weighted_mean_trim
from ecutune.logparse.romraider_csv import LogTable, parse_romraider_csv
from ecutune.logparse.schema import map_header

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def test_parse_fixture_channels_and_units():
    log = parse_romraider_csv(FIXTURES / "sample_idle_log.csv")
    assert len(log) == 12
    for role in ("rpm", "maf_gs", "load", "af_correction", "af_learning",
                 "wideband_afr", "knock_retard", "fine_knock_learn", "timing_total",
                 "injector_duty", "iat", "coolant", "tps", "battery_v"):
        assert log.has(role), f"missing {role}"
    # right column won for wideband (14.7), NOT the narrowband "A/F Sensor #1" (14.5)
    assert abs(log.get("wideband_afr")[0] - 14.7) < 1e-9
    assert abs(np.nanmean(log.get("rpm")) - 850.0) < 5.0
    assert log.sample_hz == 10.0  # 100 msec/sample -> 10 Hz


def test_schema_mapping_table():
    cases = {
        "Mass Airflow (g/s)": "maf_gs",
        "Engine Load (g/rev)": "load",
        "AF Correction 1 (%)": "af_correction",
        "AF Learning 1 (%)": "af_learning",
        "Wideband AFR (AFR)": "wideband_afr",
        "AEM UEGO (AFR)": "wideband_afr",
        "Fine Knock Learn (degrees)": "fine_knock_learn",
        "Knock Correction Advance (degrees)": "knock_retard",
        "Ignition Total Timing (degrees)": "timing_total",
        "Injector Duty Cycle (%)": "injector_duty",
        "Throttle Opening Angle (%)": "tps",
        "RPM (rpm)": "rpm",
        "A/F Sensor #1 (AFR)": None,   # narrowband: deliberately NOT the wideband
    }
    for header, expected in cases.items():
        assert map_header(header) == expected, header


def test_missing_channel_is_absent_not_crash():
    text = "RPM (rpm),Coolant Temp (F)\n850,185\n860,186\n"
    log = parse_romraider_csv(text)
    assert log.has("rpm") and log.has("coolant")
    assert not log.has("maf_gs")            # simply absent
    assert len(log) == 2


def test_binning_lands_in_cell_and_computes_trim():
    n = 50
    log = LogTable(channels={
        "rpm": np.full(n, 850.0),
        "maf_gs": np.full(n, 2.4),          # nearest to break 2.0
        "af_correction": np.full(n, 6.0),
        "af_learning": np.full(n, 5.0),
        "tps": np.zeros(n),
    })
    spec = GridSpec(x_role="maf_gs", x_breaks=(2.0, 3.0, 5.0), y_breaks=(800.0, 1200.0),
                    min_samples=10)
    grid = bin_log(log, spec)
    assert grid.count[0, 0] == 50
    assert grid.confidence[0, 0]            # 50 >= 10
    assert grid.mean_trim[0, 0] == 11.0     # 6 + 5 (short + long term trim)
    assert weighted_mean_trim(grid) == 11.0


def test_binning_drops_transient_samples():
    n = 50
    log = LogTable(channels={
        "rpm": np.full(n, 850.0),
        "maf_gs": np.full(n, 2.4),
        "af_correction": np.full(n, 6.0),
        "af_learning": np.full(n, 5.0),
        "tps": np.linspace(0.0, 300.0, n),  # steep throttle ramp -> all transient
    })
    spec = GridSpec(x_role="maf_gs", x_breaks=(2.0, 3.0), y_breaks=(800.0,),
                    min_samples=5, steady_tps_tol=2.0)
    grid = bin_log(log, spec)
    assert grid.count.sum() == 0            # every sample rejected as transient
    assert weighted_mean_trim(grid) == 0.0  # graceful fallback
