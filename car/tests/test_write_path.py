"""The meta-invariant: apply_proposal is the ONLY path from a Proposal to a written Table, and
nothing outside safety/ mutates table values. This is what makes the safety separation structural."""
from __future__ import annotations

import pathlib
import re

import numpy as np

from ecutune.core.config import load_config
from ecutune.core.models import CellEdit, ClampContext, Proposal, Table, TableSet
from ecutune.safety import apply_proposal

SAFETY = load_config().safety


def _ts(val=750.0):
    return TableSet({"Injector Flow Scaling": Table("Injector Flow Scaling", "scalar",
                                                    np.array(float(val)), units="cc/min")})


def _prop(new):
    return Proposal("p", "idle_stage2", (CellEdit("Injector Flow Scaling", 0, 0, new),),
                    "fuel", "algorithm:test")


def test_apply_proposal_unchanged_on_knock():
    ts = _ts(750.0)
    new_ts, res = apply_proposal(ts, _prop(760.0), ClampContext(ts, SAFETY, knock_active=True))
    assert res.ok is False
    assert float(new_ts.tables["Injector Flow Scaling"].values) == 750.0   # nothing written
    assert float(ts.tables["Injector Flow Scaling"].values) == 750.0       # original unmutated


def test_apply_proposal_writes_clamped_value():
    ts = _ts(750.0)
    new_ts, res = apply_proposal(ts, _prop(900.0), ClampContext(ts, SAFETY))  # +20% -> clamped 3%
    assert float(new_ts.tables["Injector Flow Scaling"].values) == 772.5
    assert float(ts.tables["Injector Flow Scaling"].values) == 750.0          # COPY semantics


def test_only_safety_layer_applies_edits():
    """Source scan: no module outside safety/ may call TableSet.with_edits, and no module
    outside core/models.py may mutate `.values[...]` in place. Cheap structural insurance."""
    root = pathlib.Path(__file__).resolve().parents[1] / "ecutune"
    offenders = []
    for p in root.rglob("*.py"):
        rel = p.relative_to(root)
        text = p.read_text(encoding="utf-8")
        if ".with_edits(" in text and rel.parts[0] != "safety" and rel.name != "models.py":
            offenders.append((str(rel), "calls with_edits"))
        if re.search(r"\.values\s*\[[^\]]*\]\s*=(?!=)", text) and rel.name != "models.py":
            offenders.append((str(rel), "in-place .values[] mutation"))
    assert offenders == [], f"write-path violations: {offenders}"
