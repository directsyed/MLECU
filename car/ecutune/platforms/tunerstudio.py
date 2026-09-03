"""TunerStudio (Speeduino) adapter, semantic IDs -> speeduino.ini names.

Exists primarily to PROVE the universal seam with a second platform: the same semantic vocabulary
maps onto an open ECU's tables (names from the ingested tunerstudio_ini corpus source). Coverage
is honest. Speeduino is typically speed-density, so SENSOR_MAF_TRANSFER is simply absent, and
fuel scaling is the reqFuel constant rather than a table. Absence == lever not available.
"""
from __future__ import annotations

from ..core import tables as T

PLATFORM = "tunerstudio"

TO_PLATFORM: dict[str, str] = {
    T.FUEL_INJECTOR_LATENCY: "injOpen",            # injector opening/dead time
    T.FUEL_INJECTOR_FLOW: "reqFuel",               # required-fuel scalar (flow analog)
    T.IGNITION_BASE_TIMING: "advTable1Tbl",        # ignition advance table
    T.FUEL_TARGET_AFR_PRIMARY_A: "afrTable1Tbl",   # AFR target table
    # SENSOR_MAF_TRANSFER intentionally absent (speed-density platform)
}

VARIANTS: dict[str, tuple[str, ...]] = {}
