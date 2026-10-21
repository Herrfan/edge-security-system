"""Vector index backed by sqlite-vec.

sqlite-vec adds a virtual table `vec0` to SQLite that exposes KNN (k-nearest
neighbour) queries through the MATCH keyword. This module wraps that with
typed row handling: each vector row carries chunk metadata plus the embedding
bytes. The application sees numpy arrays; SQLite sees packed float32.

Design notes:
  - We keep a companion table `knowledge_chunks` with all the text + source
    metadata, and only store the raw bytes in the vec0 virtual table.
  - Chunk rowid is stable across re-imports; re-sync drops and rebuilds.
  - `enable_load_extension(True)` is required on fresh sqlite3 connections.
"""
from __future__ import annotations

import logging
import sqlite3
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VecQueryHit:
    chunk_id: str
    document_id: str
    rowid: int          # sqlite-vec rowid (stable within one rebuild)
    distance: float     # l2 distance — smaller is better
    score: float        # 0..1 higher is better (converted from distance)


class VecIndex:
    """sqlite-vec wrapper for chunk embeddings."""

    VEC_TABLE = "vec_chunks"
    DATA_TABLE = "knowledge_chunks"

    def __init__(self, db_path: str | Path, *, dim: int = 768) -> None:
        self._db_path = str(db_path)
        self._dim = dim
        # Ensure directory
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # -------- connection helpers ----------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.enable_load_extension(True)
        try:
            import sqlite_vec  # noqa: F401
            sqlite_vec.load(conn)
        finally:
            conn.enable_load_extension(False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            # Metadata table: one row per chunk, carries source + text
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.DATA_TABLE} (
                    rowid          INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_id       TEXT NOT NULL UNIQUE,
                    document_id    TEXT NOT NULL,
                    source         TEXT NOT NULL,
                    source_ref     TEXT NOT NULL,
                    title          TEXT NOT NULL,
                    content        TEXT NOT NULL,
                    source_url     TEXT,
                    published_at   TEXT
                )
            """)
            # Virtual vec0 table — dim must match embeddings exactly
            conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {self.VEC_TABLE} USING vec0(
                    embedding float[{self._dim}]
                )
            """)
            conn.commit()
        finally:
            conn.close()

    # -------- write ----------

    def reset(self) -> None:
        """Drop and recreate. Safe during knowledge sync."""
        conn = self._connect()
        try:
            conn.execute(f"DROP TABLE IF EXISTS {self.VEC_TABLE}")
            conn.execute(f"DROP TABLE IF EXISTS {self.DATA_TABLE}")
            conn.commit()
        finally:
            conn.close()
        self._init_schema()

    def upsert(
        self,
        *,
        chunk_id: str,
        document_id: str,
        source: str,
        source_ref: str,
        title: str,
        content: str,
        source_url: Optional[str] = None,
        published_at: Optional[str] = None,
        vector: np.ndarray,
    ) -> int:
        """Insert or replace one chunk + its vector. Returns rowid."""
        if vector.shape[0] != self._dim:
            raise ValueError(f"vector dim mismatch: got {vector.shape[0]}, want {self._dim}")

        vec_bytes = struct.pack(f"{self._dim}f", *vector.astype(np.float32).tolist())

        conn = self._connect()
        try:
            # Upsert metadata
            cur = conn.execute(
                f"""
                INSERT INTO {self.DATA_TABLE}
                    (chunk_id, document_id, source, source_ref, title, content, source_url, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    content=excluded.content, source_ref=excluded.source_ref
                """,
                (chunk_id, document_id, source, source_ref, title, content, source_url, published_at),
            )
            rowid = cur.lastrowid

            # Upsert vector — vec0 is keyed by rowid (not by any column name)
            # We store the rowid from the data table as the key
            conn.execute(f"DELETE FROM {self.VEC_TABLE} WHERE rowid = ?", (rowid,))
            conn.execute(
                f"INSERT INTO {self.VEC_TABLE}(rowid, embedding) VALUES (?, ?)",
                (rowid, vec_bytes),
            )
            conn.commit()
            return rowid
        finally:
            conn.close()

    def bulk_upsert(self, rows: Sequence[dict]) -> int:
        """Bulk write a list of upsert dicts. Returns count."""
        count = 0
        for r in rows:
            self.upsert(**r)
            count += 1
        return count

    # -------- read ----------

    def search(self, query_vector: np.ndarray, *, top_k: int = 10) -> List[VecQueryHit]:
        """KNN search via vec0. Lower distance → higher score.

        sqlite-vec vec0 requires an explicit `k = N` in the WHERE clause;
        the ORDER BY distance constraint is implicit in the MATCH + k form.
        """
        if query_vector.shape[0] != self._dim:
            raise ValueError(f"query vector dim mismatch: got {query_vector.shape[0]}, want {self._dim}")
        q_bytes = struct.pack(f"{self._dim}f", *query_vector.astype(np.float32).tolist())

        conn = self._connect()
        try:
            cur = conn.execute(
                f"""
                SELECT v.rowid, v.distance, d.chunk_id, d.document_id
                FROM {self.VEC_TABLE} v
                JOIN {self.DATA_TABLE} d ON d.rowid = v.rowid
                WHERE v.embedding MATCH ? AND k = ?
                ORDER BY v.distance
                """,
                (q_bytes, top_k),
            )
            hits = []
            for row in cur.fetchall():
                dist = float(row["distance"])
                score = 1.0 / (1.0 + dist)
                hits.append(VecQueryHit(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    rowid=row["rowid"],
                    distance=dist,
                    score=score,
                ))
            return hits
        finally:
            conn.close()

    def count(self) -> int:
        conn = self._connect()
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {self.DATA_TABLE}").fetchone()[0]
        finally:
            conn.close()

    def get_chunk_text(self, rowid: int) -> Optional[str]:
        conn = self._connect()
        try:
            r = conn.execute(
                f"SELECT content FROM {self.DATA_TABLE} WHERE rowid = ?", (rowid,)
            ).fetchone()
            return r["content"] if r else None
        finally:
            conn.close()

    def get_chunk(self, rowid: int) -> Optional[dict]:
        """Return full metadata for a chunk: source, source_ref, title, content, document_id, chunk_id."""
        conn = self._connect()
        try:
            r = conn.execute(
                f"SELECT rowid, chunk_id, document_id, source, source_ref, title, content "
                f"FROM {self.DATA_TABLE} WHERE rowid = ?",
                (rowid,),
            ).fetchone()
            return dict(r) if r else None
        finally:
            conn.close()

    def get_all_docs(self) -> List[dict]:
        """Return all stored chunks (used by BM25 keyword retriever)."""
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT rowid, chunk_id, document_id, source, source_ref, title, content "
                f"FROM {self.DATA_TABLE}"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# ============================================================================
