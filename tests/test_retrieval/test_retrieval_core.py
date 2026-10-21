"""Tests for VecIndex + BM25 + RRF — use MockEmbedding for speed + stability."""
from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

import numpy as np
import pytest

from app.adapters.embedding.base import MockEmbedding
from app.services.knowledge_ingestion import chunk_text
from app.services.retrieval import (
    BM25Index,
    VecIndex,
    reciprocal_rank_fusion,
)


# ---------- chunk_text ----------

class TestChunking:
    def test_short_text_one_chunk(self):
        text = "This is a single paragraph of text with moderate length."
        chunks = chunk_text(text)
        assert len(chunks) >= 1
        # Every returned chunk must have content
        for c in chunks:
            assert c.strip()

    def test_long_text_multiple_chunks(self):
        text = "A. " * 300
        chunks = chunk_text(text, max_chars=500)
        assert len(chunks) >= 2

    def test_empty_text(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []


# ---------- VecIndex (in-memory sqlite) ----------


@pytest.fixture()
def vec_db(tmp_path) -> str:
    return str(tmp_path / "test_vec.db")


@pytest.fixture()
def mock_provider() -> MockEmbedding:
    return MockEmbedding(dim=32)


class TestVecIndex:
    def test_insert_and_count(self, vec_db, mock_provider):
        idx = VecIndex(vec_db, dim=32)
        assert idx.count() == 0
        vec = mock_provider.embed("test text about port scan")
        idx.upsert(
            chunk_id="c1",
            document_id="doc_1",
            source="CVE", source_ref="ref", title="t", content="port scan details",
            vector=vec,
        )
        assert idx.count() == 1

    def test_reset_clears_all(self, vec_db, mock_provider):
        idx = VecIndex(vec_db, dim=32)
        vec = mock_provider.embed("hello")
        for i in range(5):
            idx.upsert(
                chunk_id=f"c{i}", document_id="d",
                source="CVE", source_ref="r", title="t", content=f"text {i}",
                vector=vec,
            )
        assert idx.count() == 5
        idx.reset()
        assert idx.count() == 0

    def test_upsert_replaces(self, vec_db, mock_provider):
        idx = VecIndex(vec_db, dim=32)
        v1 = mock_provider.embed("first")
        v2 = mock_provider.embed("second")
        idx.upsert(
            chunk_id="dup", document_id="d",
            source="CVE", source_ref="r", title="t", content="first content", vector=v1,
        )
        idx.upsert(
            chunk_id="dup", document_id="d",
            source="CVE", source_ref="r", title="t", content="second content", vector=v2,
        )
        # metadata row replaced but rowid stable? actually ON CONFLICT replaces content, not rowid
        assert idx.count() == 1  # still one chunk

    def test_dim_mismatch_rejected(self, vec_db, mock_provider):
        idx = VecIndex(vec_db, dim=32)
        # Try to insert a 768-dim vector
        bad = np.zeros(768, dtype=np.float32)
        with pytest.raises(ValueError, match="dim mismatch"):
            idx.upsert(
                chunk_id="c", document_id="d",
                source="CVE", source_ref="r", title="t", content="c", vector=bad,
            )


# ---------- BM25Index ----------


class TestBM25Index:
    @pytest.fixture()
    def docs(self):
        return [
            {"rowid": 1, "chunk_id": "c1", "document_id": "d1",
             "title": "SSH brute force detection", "content": "Detect brute force on SSH port 22"},
            {"rowid": 2, "chunk_id": "c2", "document_id": "d2",
             "title": "Log4j RCE CVE-2021-44228", "content": "Log4Shell remote code execution JNDI"},
            {"rowid": 3, "chunk_id": "c3", "document_id": "d3",
             "title": "Port scan SYN traffic", "content": "SYN scan short duration low bytes"},
        ]

    def test_search_brute_force(self, docs):
        b = BM25Index(docs)
        hits = b.search("brute force SSH port 22", top_k=2)
        assert len(hits) == 2
        # rowid 1 (SSH brute force) must rank #1
        assert hits[0].rowid == 1
        assert hits[0].score > 0

    def test_search_log4j(self, docs):
        b = BM25Index(docs)
        hits = b.search("Log4j CVE RCE JNDI", top_k=2)
        assert any(h.document_id == "d2" for h in hits)

    def test_search_empty_query(self, docs):
        b = BM25Index(docs)
        assert b.search("", top_k=3) == []
        assert b.search("   ", top_k=3) == []

    def test_search_no_matches(self, docs):
        b = BM25Index(docs)
        hits = b.search("xyzzy nonexistent termzzz", top_k=3)
        # Should be empty
        assert hits == []


# ---------- RRF ----------


class TestRRF:
    def test_basic_fusion(self):
        from app.services.retrieval import VecQueryHit
        kw = [
            VecQueryHit("c1", "d1", 1, 0.1, 0.9),
            VecQueryHit("c2", "d2", 2, 0.2, 0.8),
            VecQueryHit("c3", "d3", 3, 0.3, 0.7),
        ]
        vec = [
            VecQueryHit("c2", "d2", 2, 0.15, 0.85),  # overlap with kw
            VecQueryHit("c4", "d4", 4, 0.25, 0.75),
            VecQueryHit("c1", "d1", 1, 0.4, 0.6),
        ]
        fused = reciprocal_rank_fusion([kw, vec], top_k=4)
        assert fused  # non-empty
        # rowid 2 (d2) appears in BOTH lists → should rank highest
        assert fused[0].rowid == 2

    def test_empty_lists(self):
        assert reciprocal_rank_fusion([]) == []

    def test_single_list(self):
        from app.services.retrieval import VecQueryHit
        hits = [VecQueryHit(f"c{i}", f"d{i}", i, 0.1, 1.0 - 0.1 * i) for i in range(5)]
        fused = reciprocal_rank_fusion([hits], top_k=3)
        assert len(fused) == 3
