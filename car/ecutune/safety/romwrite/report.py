"""The human CHANGE REPORT, what Syed reads before deciding to flash.

ROADMAP Phase E.4 requires it to carry "table, cell, old->new, which log evidence, which clamps
fired". The clamps' own docstring calls auditability a safety property: an edit made on a
model's say-so must be distinguishable from one the algorithm's neutral default made, which is
why `provenance` is printed prominently rather than buried.

Deliberately plain markdown -- it is meant to be read on a laptop in a garage.
"""
from __future__ import annotations

import numpy as np

from ...core.models import ClampResult, Proposal, Table
from .patcher import WriteResult


def change_report(prop: Proposal, result: ClampResult, write: WriteResult,
                  before: dict[str, Table], after: dict[str, Table],
                  rom_name: str = "") -> str:
    L: list[str] = []
    L.append(f"# CHANGE REPORT, {prop.stage}")
    L.append("")
    L.append(f"- ROM: `{rom_name or 'unnamed'}`")
    L.append(f"- proposal: `{prop.proposal_id}`  provenance: **{prop.provenance}**")
    L.append(f"- edits proposed: {len(prop.edits)} -> surviving clamps: {len(result.clamped_edits)}")
    L.append(f"- bytes changed: {sum(b - a for a, b in write.byte_ranges)} "
             f"in {len(write.byte_ranges)} range(s)")
    if write.checksum_repaired:
        L.append(f"- checksum records repaired: {list(write.checksum_repaired)}")
    if write.max_quantisation_error:
        L.append(f"- max storage quantisation error: {write.max_quantisation_error:.4g}")
    L.append("")

    for note in write.notes:
        L.append(f"> {note}")
    L.append("")

    by_table: dict[str, list] = {}
    for e in write.edits:
        by_table.setdefault(e.table_id, []).append(e)
    for table_id, edits in by_table.items():
        shape = np.asarray(before[table_id].values, float).shape
        b = np.asarray(before[table_id].values, float).ravel()
        a = np.asarray(after[table_id].values, float).ravel()
        # Row-major with X fastest, matching patcher._cell_offset: the linear index is
        # `row * n_x + col`, where n_x is the COLUMN COUNT. This previously read
        # `e.row * a.shape[0]`, but `a` has already been raveled -- so shape[0] was the total
        # element count (270 for Base Timing, not 15) and the first edit with row >= 1 either
        # indexed past the end or reported a completely unrelated cell. Never hit because the
        # only table ever written so far was a 1-D curve. Found 2026-08-30.
        n_x = shape[1] if len(shape) == 2 else 1
        L.append(f"## {table_id}  ({before[table_id].units})")
        L.append("")
        L.append("| cell | before | after | change |")
        L.append("|---|---|---|---|")
        for e in sorted(edits, key=lambda x: (x.row, x.col)):
            i = e.col if before[table_id].kind != "map_2d" else e.row * n_x + e.col
            pct = (a[i] / b[i] - 1) * 100 if b[i] else float("nan")
            L.append(f"| {e.row},{e.col} | {b[i]:.4g} | {a[i]:.4g} | {pct:+.1f}% |")
        L.append("")
        untouched = int(np.sum(np.abs(a - b) <= 1e-12))
        L.append(f"_{len(edits)} cells changed, {untouched} left at stock._")
        L.append("")

    if result.violations:
        L.append("## Clamps that fired")
        L.append("")
        L.append("| clamp | cell | requested | allowed | action |")
        L.append("|---|---|---|---|---|")
        for v in result.violations:
            L.append(f"| {v.clamp} | {v.row},{v.col} | {v.requested:.4g} | "
                     f"{v.allowed:.4g} | {v.action} |")
        L.append("")
    else:
        L.append("_No clamp modified any edit._")
        L.append("")

    reasons = sorted({e.reason for e in write.edits if e.reason})
    if reasons:
        L.append("## Evidence")
        L.append("")
        for r in reasons[:24]:
            L.append(f"- {r}")
        if len(reasons) > 24:
            L.append(f"- _(+{len(reasons) - 24} more)_")
        L.append("")

    L.append("---")
    L.append("**Nothing has been flashed.** This file is a candidate image; flashing stays a "
             "human act, against the checklist:")
    L.append("")
    L.append("- battery **maintainer on the car** (prevents a voltage sag mid-write)")
    L.append("- **laptop on its OWN BATTERY, fully charged, NOT on mains.** Revised "
             "2026-08-31: the old checklist said \"AC power\", and a mains-powered laptop plus a "
             "mains-powered charger are two earthed devices bonded through the OBD ground pin. "
             "A J2534 clone has no galvanic isolation, so any potential difference between them "
             "flows through the interface. See `ecu/INTERFACE-FAILURE-2026-08-31.md`.")
    L.append("- green test-mode connectors joined")
    L.append("- stock ROM archived in three places")
    L.append("- **the interface's LEDs confirmed lit before starting**: no lights means no "
             "power section, and starting anyway is how you brick an ECU mid-write")
    L.append("")
    L.append("Tool: **FastECU** (stock upstream build, profile `sub_ecu_denso_sh7058`). EcuFlash "
             "cannot be used on this ECU -- its SecurityAccess key is rejected even with the "
             "green connectors joined, retested 2026-08-29. See ecu/ROM-READ-BLOCKER.md.")
    return "\n".join(L)
