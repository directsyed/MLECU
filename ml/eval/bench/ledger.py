"""Resumable work ledger for the multi-day benchmark pipeline (2026-07-29).

WHY THIS EXISTS: the pipeline spans ~4 days across burn-in, guard trials, and a 5-model
showdown, on a box whose 3090 has killed it 11 times. A bash chain cannot survive that.
This copies the judge's proven pattern (corpus_pipeline/core/state.py): sqlite + WAL,
idempotent migrate, atomic claim, all-or-nothing completion. A unit is either fully done
or fully pending, never half-credited, so a reboot mid-run resumes exactly where it
stopped.

THE VALIDATION RULE IS THE POINT. `harness.cli` exits 0 even when a run is garbage, so
"the process finished" proves nothing. A unit is `done` only if its output file passes
validate_output(): right row count, right model tag, retrieval actually happened on
retrieval arms, and the model actually answered. Everything else is `failed` with a reason.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
DB_PATH = BENCH_DIR / "bench.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS unit (
    id              INTEGER PRIMARY KEY,
    phase           TEXT NOT NULL,          -- burnin | guard | showdown
    seq             INTEGER NOT NULL,       -- execution order within phase
    model_key       TEXT NOT NULL,          -- '' for burn-in units
    label           TEXT NOT NULL,          -- human-readable unit name (unique)
    kind            TEXT NOT NULL,          -- shell | harness
    argv_json       TEXT NOT NULL,          -- shell: [cmd]; harness: [flags...]
    server_profile  TEXT NOT NULL DEFAULT '',
    arm             TEXT NOT NULL DEFAULT '',
    suite           TEXT NOT NULL DEFAULT '',
    model_tag       TEXT NOT NULL DEFAULT '',   -- expected `model` field in result rows
    n_rows_expected INTEGER NOT NULL DEFAULT 0,
    state           TEXT NOT NULL DEFAULT 'pending',
    attempts        INTEGER NOT NULL DEFAULT 0,
    started_at      TEXT, ended_at TEXT,
    out_path        TEXT, n_rows_got INTEGER, note TEXT,
    UNIQUE(label)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS unit_ready ON unit(state, phase, seq);
"""

TERMINAL = ("done", "skipped")

# Floor for "the model actually reasoned". Observed medians: Qwen3.6-35B ~1750-2010,
# gpt-oss (harmony analysis channel) ~208, Qwen3-Next-Instruct 8 (non-thinking = invalid).
# 40 sits well below any genuine reasoner and well above a bare grammar-constrained answer.
MIN_MEDIAN_TOKENS = 40

# Share of rows allowed to end at the token ceiling before the cell is rejected. Some
# truncation is normal on the hardest cases; a fifth of the run is a budget problem.
MAX_TRUNCATED_FRAC = 0.20


