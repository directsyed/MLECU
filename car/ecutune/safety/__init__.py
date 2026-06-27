"""The write-path guard. `apply_proposal` is THE ONLY function in the whole car/ package that
turns a Proposal into applied Table edits — every write (algorithm, future LLM, human override)
goes through here, so "the LLM never writes ECU values directly" is true by construction.
"""
from __future__ import annotations

from ..core.models import ClampContext, ClampResult, Proposal, TableSet
from .pipeline import CLAMP_PIPELINE, apply_clamps

__all__ = ["apply_proposal", "apply_clamps", "CLAMP_PIPELINE"]


def apply_proposal(tables: TableSet, prop: Proposal, ctx: ClampContext) -> tuple[TableSet, ClampResult]:
    """Clamp the proposal, then apply the surviving edits to a COPY of the tables.

    Returns (new_tables, result). If the proposal is blocked (knock abort / deferral) or nothing
    survives, the tables are returned UNCHANGED. This is the only call site permitted to invoke
    TableSet.with_edits — enforced by the meta-test in tests/test_write_path.py.
    """
    result = apply_clamps(prop, ctx)
    if not result.ok or not result.clamped_edits:
        return tables, result
    return tables.with_edits(result.clamped_edits), result
