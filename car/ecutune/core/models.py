"""Core data contracts for the deterministic tuning layer — THE types every module shares.

Mirrors corpus_pipeline/core/models.py (dataclass + __post_init__ + dumps/loads), adapted
from documents to ECU tables/proposals.

The load-bearing safety object is `Proposal`: the typed unit of change. A Proposal NEVER
reaches a Table except through safety.apply_proposal(). The future LLM is just another
Proposal producer — same path, same clamps, same audit trail. That is what makes "the LLM
never writes ECU values" true *by construction*, not by promise.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace

import numpy as np

from .config import SafetyCfg


@dataclass(frozen=True)
class TableAxis:
    name: str                       # "rpm" | "load" | "airflow_gs" | "battery_v"
    breakpoints: tuple[float, ...]
    units: str = ""


@dataclass
class Table:
    """An ECU table: a scalar, a 1-D curve, or a 2-D map.

    `values` is a numpy array of shape (), (n,) or (rows, cols). Tables are treated as
    immutable by callers: every edit goes through with_edit(), which returns a COPY. Only
    safety.apply_proposal builds edited tables.
    """
    table_id: str                   # canonical ECUFlash name (see core/tables.py)
    kind: str                       # "scalar" | "curve_1d" | "map_2d"
    values: np.ndarray
    units: str = ""
    hard_min: float = -math.inf     # absolute floor (config / base-def) — never crossable
    hard_max: float = math.inf
    x_axis: TableAxis | None = None   # cols (load / airflow / battery_v)
    y_axis: TableAxis | None = None   # rows (rpm)

    def __post_init__(self) -> None:
        self.values = np.asarray(self.values, dtype=float)

    def current(self, edit: CellEdit) -> float:
        if self.kind == "scalar":
            return float(self.values.reshape(-1)[0])
        if self.kind == "curve_1d":
            return float(self.values[edit.col])
        return float(self.values[edit.row, edit.col])

    def with_edit(self, edit: CellEdit, new_value: float) -> Table:
        arr = self.values.copy()
        if self.kind == "scalar":
            arr.reshape(-1)[0] = new_value
        elif self.kind == "curve_1d":
            arr[edit.col] = new_value
        else:
            arr[edit.row, edit.col] = new_value
        return replace(self, values=arr)

    def cell_x(self, edit: CellEdit) -> float | None:
        """The x-axis (load/airflow/battery_v) value at this cell, if any."""
        if self.x_axis is None:
            return None
        idx = edit.col if edit.col >= 0 else 0
        if 0 <= idx < len(self.x_axis.breakpoints):
            return self.x_axis.breakpoints[idx]
        return None

    def cell_rpm(self, edit: CellEdit) -> float | None:
        if self.y_axis is None:
            return None
        idx = edit.row if edit.row >= 0 else 0
        if 0 <= idx < len(self.y_axis.breakpoints):
            return self.y_axis.breakpoints[idx]
        return None


@dataclass(frozen=True)
class CellEdit:
    """One proposed cell change. new_value is ABSOLUTE (not a delta) so the clamp layer can
    always recompute the delta against the live table and re-clamp idempotently."""
    table_id: str
    row: int                        # y/rpm index (use 0 for scalar/1-D)
    col: int                        # x/load index (use 0 for scalar)
    new_value: float
    reason: str = ""

    def to_dict(self) -> dict:
        return {"table_id": self.table_id, "row": self.row, "col": self.col,
                "new_value": self.new_value, "reason": self.reason}

    @staticmethod
    def from_dict(d: dict) -> CellEdit:
        return CellEdit(d["table_id"], int(d["row"]), int(d["col"]),
                        float(d["new_value"]), d.get("reason", ""))


@dataclass
class Proposal:
    """The typed unit of change. Today only car/algorithms produces these; tomorrow the LLM
    produces the identical object (provenance="llm:vN"). Kept JSON-serializable so the audit
    log records who proposed what."""
    proposal_id: str
    stage: str                      # "idle_stage2" | "stage3_boost" | ...
    edits: tuple[CellEdit, ...]
    targets_kind: str               # "fuel" | "timing" | "boost" — drives ordering clamps
    provenance: str                 # "algorithm:idle_global_scalar" | "llm:vN" | "human"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"proposal_id": self.proposal_id, "stage": self.stage,
                "edits": [e.to_dict() for e in self.edits],
                "targets_kind": self.targets_kind, "provenance": self.provenance,
                "metadata": self.metadata}

    @staticmethod
    def from_dict(d: dict) -> Proposal:
        return Proposal(d["proposal_id"], d["stage"],
                        tuple(CellEdit.from_dict(e) for e in d["edits"]),
                        d["targets_kind"], d["provenance"], d.get("metadata", {}))


@dataclass(frozen=True)
class ClampViolation:
    """One audit-trail entry: a clamp modified or rejected an edit. Every modification is
    recorded — auditability is itself a safety property (and a future training signal)."""
    clamp: str                      # e.g. "ve_rate_limit"
    table_id: str
    row: int
    col: int
    requested: float
    allowed: float
    action: str                     # "rate_limited" | "floored" | "aborted" | "deferred"


@dataclass
class ClampResult:
    ok: bool                        # False => proposal hard-blocked (aborted or fully deferred)
    clamped_edits: tuple[CellEdit, ...]
    violations: tuple[ClampViolation, ...] = ()
    aborted_by: str | None = None   # set iff a hard-abort clamp fired (e.g. knock)


@dataclass
class TableSet:
    """A named collection of the tables under tuning."""
    tables: dict[str, Table]

    def get(self, table_id: str) -> Table:
        return self.tables[table_id]

    def current(self, edit: CellEdit) -> float:
        return self.tables[edit.table_id].current(edit)

    def with_edits(self, edits) -> TableSet:
        new = dict(self.tables)
        for e in edits:
            new[e.table_id] = new[e.table_id].with_edit(e, e.new_value)
        return TableSet(new)

    def copy(self) -> TableSet:
        return TableSet({k: replace(v, values=v.values.copy()) for k, v in self.tables.items()})


@dataclass
class ClampContext:
    """Everything a clamp needs beyond the Proposal: the current tables (to compute deltas),
    live signals (knock, trims, wideband), and the resolved safety limits."""
    tables: TableSet
    safety: SafetyCfg
    knock_active: bool = False
    # --- 2026-08-05: the deterministic layer's OWN verdict, and the stock baseline -----------
    # `fault_estimate` is an algorithms.identify.FaultEstimate (typed loosely to avoid a
    # core -> algorithms import cycle). When present, clamp_diagnosis_agreement requires the
    # proposal to move the SAME table the layer's own analysis points at. This is what makes the
    # LLM a pointer rather than a command: E4 showed a single-iteration slip could permanently
    # bend a table because the layer had no independent basis on which to disagree.
    fault_estimate: object | None = None
    # The archived stock-ROM values. clamp_ve_rate_limit bounds RATE (3%/iteration) and nothing
    # bounded cumulative displacement — 12 iterations compounds to 43%. clamp_belief_envelope
    # bounds distance from here.
    baseline_tables: TableSet | None = None
    fuel_trims_converged: bool = False    # gates fuel_before_timing
    steady_state_ok: bool = False         # gates steady_before_transient
    wideband_tracking: bool = False       # gates boost
    boost_control_verified: bool = False  # gates boost
    max_trim_abs: float = 0.0             # current |trim| over the window (boost +/-5% gate)


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def loads(s: str | None):
    if not s:
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None