@contextmanager
def connect(path: Path | None = None):
    # resolved at CALL time, not def time, a default arg would bind DB_PATH at import
    # and silently ignore any later redirect (found by the test suite, 2026-07-29)
    conn = sqlite3.connect(path or DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")     # survive a hard box death mid-write
    try:
        yield conn
    finally:
        conn.close()


def init(path: Path | None = None) -> None:
    """Idempotent, safe to call on every driver start."""
    with connect(path) as c:
        c.executescript(SCHEMA)
        c.commit()


def add_unit(**kw) -> int:
    """Insert a unit; existing label is left untouched (idempotent re-seeding)."""
    cols = ("phase", "seq", "model_key", "label", "kind", "argv_json", "server_profile",
            "arm", "suite", "model_tag", "n_rows_expected")
    vals = {k: kw.get(k, "") for k in cols}
    vals["seq"] = int(kw.get("seq", 0))
    vals["n_rows_expected"] = int(kw.get("n_rows_expected", 0))
    with connect() as c:
        cur = c.execute(
            f"INSERT OR IGNORE INTO unit ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [vals[k] for k in cols])
        c.commit()
        return cur.lastrowid


def claim_next(phase: str | None = None) -> sqlite3.Row | None:
    """Atomically take the lowest-seq pending unit. Returns None when the phase is drained.

    Atomicity: the UPDATE's WHERE re-checks state='pending', so if two drivers ever race,
    exactly one gets rowcount 1 (same trick the judge uses on document rows)."""
    with connect() as c:
        q = "SELECT * FROM unit WHERE state='pending'"
        args: list = []
        if phase:
            q += " AND phase=?"
            args.append(phase)
        q += " ORDER BY phase, seq, id LIMIT 1"
        row = c.execute(q, args).fetchone()
        if row is None:
            return None
        upd = c.execute(
            "UPDATE unit SET state='running', attempts=attempts+1, started_at=?, note=NULL "
            "WHERE id=? AND state='pending'", (time.strftime("%F %T"), row["id"]))
        c.commit()
        if upd.rowcount != 1:
            return claim_next(phase)          # lost the race; take the next one
        return c.execute("SELECT * FROM unit WHERE id=?", (row["id"],)).fetchone()


def _finish(unit_id: int, state: str, note: str = "", out_path: str = "",
            n_rows_got: int | None = None) -> None:
    with connect() as c:
        c.execute("UPDATE unit SET state=?, ended_at=?, note=?, out_path=?, n_rows_got=? "
                  "WHERE id=?",
                  (state, time.strftime("%F %T"), note or None, out_path or None,
                   n_rows_got, unit_id))
        c.commit()


def mark_done(unit_id: int, out_path: str = "", n_rows_got: int | None = None,
              note: str = "") -> None:
    _finish(unit_id, "done", note, out_path, n_rows_got)


def mark_failed(unit_id: int, reason: str, out_path: str = "",
                n_rows_got: int | None = None) -> None:
    _finish(unit_id, "failed", reason, out_path, n_rows_got)


def mark_skipped(unit_id: int, reason: str) -> None:
    _finish(unit_id, "skipped", reason)


def requeue(unit_id: int, note: str = "") -> None:
    """Return a failed unit to pending (retry paths, or after a config change).

    Clears the PREVIOUS attempt's completion fields (2026-08-03). Leaving a stale `ended_at`
    on a pending unit makes every duration and ordering query built on it lie: the re-queued
    35B cell reported a running time of MINUS 228 minutes, because `ended_at` still held the
    moment its failed attempt died while `started_at` had moved forward to the retry.
    `out_path`/`n_rows_got` are cleared for the same reason; they describe an attempt that is
    no longer the unit's result.
    """
    with connect() as c:
        c.execute("UPDATE unit SET state='pending', note=?, ended_at=NULL, out_path=NULL, "
                  "n_rows_got=NULL WHERE id=?", (note or None, unit_id))
        c.commit()


def reset_running(note: str = "reset after driver restart") -> int:
    """Crash recovery: a unit left 'running' means the driver died mid-unit. Its output is
    untrusted (possibly truncated), so it goes back to pending for a clean re-run."""
    with connect() as c:
        cur = c.execute("UPDATE unit SET state='pending', note=? WHERE state='running'", (note,))
        c.commit()
        return cur.rowcount


def skip_model(model_key: str, reason: str) -> int:
    """Mark every remaining unit of a model skipped (arch unsupported, repeated OOM)."""
    with connect() as c:
        cur = c.execute("UPDATE unit SET state='skipped', note=?, ended_at=? "
                        "WHERE model_key=? AND state IN ('pending','failed')",
                        (reason, time.strftime("%F %T"), model_key))
        c.commit()
        return cur.rowcount


def set_meta(key: str, value: str) -> None:
    with connect() as c:
        c.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        c.commit()


def get_meta(key: str, default: str = "") -> str:
    with connect() as c:
        row = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def status() -> dict:
    with connect() as c:
        rows = c.execute("SELECT phase, state, COUNT(*) n FROM unit "
                         "GROUP BY phase, state").fetchall()
    out: dict = {}
    for r in rows:
        out.setdefault(r["phase"], {})[r["state"]] = r["n"]
    return out


# ---------------------------------------------------------------- validation

def validate_output(path: Path, model_tag: str, n_expected: int, arm: str,
                    min_answer_frac: float = 0.8) -> tuple[bool, str]:
    """The done-predicate. `harness.cli` exits 0 on garbage, so this is the real gate.

    Catches, in order: missing file; truncated/overlong run; wrong probe or case file
    (row count mismatch); mislabeled cell (model tag); silent arm-A degradation on a
    retrieval arm (arms.build_user returns [] refs when retrieve() finds nothing);
    and a model that returned nothing usable (thinking-budget exhaustion, or grammar
    unsupported on a new architecture; both produce well-formed empty rows).
    """
    if not path.exists():
        return False, "output file missing"
    try:
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    except json.JSONDecodeError as e:
        return False, f"unparseable output: {e}"
    if len(rows) != n_expected:
        return False, f"row count {len(rows)} != expected {n_expected}"
    bad_tag = {r.get("model") for r in rows} - {model_tag}
    if bad_tag:
        return False, f"wrong model tag in rows: {sorted(bad_tag)[:2]}"
    if arm in ("B", "D"):
        with_refs = sum(1 for r in rows if r.get("retrieved_doc_ids"))
        if with_refs == 0:
            return False, "retrieval arm returned ZERO refs on every row (silent arm-A degradation)"
    answered = sum(1 for r in rows if _has_answer(r))
    if answered < min_answer_frac * len(rows):
        return False, f"only {answered}/{len(rows)} rows carry an answer"
    # "answered" is not "engaged", the 2026-07-30 lesson. The Qwen3-Next Instruct variant
    # returned a valid grammar-constrained answer on every row in ~8 tokens, i.e. no
    # reasoning at all, and passed every other check. A thinking model that suddenly emits
    # near-zero tokens is either the wrong variant or has reasoning disabled, and its scores
    # are not a capability measurement. Flag it rather than silently banking the cell.
    # A MISSING field means the harness didn't record token counts, not evidence about the
    # model. Only judge when the field is actually present.
    toks = sorted(r["completion_tokens"] for r in rows
                  if r.get("completion_tokens") is not None)
    median = toks[len(toks) // 2] if toks else None
    if median is not None and median < MIN_MEDIAN_TOKENS:
        return False, (f"median completion_tokens {median} < {MIN_MEDIAN_TOKENS}: model is "
                       f"answering without reasoning (wrong variant / thinking disabled?)")
    # finish_reason census (2026-08-02). The 8192-token ceiling silently truncated Thinking
    # models mid-trace on 2026-07-31 and their blanks scored as misses, understating them by
    # up to 14pp, with nothing in the ledger to show it. A cell where a large share of rows
    # died at the ceiling is not a capability measurement, it is a budget measurement.
    census: dict[str, int] = {}
    for r in rows:
        census[str(r.get("finish_reason"))] = census.get(str(r.get("finish_reason")), 0) + 1
    n_len = census.get("length", 0)
    if n_len > MAX_TRUNCATED_FRAC * len(rows):
        return False, (f"{n_len}/{len(rows)} rows hit the token ceiling "
                       f"(finish_reason=length), raise --max-tokens before banking this cell")
    # a stale dense index or a silent hybrid->BM25 fallback changes what the model was shown
    if any(r.get("index_stale") for r in rows):
        return False, "rows report a STALE dense index, rebuild before banking this cell"
    if any(r.get("dense_fallback") for r in rows):
        return False, "hybrid silently fell back to BM25 (dense index unavailable)"
    cen = " ".join(f"{k}={v}" for k, v in sorted(census.items()))
    return True, f"ok ({len(rows)} rows, {answered} answered, median {median} tok; {cen})"


def _has_answer(row: dict) -> bool:
    a = row.get("answer")
    if isinstance(a, dict):                     # E2 shape
        return bool(a.get("value")) or bool(a.get("must_retrieve"))
    return bool(a)                              # E1 shape: the fault string
