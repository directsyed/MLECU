"""SQLite-backed corpus store: document upserts, dedup, gone-sweep, poll-run log.

Adapted from Hardware Parser's core/state.py (WAL, idempotent _migrate, upsert→(id,was_new),
dedup on (source, source_id), poll_run health). Listing→Document; qualify/alert bookkeeping
dropped (the LLM judge replaces it).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

from .models import SCHEMA_SQL, Document, dumps, utcnow_iso


class State:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        # Two writers can coexist during calibration (judge runner + labeling CLI): WAL
        # serializes them, busy_timeout makes the loser wait instead of throwing.
        self.conn.execute("PRAGMA busy_timeout=10000")
        self.conn.executescript(SCHEMA_SQL)
        self._migrate()

    def _migrate(self) -> None:
        """Idempotent ALTER TABLE for columns added after the initial schema.

        Convention (same as Hardware Parser): when you add a Document field, add it to
        models.SCHEMA_SQL AND here, then thread it through upsert_document().
        """
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(document)")}
        for col, decl in [
            ("judge_score", "INTEGER"),
            ("gone_at", "TEXT"),
            ("tier", "TEXT NOT NULL DEFAULT 'community'"),
            ("judge_model", "TEXT"),        # which model produced judge_score (audit)
            ("rubric_version", "TEXT"),     # which rubric it was scored under
            ("judged_at", "TEXT"),
        ]:
            if col not in existing:
                self.conn.execute(f"ALTER TABLE document ADD COLUMN {col} {decl}")
        existing_j = {row[1] for row in self.conn.execute("PRAGMA table_info(judgment)")}
        for col, decl in [
            ("relevance", "TEXT"),
            ("evidence_in_images", "INTEGER"),
        ]:
            if existing_j and col not in existing_j:
                self.conn.execute(f"ALTER TABLE judgment ADD COLUMN {col} {decl}")

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.conn.execute("BEGIN")
        try:
            yield self.conn
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def upsert_document(self, doc: Document) -> tuple[int, bool]:
        """Insert or update by (source, source_id). Returns (row_id, was_new)."""
        now = utcnow_iso()
        row = self.conn.execute(
            "SELECT id, first_seen FROM document WHERE source=? AND source_id=?",
            (doc.source, doc.source_id),
        ).fetchone()
        if row is None:
            cur = self.conn.execute(
                """INSERT INTO document (
                    source, source_id, kind, domain, tier, title, text, url, meta_json,
                    content_hash, token_est, gate_status, gate_flags,
                    judgment_status, judge_score, first_seen, last_seen, miss_streak
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                (
                    doc.source, doc.source_id, doc.kind, doc.domain, doc.tier, doc.title, doc.text,
                    doc.url, dumps(doc.meta), doc.content_hash, doc.token_est,
                    doc.gate_status, dumps(doc.gate_flags), doc.judgment_status,
                    doc.judge_score, now, now,
                ),
            )
            return cur.lastrowid, True
        # Existing — refresh content, keep first_seen, reset miss_streak. If the content
        # changed, reset judgment so the judge re-scores it.
        prev = self.conn.execute(
            "SELECT content_hash FROM document WHERE id=?", (row["id"],)
        ).fetchone()
        changed = prev is None or prev["content_hash"] != doc.content_hash
        self.conn.execute(
            """UPDATE document SET
                kind=?, domain=?, tier=?, title=?, text=?, url=?, meta_json=?,
                content_hash=?, token_est=?, gate_status=?, gate_flags=?,
                last_seen=?, miss_streak=0, gone_at=NULL"""
            + (", judgment_status='pending', judge_score=NULL" if changed else "")
            + " WHERE id=?",
            (
                doc.kind, doc.domain, doc.tier, doc.title, doc.text, doc.url, dumps(doc.meta),
                doc.content_hash, doc.token_est, doc.gate_status, dumps(doc.gate_flags),
                now, row["id"],
            ),
        )
        return row["id"], False

    def sweep_gone(self, source: str, seen_ids: Iterable[str], gone_after: int) -> int:
        """Increment miss_streak for docs of `source` not seen this run; mark gone_at past
        threshold. Returns count newly marked gone."""
        seen = set(seen_ids)
        rows = self.conn.execute(
            "SELECT id, source_id, miss_streak FROM document WHERE source=? AND gone_at IS NULL",
            (source,),
        ).fetchall()
        now = utcnow_iso()
        newly_gone = 0
        for r in rows:
            if r["source_id"] in seen:
                continue
            streak = r["miss_streak"] + 1
            if streak >= gone_after:
                self.conn.execute(
                    "UPDATE document SET miss_streak=?, gone_at=? WHERE id=?",
                    (streak, now, r["id"]),
                )
                newly_gone += 1
            else:
                self.conn.execute(
                    "UPDATE document SET miss_streak=? WHERE id=?", (streak, r["id"])
                )
        return newly_gone

    # --- poll-run health -------------------------------------------------
    def start_poll_run(self, source: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO poll_run (started_at, source, ok) VALUES (?, ?, 0)",
            (utcnow_iso(), source),
        )
        return cur.lastrowid

    def finish_poll_run(self, run_id: int, *, ok: bool, fetched: int = 0,
                        kept: int = 0, new_count: int = 0, error: str | None = None) -> None:
        self.conn.execute(
            """UPDATE poll_run SET finished_at=?, ok=?, fetched=?, kept=?, new_count=?, error=?
               WHERE id=?""",
            (utcnow_iso(), int(ok), fetched, kept, new_count, error, run_id),
        )

    # --- read helpers (verification / downstream) ------------------------
    def counts_by_source(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT source, tier, kind,
                      COUNT(*) AS docs,
                      SUM(gate_status='kept') AS kept,
                      SUM(judgment_status='pending') AS pending_judge
               FROM document WHERE gone_at IS NULL
               GROUP BY source, tier, kind ORDER BY tier DESC, source"""
        ).fetchall()

    def pending_for_judge(self, limit: int = 100,
                          sources: tuple[str, ...] | None = None) -> list[sqlite3.Row]:
        """Next docs awaiting the judge, oldest first. `sources` filters in SQL — filtering
        after the fetch would starve the batch when the low ids are all other sources.

        NO `gone_at` filter — deliberately (fixed 2026-08-16). The gone-sweep policy ratified
        2026-07-22 (decisions.md, "NARROW") says gone-ness affects SCRAPING only, never judging,
        retrieval or pair-mining: archived text is first-class corpus material forever. This
        query still carried `AND gone_at IS NULL`, which hid 303 of the 314 pending community
        docs (all gone-marked by the 2026-06-26 sweep) from every judge run for a month.
        """
        if sources:
            marks = ",".join("?" * len(sources))
            return self.conn.execute(
                f"""SELECT * FROM document
                    WHERE gate_status='kept' AND judgment_status='pending'
                      AND source IN ({marks})
                    ORDER BY id LIMIT ?""",
                (*sources, limit),
            ).fetchall()
        return self.conn.execute(
            """SELECT * FROM document
               WHERE gate_status='kept' AND judgment_status='pending'
               ORDER BY id LIMIT ?""",
            (limit,),
        ).fetchall()

    # --- Stage-B judge writes (curation harness) --------------------------
    def mark_judged(self, doc_id: int, *, score: int, judge_model: str,
                    rubric_version: str, chunks: list[dict]) -> None:
        """Record a full judgment atomically: per-chunk verdict rows + the document rollup.

        `chunks`: [{chunk_index, n_chunks, score, rationale, pairs_json, grounding_json,
                    prompt_tokens, completion_tokens}]. All-or-nothing by design — a crash
        mid-doc leaves judgment_status='pending' so the next run re-picks it cleanly.
        """
        now = utcnow_iso()
        with self.transaction() as conn:
            for ch in chunks:
                conn.execute(
                    """INSERT OR REPLACE INTO judgment (
                        doc_id, chunk_index, n_chunks, score, rationale, pairs_json,
                        grounding_json, judge_model, rubric_version,
                        prompt_tokens, completion_tokens, relevance, evidence_in_images,
                        created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (doc_id, ch.get("chunk_index", 0), ch.get("n_chunks", 1),
                     ch.get("score"), ch.get("rationale"), ch.get("pairs_json"),
                     ch.get("grounding_json"), judge_model, rubric_version,
                     ch.get("prompt_tokens"), ch.get("completion_tokens"),
                     ch.get("relevance"), ch.get("evidence_in_images"), now),
                )
            conn.execute(
                """UPDATE document SET judgment_status='judged', judge_score=?,
                   judge_model=?, rubric_version=?, judged_at=? WHERE id=?""",
                (score, judge_model, rubric_version, now, doc_id),
            )

    def mark_judge_failed(self, doc_id: int, reason: str = "") -> None:
        """Park a doc that exhausted retries so the batch loop can't spin on it.
        (pending_for_judge filters on ='pending', so 'failed' is naturally excluded.)"""
        self.conn.execute(
            "UPDATE document SET judgment_status='failed', judged_at=? WHERE id=?",
            (utcnow_iso(), doc_id),
        )

    def reset_failed_judgments(self) -> int:
        """failed -> pending (e.g. after a server fix). Returns rows flipped."""
        cur = self.conn.execute(
            "UPDATE document SET judgment_status='pending' WHERE judgment_status='failed'"
        )
        return cur.rowcount

    def reference_kept_count(self) -> int:
        """Cheap staleness signal for the grounding index."""
        return self.conn.execute(
            """SELECT COUNT(*) FROM document
               WHERE tier='reference' AND gate_status='kept' AND gone_at IS NULL"""
        ).fetchone()[0]

    def reference_kept_docs(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT id, title, text FROM document
               WHERE tier='reference' AND gate_status='kept' AND gone_at IS NULL"""
        ).fetchall()

    # --- community index (2026-08-16, Syed ruling 3: SEPARATE from ref_fts) ------------
    # NO gone_at filter here — 624 of 641 kept community docs are gone-marked (2026-06-26
    # sweep) and the ratified NARROW policy says gone-ness affects scraping only. Copying the
    # reference predicate verbatim would index 17 documents and call it done.
    def community_kept_count(self, min_score: int) -> int:
        return self.conn.execute(
            """SELECT COUNT(*) FROM document
               WHERE tier='community' AND gate_status='kept' AND judge_score >= ?""",
            (min_score,),
        ).fetchone()[0]

    def community_kept_docs(self, min_score: int) -> list[sqlite3.Row]:
        """Judged-and-kept community docs (score >= min_score), gone or not, for the
        community retrieval index. `document.tier` is read, never written."""
        return self.conn.execute(
            """SELECT id, title, text, source, source_id, judge_score FROM document
               WHERE tier='community' AND gate_status='kept' AND judge_score >= ?
               ORDER BY id""",
            (min_score,),
        ).fetchall()

    # --- calibration / spot-check labels ----------------------------------
    def add_label(self, doc_id: int, *, score: int, label_set: str,
                  rater: str = "syed", notes: str = "") -> None:
        self.conn.execute(
            """INSERT INTO human_label (doc_id, score, notes, label_set, rater, created_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(doc_id, label_set, rater)
               DO UPDATE SET score=excluded.score, notes=excluded.notes,
                             created_at=excluded.created_at""",
            (doc_id, score, notes, label_set, rater, utcnow_iso()),
        )

    def labels(self, label_set: str, rater: str | None = None) -> list[sqlite3.Row]:
        if rater:
            return self.conn.execute(
                "SELECT * FROM human_label WHERE label_set=? AND rater=? ORDER BY doc_id",
                (label_set, rater),
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM human_label WHERE label_set=? ORDER BY doc_id, rater",
            (label_set,),
        ).fetchall()

    def total_docs(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM document WHERE gone_at IS NULL").fetchone()[0]

    def recent_titles(self, limit: int = 8) -> list[str]:
        """Titles of the most-recently-inserted docs (new docs get the highest ids)."""
        rows = self.conn.execute("SELECT title FROM document ORDER BY id DESC LIMIT ?", (limit,))
        return [r["title"] for r in rows]

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
