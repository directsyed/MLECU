"""Platform adapters: semantic table IDs <-> what each platform calls the table.

An adapter is data, not behavior: TO_PLATFORM maps semantic -> primary platform name (what the
ROM-write bridge / def parser uses), VARIANTS lists known alternate spellings across that
platform's definition files (per-ROM-def drift), and absence of a key means the platform simply
doesn't have that table (e.g. speed-density ECUs have no MAF transfer) — callers treat that as
"lever not available", not an error.
"""
from __future__ import annotations

from . import subaru_ecuflash, tunerstudio

REGISTRY = {
    subaru_ecuflash.PLATFORM: subaru_ecuflash,
    tunerstudio.PLATFORM: tunerstudio,
}


def platform_name(platform: str, semantic_id: str) -> str | None:
    """Primary platform table name for a semantic ID (None = platform lacks that table)."""
    return REGISTRY[platform].TO_PLATFORM.get(semantic_id)


def semantic_id(platform: str, name: str) -> str | None:
    """Semantic ID for a platform table name, matching primary names AND known variants."""
    mod = REGISTRY[platform]
    for sem, primary in mod.TO_PLATFORM.items():
        if name == primary or name in getattr(mod, "VARIANTS", {}).get(sem, ()):
            return sem
    return None
