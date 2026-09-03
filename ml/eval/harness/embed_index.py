"""Dense retrieval index builder, retrieval-v2 (2026-07-22 overnight, Syed-ratified P2).

WHAT THIS IS (morning-read version): BM25 (retrieval-v1) matches exact words, so a datalog
phrase and a forum phrase meaning the same thing can score zero ("trims climbing at idle"
vs "additive fuel correction rising at closed throttle"). This builder runs every ref_fts
row through BGE-M3, a 568M-parameter embedding model trained contrastively so that
same-meaning texts land near each other, and stores one L2-normalized 1024-dim float32
vector per row. At query time retrieval.py embeds the question the same way and ranks
chunks by cosine similarity (a normalized dot product), then FUSES that ranking with BM25's
via Reciprocal Rank Fusion. Same text units as BM25 (identical rowids), so the two rankers
vote on the same candidates and RefSnippet provenance is unchanged.

DEVICE: defaults to CPU, zero VRAM, safe to run alongside training or serving, which is why
it was written that way. The "~15-25 min" figure that used to sit here was never measured: the
corpus is 5,638 chunks averaging ~2,700 chars, i.e. ~3.8M tokens through a 568M-parameter
model, which is ~4 HOURS on this box's 28 Broadwell cores (verified 2026-08-02 the slow way).
Pass --device cuda to run it on an idle GPU in ~4 minutes instead. Only do that when no model
is being served, the default stays CPU precisely so the safe choice is the automatic one.

Run: car/.venv/bin/python -m harness.embed_index                    (cwd: ml/eval)
     CUDA_VISIBLE_DEVICES=0 car/.venv/bin/python -m harness.embed_index --device cuda
Output: ml/eval/data/ref_dense_v2.npz  (~23 MB: 'vecs' [N,1024] f32, 'rowids' [N] i64,
'n_rows' i64 freshness stamp, 'built_at' str)
"""
from __future__ import annotations

import sqlite3
import time

import numpy as np

from .config import RetrievalCfg

MODEL_NAME = "BAAI/bge-m3"   # re-verified 2026-07-22: MIT, 2026 production default
BATCH = 16
MAX_CHARS = 6000             # BGE-M3 handles 8K tokens; chunks are <= ~1.5K tokens anyway


def source_rows(db_path, table: str = "ref_fts") -> list[tuple]:
    """(rowid, title, text) rows of an FTS table, rowid order, the embedding job's input.
    Split out (2026-08-16) so the community index uses the identical selection logic."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return conn.execute(f"SELECT rowid, title, text FROM {table} ORDER BY rowid").fetchall()
    finally:
        conn.close()


def build(cfg: RetrievalCfg | None = None, log=print, device: str = "cpu",
          batch: int | None = None, table: str = "ref_fts", out=None) -> None:
    """Embed every row of `table` into `out` (default: cfg.index_path for ref_fts).

    2026-08-16: `table`/`out` let the same builder produce a SEPARATE community index
    (e.g. table="community_fts", out=EVAL_DIR/"data/community_dense_v2.npz") carrying the same
    n_rows freshness stamp. Defaults are unchanged. NOT invoked on the real corpus tonight -
    nothing enters a retrieval index without Syed's sign-off.
    """
    cfg = cfg or RetrievalCfg()
    out = cfg.index_path if out is None else out
    from sentence_transformers import SentenceTransformer   # heavy import, kept local
    t0 = time.time()
    log(f"loading {MODEL_NAME} ({device})...")
    model = SentenceTransformer(MODEL_NAME, device=device)
    batch = batch or (64 if device.startswith("cuda") else BATCH)

    rows = source_rows(cfg.db_path, table)
    log(f"{len(rows)} {table} rows to embed")

    texts = [((t or "") + "\n" + (x or ""))[:MAX_CHARS] for _, t, x in rows]
    vecs = model.encode(texts, batch_size=batch, normalize_embeddings=True,
                        show_progress_bar=False, convert_to_numpy=True)
    rowids = np.array([r[0] for r in rows], dtype=np.int64)
    out.parent.mkdir(parents=True, exist_ok=True)
    # FRESHNESS STAMP (2026-08-02, audit finding A10): the index silently drifted 30 rows
    # behind ref_fts (5,608 vs 5,638) and nothing noticed, so those chunks were invisible to
    # the dense ranker for every hybrid cell of the showdown. Recording the source row count
    # IN the artifact lets retrieval.py compare against the live DB at load and shout.
    np.savez(out, vecs=vecs.astype(np.float32), rowids=rowids,
             n_rows=np.int64(len(rows)), built_at=np.str_(time.strftime("%F %T")),
             table=np.str_(table))
    log(f"index -> {out} ({vecs.shape[0]}x{vecs.shape[1]}, "
        f"{out.stat().st_size/1e6:.1f} MB, {time.time()-t0:.0f}s, "
        f"n_rows stamp {len(rows)})")


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    ap = argparse.ArgumentParser("embed_index")
    ap.add_argument("--device", default="cpu",
                    help="cpu (default, zero VRAM) or cuda (~60x faster; only when idle)")
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--table", default="ref_fts",
                    help="FTS table to embed (default ref_fts; community_fts for the "
                         "separate community index)")
    ap.add_argument("--out", default=None,
                    help="output .npz (default: RetrievalCfg().index_path; REQUIRED when "
                         "--table is not ref_fts so the reference index is never overwritten)")
    args = ap.parse_args()
    if args.table != "ref_fts" and not args.out:
        ap.error("--out is required for a non-reference table")
    build(device=args.device, batch=args.batch, table=args.table,
          out=Path(args.out) if args.out else None)
