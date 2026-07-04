"""Seed the convergence sim from the REAL 2005 FXT calibration (A2WC411D / CID 3B12504206).

Replaces mismatch.ej20x_into_ej255()'s invented "believed" numbers with what Syed's ECU
actually believes — the values read out of the harvested stock ROM (RomRaider attachment,
SHA1 in the roms manifest; same CID revision family as the car's 4EAT ECU):

  believed injector flow  = the ROM's Injector Flow Scaling scalar (503.93 cc/min — the
                            "~500cc matched injectors" prior, now a measured fact)
  believed latency        = the ROM's Injector Latency curve interpolated at idle charging
                            voltage (~14.1 V with the alternator loaded)
  believed MAF scale      = 1.0 by definition: the stock transfer curve IS the reference
  idle operating point    = the ROM's own hot-idle target (Idle Speed Target A @ 90 degC)

The TRUTH side keeps the same neutral physical-error priors as ej20x_into_ej255 — every fuel
lever a little off, no pre-decided culprit (the data sets priorities) — but expressed relative
to the real believed values, so believed/true ratios (what the trim actually sees) match the
documented swap uncertainty: MAF reads ~7% low (intake mods), believed flow ~2% high, believed
latency ~4% low.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..core.models import Table, TableSet
from ..core.tables import (FUEL_INJECTOR_FLOW, FUEL_INJECTOR_LATENCY, IDLE_SPEED_TARGET_A,
                           SENSOR_MAF_TRANSFER)
from ..platforms.subaru_ecuflash import TO_PLATFORM, VARIANTS
from ..romread import EcuFlashDefs, RomImage, read_semantic_tables
from .mvem import EngineParams, OperatingPoint

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ROM = (REPO_ROOT / "ml" / "data-pipeline" / "data" / "raw" / "roms" / "romraider"
               / "3B12504206_A2WC411D.bin")
DEFAULT_DEFS = (REPO_ROOT / "ml" / "data-pipeline" / "data" / "raw" / "SubaruDefs"
                / "ECUFlash" / "subaru metric")
SIBLING_DEFS = ("A2WC410D", "A2WC412D")   # 411D itself has no community def; see reader docstring

IDLE_CHARGING_V = 14.1
HOT_COOLANT_C = 90.0

# Neutral swap-uncertainty priors — SAME ratios as mismatch.ej20x_into_ej255 (believed/true):
_RATIO_FLOW = 510.0 / 500.0     # believed flow ~2% high
_RATIO_LATENCY = 0.96 / 1.0     # believed latency ~4% low
_RATIO_MAF = 0.93 / 1.0         # ECU's airflow estimate ~7% low (intake mods)


def _interp(curve: Table, at: float) -> float:
    ax = np.asarray(curve.x_axis.breakpoints, dtype=float)
    vals = np.asarray(curve.values, dtype=float)
    if ax[0] > ax[-1]:                      # np.interp needs ascending x
        ax, vals = ax[::-1], vals[::-1]
    return float(np.interp(at, ax, vals))


def fxt_rom_into_ej20x(rom_path: Path | str = DEFAULT_ROM,
                       defs_root: Path | str = DEFAULT_DEFS,
                       ) -> tuple[TableSet, EngineParams, OperatingPoint, dict]:
    """(believed tables from the REAL ROM, true engine params, idle operating point, rom report)."""
    rom = RomImage.load(rom_path)
    defs = EcuFlashDefs(Path(defs_root))
    sem, report = read_semantic_tables(rom, defs, list(SIBLING_DEFS), TO_PLATFORM, VARIANTS)

    flow_b = float(sem[FUEL_INJECTOR_FLOW].values)
    lat_b = _interp(sem[FUEL_INJECTOR_LATENCY], IDLE_CHARGING_V)
    idle_rpm = _interp(sem[IDLE_SPEED_TARGET_A], HOT_COOLANT_C)

    believed = TableSet({
        FUEL_INJECTOR_FLOW: Table(FUEL_INJECTOR_FLOW, "scalar", np.array(flow_b), units="cc/min"),
        FUEL_INJECTOR_LATENCY: Table(FUEL_INJECTOR_LATENCY, "scalar", np.array(lat_b), units="ms"),
        SENSOR_MAF_TRANSFER: Table(SENSOR_MAF_TRANSFER, "scalar", np.array(1.0), units="scale"),
    })
    truth = EngineParams(
        displacement_l=2.0, idle_air_g=0.10,
        flow_true=flow_b / _RATIO_FLOW,
        latency_true=lat_b / _RATIO_LATENCY,
        maf_scaling_true=1.0 / _RATIO_MAF,
    )
    op = OperatingPoint(rpm=idle_rpm)
    report["seed"] = {"flow_cc_min": flow_b, "latency_ms_at_14v": lat_b,
                      "hot_idle_target_rpm": idle_rpm}
    return believed, truth, op, report
