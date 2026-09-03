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


def test_real_romraider_v370_names_map_correctly():
    """Regression: the fixture used idealised headers, so these real v370 parameter names
    were never exercised. Each one collided with a REQUIRED capture channel (2026-08-12)."""
    # P91's real name has "Learning" between the two words the old pattern required to be adjacent.
    assert map_header("Fine Learning Knock Correction (degrees)") == "fine_knock_learn"
    assert map_header("Knock Correction Advance (degrees)") == "knock_retard"

    # Collisions with required channels -> must map to nothing at all.
    for header in (
        "Mass Airflow Sensor Voltage (V)",          # was -> maf_gs
        "Throttle Sensor Voltage (V)",              # was -> tps
        "Rear O2 Heater Voltage (V)",               # was -> battery_v
        "A/F Adjustment Voltage (V)",               # was -> battery_v
        "Differential Pressure Sensor Voltage (V)",  # was -> battery_v
        "Primary Wastegate Duty Cycle (%)",         # was -> injector_duty
        "Secondary Wastegate Duty Cycle (%)",       # was -> injector_duty
    ):
        assert map_header(header) is None, header

    # ...while the genuine articles still map.
    assert map_header("Mass Airflow (g/s)") == "maf_gs"
    assert map_header("Battery Voltage (V)") == "battery_v"
    assert map_header("Throttle Opening Angle (%)") == "tps"
    assert map_header("Injector Duty Cycle (%)") == "injector_duty"


# --- roles added for the ignition-timing stage (2026-08-30) --------------------------------
# Both channels were being lost or mis-assigned on the 2026-08-30 capture. This is the fifth
# and sixth silent role collision found in this project, so each gets a named test.

def test_iam_maps_to_its_own_role():
    """"IAM (1-byte)** (multiplier)" matched NO rule, so the channel that recorded the ECU
    withdrawing all dynamic advance for 52 seconds was invisible to the layer."""
    assert map_header("IAM (1-byte)** (multiplier)") == "iam"
    assert map_header("IAM (4-byte)* (multiplier)") == "iam"


def test_base_timing_does_not_collide_with_total_timing():
    """"Ignition Base Timing*" matched r"\\btiming\\b" and landed on `timing_total`, the role
    that means FINAL commanded advance. It only lost to "Ignition Total Timing" because that
    column happened to come first, and RomRaider's column order is not stable between
    sessions, which is precisely how "Final Fueling Base (lambda)" took over `wideband_afr`."""
    assert map_header("Ignition Base Timing* (degrees)") == "timing_base"
    assert map_header("Ignition Total Timing (degrees)") == "timing_total"


def test_iam_prefers_the_4byte_parameter_when_both_are_logged():
    from ecutune.logparse.schema import prefer
    hs = ["IAM (1-byte)** (multiplier)", "IAM (4-byte)* (multiplier)"]
    assert prefer("iam", hs) == "IAM (4-byte)* (multiplier)"
    assert prefer("iam", list(reversed(hs))) == "IAM (4-byte)* (multiplier)"


def test_tps_prefers_the_dbw_plate_angle_over_the_pedal_angle():
    """They track each other (r = 0.9992) but differ by up to 12.6 points in transitions, and
    the plate is what actually meters air. Resolved by an explicit rule, not by column order."""
    from ecutune.logparse.schema import prefer
    hs = ["Throttle Opening Angle (%)", "Throttle Plate Opening Angle (4-byte)* (%)"]
    assert prefer("tps", hs) == "Throttle Plate Opening Angle (4-byte)* (%)"
    assert prefer("tps", list(reversed(hs))) == "Throttle Plate Opening Angle (4-byte)* (%)"


def test_knock_sum_never_wins_the_knock_retard_role():
    """"Knock Sum* (count)" is a cumulative COUNTER, non-zero on 6425 of 7402 samples on the
    2026-08-30 log. If a reordered export let it win, every timing evidence figure would be
    computed from a monotonically rising integer."""
    from ecutune.logparse.schema import prefer
    hs = ["Knock Sum* (count)", "Knock Correction Advance (degrees)",
          "Feedback Knock Correction (4-byte)* (degrees)"]
    assert prefer("knock_retard", hs) == "Feedback Knock Correction (4-byte)* (degrees)"


def test_binned_timing_channels_are_nan_not_zero_when_absent():
    """A missing channel read as 0.0 would make (base - total) evidence look like a colossal
    retard demand on the nine logs that do not carry Ignition Base Timing."""
    n = 40
    log = LogTable({"rpm": np.full(n, 2000.0), "load": np.full(n, 0.5),
                    "tps": np.full(n, 20.0), "af_correction": np.zeros(n),
                    "af_learning": np.zeros(n)})
    g = bin_log(log, GridSpec(x_role="load", x_breaks=(0.5,), y_breaks=(2000.0,)))
    assert g.mean_timing_base is None
    assert g.mean_fine_knock is None


# --- live clamp signals (2026-08-30) -------------------------------------------------------

def test_knock_onsets_counts_steps_not_samples():
    """The project's own definition (ANALYSIS-2026-08-26): an onset is a step DOWN of >= 1.5
    deg. Counting non-zero samples instead counts the slow ramp-back as fresh knock."""
    from ecutune.logparse.signals import knock_onsets
    ramp = np.array([0.0, -4.0, -3.5, -3.0, -2.5, -2.0, -1.0, 0.0])
    assert knock_onsets(ramp) == (1, -4.0)
    assert knock_onsets(np.zeros(10)) == (0, 0.0)
    assert knock_onsets(None) == (0, 0.0)


def test_knock_onsets_ignores_a_link_spike():
    """The 2026-08-26 capture held one -32.0 sample between neighbours of -8.12 and -7.94.
    Counting it would be counting the K-line, not the engine."""
    from ecutune.logparse.signals import knock_onsets
    spike = np.array([-8.12, -32.0, -7.94])
    assert knock_onsets(spike)[0] == 0


def test_live_signals_reproduce_the_published_onset_count():
    """The 2026-08-30 post-flash-3 drive was independently reported as 23 onsets, worst -7.00
    deg. If this module cannot reproduce a number the project already published from the same
    file, one of the two is wrong."""
    import pathlib as _pl
    from ecutune.core.config import load_config
    from ecutune.logparse.signals import live_signals
    p = (_pl.Path(__file__).resolve().parents[1] / "logging" / "drive"
         / "drive-20260830-02-postflash3-timing.csv")
    if not p.exists():
        import pytest
        pytest.skip("drive log not available")
    log = parse_romraider_csv(p)
    g = bin_log(log, GridSpec(x_role="load", x_breaks=(0.25, 0.55, 0.85, 1.15),
                              y_breaks=(800.0, 2000.0, 3200.0), require_closed_loop=False))
    sig = live_signals(log, g, load_config().safety)
    assert sig.knock_onsets == 23
    assert sig.worst_knock_deg == -7.0
    assert sig.knock_active is True
