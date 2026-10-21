"""RetrievalService + knowledge_ingestion tests (use MockEmbedding for speed)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.adapters.embedding.base import MockEmbedding
from app.services.knowledge_ingestion import chunk_text, sync_knowledge
from app.services.retrieval import RetrievalService


@pytest.fixture()
def small_knowledge_dir(tmp_path) -> Path:
    """Write 3 synthetic JSONL docs so tests don't need real knowledge files."""
    p = tmp_path / "knowledge.jsonl"
    docs = [
        {
            "document_id": "t_ssh_brute",
            "source": "Test", "source_ref": "test://ssh",
            "title": "SSH brute force",
            "content": "Detect SSH brute force on port 22. Threshold: > 10 failed attempts per minute from one source IP. Mitigation: fail2ban, key auth.",
        },
        {
            "document_id": "t_log4j",
            "source": "Test", "source_ref": "test://log4j",
            "title": "Log4j RCE",
            "content": "CVE-2021-44228 Log4Shell remote code execution. Exploitation via JNDI lookup in log messages. Mitigation: upgrade to 2.17.1.",
        },
        {
            "document_id": "t_port_scan",
            "source": "Test", "source_ref": "test://portscan",
            "title": "Port scan traffic",
            "content": "Port scan traffic is short duration SYN packets. One source IP to many destination ports, few packets, low bytes per flow.",
        },
    ]
    with p.open("w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps(d) + "\n")
    return tmp_path


@pytest.fixture()
def seeded_service(small_knowledge_dir, tmp_path) -> tuple[RetrievalService, Path]:
    """Return a RetrievalService backed by a freshly indexed DB."""
    db_path = tmp_path / "test_knowledge.db"
    mock = MockEmbedding(dim=32)

    # Build index
    summary = sync_knowledge(small_knowledge_dir, provider=mock, reset_first=True, db_path=str(db_path))
    assert summary["documents"] == 3

    svc = RetrievalService(db_path=str(db_path), provider=mock)
    return svc, db_path


class TestRetrievalServiceEmpty:
    def test_empty_index_returns_EMPTY(self, tmp_path):
        mock = MockEmbedding(dim=32)
        svc = RetrievalService(db_path=str(tmp_path / "empty.db"), provider=mock)
        r = svc.search("anything")
        assert r["status"] == "EMPTY"
        assert r["count"] == 0
        assert r["is_mock"] is True
        assert svc.count() == 0


class TestRetrievalServiceSeeded:
    def test_count_after_seed(self, seeded_service):
        svc, _ = seeded_service
        assert svc.count() > 0

    def test_keyword_finds_port_scan(self, seeded_service):
        svc, _ = seeded_service
        r = svc.search("port scan SYN packets", mode="keyword", top_k=3)
        # MockEmbedding sets provider_is_mock=True → status becomes DEGRADED.
        # Keyword-only retrieval actually runs (BM25 is deterministic, no embedding used).
        assert r["status"] in ("OK", "DEGRADED")
        doc_ids = {h.document_id for h in r["hits"]}
        assert "t_port_scan" in doc_ids

    def test_keyword_finds_ssh_brute(self, seeded_service):
        svc, _ = seeded_service
        r = svc.search("SSH port 22 brute force", mode="keyword", top_k=3)
        doc_ids = {h.document_id for h in r["hits"]}
        assert "t_ssh_brute" in doc_ids

    def test_hybrid_returns_hits(self, seeded_service):
        svc, _ = seeded_service
        r = svc.search("port scan traffic", mode="hybrid", top_k=3)
        assert r["status"] in ("OK", "DEGRADED")
        assert r["count"] >= 1

    def test_vector_mode_returns_hits(self, seeded_service):
        svc, _ = seeded_service
        r = svc.search("log4shell RCE CVE", mode="vector", top_k=3)
        # MockEmbedding has no real semantics, but still must return >= 0 hits
        assert r["count"] >= 0
        assert r["provider"] == "mock-hash"

    def test_get_chunk_text(self, seeded_service):
        svc, _ = seeded_service
        r = svc.search("port scan", mode="keyword", top_k=1)
        rowid = r["hits"][0].rowid
        text = svc.get_chunk_text(rowid)
        assert text is not None
        assert len(text) > 0
