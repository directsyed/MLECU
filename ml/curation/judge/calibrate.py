"""Calibration: freeze a sample, capture trusted labels, measure judge agreement.

Protocol (D4): Syed blind-rates a subset FIRST (anti-anchoring), Claude rates everything with
full project context, divergence on the blind subset validates/recalibrates Claude's ratings,
Syed guard-reviews the rest, and the adjudicated labels become the ground truth the local
judge must agree with. Pass bars are pre-registered before anyone sees agreement numbers.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field

from corpus_pipeline.core.state import State

from .config import Config

_SET_KEY = "label_set:{name}"


def freeze_sample(state: State, cfg: Config) -> list[int]:
    """Freeze the calibration doc-id list in meta (idempotent — returns the existing set).

    Composition: ALL kept community docs (there are ~96 today — labeling the full tier is a
    feature) + a few reference anchors for scale grounding, capped at calibration.n.
    """
    key = _SET_KEY.format(name=cfg.calibration.set_name)
    existing = state.get_meta(key)
    if existing:
        return json.loads(existing)
    community = [r["id"] for r in state.conn.execute(
        """SELECT id FROM document WHERE tier='community' AND gate_status='kept'
           AND gone_at IS NULL ORDER BY id""")]
    n_ref = max(0, min(8, cfg.calibration.n - len(community)))
    rng = random.Random(0)
    refs = [r["id"] for r in state.conn.execute(
        """SELECT id FROM document WHERE tier='reference' AND gate_status='kept'
           AND gone_at IS NULL""")]
    sample = community + (rng.sample(refs, min(n_ref, len(refs))) if refs else [])
    state.set_meta(key, json.dumps(sample))
    return sample


def blind_subset(state: State, cfg: Config) -> list[int]:
    """The deterministic subset Syed rates blind (seeded shuffle of the frozen sample)."""
    ids = freeze_sample(state, cfg)
    rng = random.Random(42)
    shuffled = list(ids)
    rng.shuffle(shuffled)
    return shuffled[:cfg.calibration.blind_subset]


# --- agreement metrics (hand-rolled; no scipy) -------------------------------------------

def _spearman(a: list[int], b: list[int]) -> float:
    def ranks(xs: list[int]) -> list[float]:
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return num / (da * db) if da and db else 0.0


@dataclass
class Agreement:
    n: int
    exact_pct: float
    within1_pct: float
    spearman: float
    confusion: list[list[int]]                 # [truth-1][judged-1]
    keep_agree_pct: float                      # both sides of threshold agree
    dangerous: int                             # truth <=2 but judge >= threshold
    pairs: list[tuple[int, int, int]] = field(default_factory=list)  # (doc_id, truth, judged)


def agreement(state: State, cfg: Config, *, label_set: str, truth_rater: str,
              judged_scores: dict[int, int] | None = None,
              other_rater: str | None = None) -> Agreement:
    """Agreement of `judged` vs `truth_rater` labels over a label set.

    judged side = the judge's document.judge_score by default, or another rater's labels
    (e.g. truth='syed' vs other='claude' for the blind-subset divergence check).
    """
    truth = {r["doc_id"]: r["score"] for r in state.labels(label_set, rater=truth_rater)}
    if other_rater is not None:
        judged = {r["doc_id"]: r["score"] for r in state.labels(label_set, rater=other_rater)}
    elif judged_scores is not None:
        judged = judged_scores
    else:
        judged = {}
        for doc_id in truth:
            row = state.conn.execute("SELECT judge_score FROM document WHERE id=?",
                                     (doc_id,)).fetchone()
            if row and row["judge_score"] is not None:
                judged[doc_id] = row["judge_score"]
    common = sorted(set(truth) & set(judged))
    if not common:
        raise ValueError(f"no overlapping labels for set={label_set}")
    t = [truth[i] for i in common]
    j = [judged[i] for i in common]
    thr = cfg.judge.keep_threshold
    conf = [[0] * 5 for _ in range(5)]
    for a, b in zip(t, j):
        conf[a - 1][b - 1] += 1
    return Agreement(
        n=len(common),
        exact_pct=100 * sum(a == b for a, b in zip(t, j)) / len(common),
        within1_pct=100 * sum(abs(a - b) <= 1 for a, b in zip(t, j)) / len(common),
        spearman=_spearman(t, j),
        confusion=conf,
        keep_agree_pct=100 * sum((a >= thr) == (b >= thr) for a, b in zip(t, j)) / len(common),
        dangerous=sum(1 for a, b in zip(t, j) if a <= 2 and b >= thr),
        pairs=[(i, truth[i], judged[i]) for i in common],
    )


def format_report(ag: Agreement, thr: int) -> str:
    lines = [
        f"n={ag.n}  exact={ag.exact_pct:.1f}%  within±1={ag.within1_pct:.1f}%  "
        f"spearman={ag.spearman:.3f}",
        f"keep/drop agreement @>={thr}: {ag.keep_agree_pct:.1f}%   "
        f"DANGEROUS (truth<=2, judged>={thr}): {ag.dangerous}",
        "confusion (rows=truth 1..5, cols=judged 1..5):",
    ]
    for i, row in enumerate(ag.confusion, 1):
        lines.append(f"  {i} | " + " ".join(f"{c:3d}" for c in row))
    return "\n".join(lines)