# BM25 keyword retriever — pure Python, no external deps
# ============================================================================


def _tokenize(text: str) -> List[str]:
    """Simple lowercase split — no stopword removal in Phase 4."""
    import re
    return [t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) >= 2]


class BM25Index:
    """Lightweight in-memory BM25 for keyword retrieval.

    We store a term → {doc_id → tf} inverted index, plus doc lengths and
    document frequency counts. All math is standard BM25(k1=1.5, b=0.75).
    """

    K1 = 1.5
    B = 0.75

    def __init__(self, documents: List[dict]) -> None:
        # documents: list of dicts with keys {rowid, chunk_id, content, title, ...}
        self._docs = documents
        self._doc_lens: Dict[int, int] = {}       # rowid → token count
        self._df: Dict[str, int] = {}              # term → n(docs containing term)
        self._tf: Dict[int, Dict[str, int]] = {}   # rowid → {term → count}

        for d in documents:
            rowid = int(d["rowid"])
            text = (d.get("title", "") + " " + d.get("content", "")).lower()
            tokens = _tokenize(text)
            self._doc_lens[rowid] = len(tokens)
            if not tokens:
                continue
            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self._tf[rowid] = tf
            for t in set(tf.keys()):
                self._df[t] = self._df.get(t, 0) + 1

        self._avg_doc_len = (
            sum(self._doc_lens.values()) / max(len(self._doc_lens), 1)
        )

    def search(self, query: str, *, top_k: int = 10) -> List[VecQueryHit]:
        """BM25 top-k. Scores converted to 0..1 range for compatibility."""
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        n_docs = len(self._doc_lens)
        scores: Dict[int, float] = {}
        for rowid, tf_map in self._tf.items():
            dl = self._doc_lens.get(rowid, 1)
            denom = 1.0 - self.B + self.B * dl / max(self._avg_doc_len, 1e-6)
            s = 0.0
            for t in q_tokens:
                if t not in self._df:
                    continue
                tf = tf_map.get(t, 0)
                idf = np.log((n_docs - self._df[t] + 0.5) / (self._df[t] + 0.5) + 1.0)
                s += idf * (tf * (self.K1 + 1)) / (tf + self.K1 * denom)
            if s > 0:
                scores[rowid] = s

        # Normalize to 0..1
        max_s = max(scores.values()) if scores else 1.0
        hits: List[VecQueryHit] = []
        # Build rowid → chunk_id/document_id lookup from source docs
        meta = {int(d["rowid"]): d for d in self._docs}
        for rowid, s in sorted(scores.items(), key=lambda x: -x[1])[:top_k]:
            m = meta.get(rowid, {})
            hits.append(VecQueryHit(
                chunk_id=m.get("chunk_id", "chunk_unknown"),
                document_id=m.get("document_id", "doc_unknown"),
                rowid=rowid,
                distance=1.0 - (s / max_s),
                score=s / max_s if max_s > 0 else 0.0,
            ))
        return hits


# ============================================================================
# Reciprocal Rank Fusion
# ============================================================================


