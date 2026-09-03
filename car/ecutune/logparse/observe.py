"""Real-log → Observation bridge, the piece `car/logging/CAPTURE-PROTOCOL.md` always intended.

Turns real RomRaider CSV holds into the `list[Observation]` that `algorithms.identify.identify()`
consumes: the real-car analog of `simulation.harness.collect_observations`, fed by
`parse_romraider_csv` instead of the synthetic generator. "That equivalence is the whole point of
the log-replay design" (CAPTURE-PROTOCOL.md). READ-ONLY: it produces Observations, never a table.

Design notes that matter for correctness:
- `air_scale` is the MEASURED airflow ratio vs the warm hold, not an assumed 2× (the estimator uses
  the measured ratio, CAPTURE-PROTOCOL.md).
- `trim` comes through the same binner + steady-state filter the sim uses (`bin_log` →
  `weighted_mean_trim`, a percentage → fraction here).
- **The MAF-reading term is only attached to charging-voltage holds.** A low-voltage hold is the
  LATENCY probe (trim vs voltage); under electrical load the idle speed rises and airflow with it,
  so that hold's airflow sits OFF the no-load baseline curve, comparing it to `baseline.at(rpm)`
  would manufacture a false MAF fault. Its `nominal_maf` is left NaN so `identify()` drops the MAF
  term for it (see `identify._has_maf_baseline`).
- `nominal_validated` is taken from the baseline's own flag, NOT hardcoded True (the sim harness
  hardcodes it because inside the sim the baseline is the truth; a real loader must not).
"""
from __future__ import annotations

import numpy as np

from ..algorithms.identify import Observation
from ..logparse.binning import GridSpec, bin_log, weighted_mean_trim
from ..logparse.romraider_csv import LogTable, parse_romraider_csv
from ..simulation.mvem import MafBaseline

CHARGING_TOL_V = 0.6   # a hold within this of the warm hold's voltage is a charging-voltage probe


def _as_logtable(h) -> LogTable:
    return h if isinstance(h, LogTable) else parse_romraider_csv(h)


def _mean(lt: LogTable, role: str) -> float:
    v = lt.get(role)
    return float(np.nanmean(v)) if v is not None and not np.all(np.isnan(v)) else float("nan")


def observations_from_logs(holds, baseline: MafBaseline,
                           maf_term: bool = True) -> list[Observation]:
    """Build Observations from real hold logs. `holds[0]` is the warm baseline hold (its airflow
    and voltage are the references). `holds` may be paths or `LogTable`s.

    `maf_term=False` suppresses the MAF-reading term on ALL holds, used when the baseline was
    derived from THESE SAME holds (self-referential: the ratio is 1.0 by construction and carries
    no information). For a re-log compared against a PRIOR stored baseline, leave it True.
    """
    tables = [_as_logtable(h) for h in holds]
    if len(tables) < 2:
        raise ValueError(f"need >=2 holds (warm baseline + >=1 probe), got {len(tables)}")
    warm_maf = _mean(tables[0], "maf_gs")
    warm_v = _mean(tables[0], "battery_v")
    if not (warm_maf > 0):
        raise ValueError("warm hold (holds[0]) has no usable maf_gs channel")

    obs: list[Observation] = []
    for lt in tables:
        maf, rpm, volts = _mean(lt, "maf_gs"), _mean(lt, "rpm"), _mean(lt, "battery_v")
        # one cell: breaks are cell-centres with nearest-assignment, so a single break bins the
        # whole hold into one cell after the steady-state filter.
        grid = bin_log(lt, GridSpec(x_role="maf_gs", x_breaks=(maf,), y_breaks=(rpm,)))
        charging = abs(volts - warm_v) <= CHARGING_TOL_V
        nominal = baseline.at(rpm) if (maf_term and charging) else float("nan")
        obs.append(Observation(
            air_scale=maf / warm_maf,
            voltage=volts,
            trim=weighted_mean_trim(grid) / 100.0,
            maf_reading=maf,
            nominal_maf=nominal,
            nominal_validated=baseline.validated))
    return obs
