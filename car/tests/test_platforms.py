"""Platform adapters — semantic ID <-> platform-name mapping, incl. def-name variants and gaps."""
from __future__ import annotations

from ecutune.core import tables as T
from ecutune.platforms import REGISTRY, platform_name, semantic_id


def test_subaru_primary_names():
    assert platform_name("subaru_ecuflash", T.FUEL_INJECTOR_FLOW) == "Injector Flow Scaling"
    assert platform_name("subaru_ecuflash", T.FUEL_INJECTOR_LATENCY) == "Injector Latency"
    assert platform_name("subaru_ecuflash", T.SENSOR_MAF_TRANSFER) == "MAF Sensor Scaling"


def test_subaru_reverse_and_variants():
    # primary spelling (2005 FXT A2WC400x def)
    assert semantic_id("subaru_ecuflash", "Injector Latency") == T.FUEL_INJECTOR_LATENCY
    # variant spelling from a sibling def (Forester 2.5 E2UE101J) resolves to the SAME semantic id
    assert semantic_id("subaru_ecuflash", "Injector Latency_") == T.FUEL_INJECTOR_LATENCY
    assert semantic_id("subaru_ecuflash", "Primary Open Loop Fueling A_") == T.FUEL_TARGET_AFR_PRIMARY_A
    assert semantic_id("subaru_ecuflash", "Nonexistent Table") is None


def test_tunerstudio_gaps_are_none():
    # speed-density platform: no MAF transfer — absence is "lever not available", not an error
    assert platform_name("tunerstudio", T.SENSOR_MAF_TRANSFER) is None
    assert platform_name("tunerstudio", T.FUEL_INJECTOR_LATENCY) == "injOpen"
    assert semantic_id("tunerstudio", "advTable1Tbl") == T.IGNITION_BASE_TIMING


def test_all_adapter_keys_are_known_semantic_ids():
    known = {v for k, v in vars(T).items() if k.isupper() and isinstance(v, str)}
    for pname, mod in REGISTRY.items():
        for sem in mod.TO_PLATFORM:
            assert sem in known, f"{pname} maps unknown semantic id {sem}"
        for sem in getattr(mod, "VARIANTS", {}):
            assert sem in known