def reciprocal_rank_fusion(
    ranked_lists: List[List[VecQueryHit]],
    *,
    k: int = 60,
    top_k: int = 10,
) -> List[VecQueryHit]:
    """Fuse multiple ranked lists into one using RRF.

    score(d) = Σ 1/(k + rank_i(d))  across all lists that contain d.
    The same rowid may appear in multiple lists — we merge them.
    `k=60` is the standard RRF value.
    """
    merged: Dict[int, VecQueryHit] = {}
    scores: Dict[int, float] = {}

    for rlist in ranked_lists:
        for rank, hit in enumerate(rlist, start=1):
            rid = hit.rowid
            if rid not in merged:
                merged[rid] = hit
                scores[rid] = 0.0
            scores[rid] += 1.0 / (k + rank)

    total = max(scores.values()) if scores else 1.0
    # Return hits sorted by fused score descending, normalised 0..1
    out = []
    for rid, s in sorted(scores.items(), key=lambda x: -x[1])[:top_k]:
        h = merged[rid]
        out.append(VecQueryHit(
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            rowid=h.rowid,
            distance=1.0 - (s / total),
            score=s / total if total > 0 else 0.0,
        ))
    return out


# ============================================================================
# RetrievalService — public orchestration
# ============================================================================


class RetrievalService:
    """Unified retrieval with three modes: keyword | vector | hybrid."""

    def __init__(
        self,
        *,
        db_path: Optional[str] = None,
        provider: Optional["EmbeddingProvider"] = None,
    ) -> None:
        # Import lazily to avoid circulars at module import time
        from app.adapters.embedding.base import EmbeddingProvider, get_provider
        from app.core.config import get_settings

        s = get_settings()
        self._db_path = db_path or str(s.knowledge_index_dir / "knowledge.db")
        self._provider = provider or get_provider(
            s.embedding_provider, dim_hint=768 if s.embedding_provider == "ollama" else 32
        )
        self._vec = VecIndex(self._db_path, dim=self._provider.dim)
        self._bm25: Optional[BM25Index] = None

    # -------- index rebuild hook ----------

    def refresh_bm25(self) -> None:
        """Rebuild BM25 inverted index from current VecIndex metadata."""
        docs = self._vec.get_all_docs()
        self._bm25 = BM25Index(docs)
        logger.info("BM25 rebuilt with %d docs", len(docs))

    def count(self) -> int:
        return self._vec.count()

    # -------- main search ----------

    def search(
        self,
        query: str,
        *,
        mode: Optional[str] = None,
        top_k: int = 10,
    ) -> dict:
        """Run retrieval. Returns a dict including hits + status + degraded flag.

        status ∈ {OK, DEGRADED, EMPTY} — DEGRADED means the provider is a mock.
        """
        # --- observability timing ---
        from app.core.observability import RETRIEVAL_CALLS_TOTAL, RETRIEVAL_LATENCY_MS, RETRIEVAL_HITS_PER_QUERY
        t_ret0 = time.perf_counter()

        from app.core.config import get_settings
        settings = get_settings()
        mode = mode or settings.retrieval_mode

        total_docs = self._vec.count()
        if total_docs == 0:
            # --- observability (early return still counts as a call) ---
            t_ret1 = time.perf_counter()
            RETRIEVAL_CALLS_TOTAL.inc(labels={"mode": mode, "backend": self._provider.name})
            RETRIEVAL_LATENCY_MS.observe(
                (t_ret1 - t_ret0) * 1000.0, labels={"mode": mode, "backend": self._provider.name}
            )
            RETRIEVAL_HITS_PER_QUERY.observe(0.0, labels={"mode": mode})
            return {
                "status": "EMPTY",
                "hits": [],
                "count": 0,
                "provider": self._provider.name,
                "is_mock": self._provider.is_mock,
                "mode": mode,
            }

        hits_vec: List[VecQueryHit] = []
        hits_kw: List[VecQueryHit] = []

        if mode in ("vector", "hybrid"):
            try:
                q = self._provider.embed(query)
                hits_vec = self._vec.search(q, top_k=top_k)
            except Exception as e:
                logger.warning("vector retrieval failed: %s", e)
                hits_vec = []

        if mode in ("keyword", "hybrid"):
            if self._bm25 is None:
                self.refresh_bm25()
            hits_kw = self._bm25.search(query, top_k=top_k)

        if mode == "vector":
            hits = hits_vec
        elif mode == "keyword":
            hits = hits_kw
        else:  # hybrid — RRF
            hits = reciprocal_rank_fusion([hits_vec, hits_kw], top_k=top_k)

        degraded = self._provider.is_mock
        status = "DEGRADED" if degraded else "OK"
        if not hits:
            status = "EMPTY"

        t_ret1 = time.perf_counter()
        RETRIEVAL_CALLS_TOTAL.inc(labels={"mode": mode, "backend": self._provider.name})
        RETRIEVAL_LATENCY_MS.observe(
            (t_ret1 - t_ret0) * 1000.0, labels={"mode": mode, "backend": self._provider.name}
        )
        RETRIEVAL_HITS_PER_QUERY.observe(float(len(hits)), labels={"mode": mode})

        return {
            "status": status,
            "hits": hits,
            "count": len(hits),
            "provider": self._provider.name,
            "is_mock": self._provider.is_mock,
            "mode": mode,
        }

    # -------- expose chunk text for RAG ----------

    def get_chunk_text(self, rowid: int) -> Optional[str]:
        return self._vec.get_chunk_text(rowid)

