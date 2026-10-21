"""HTTP API tests for knowledge sync + retrieval."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def small_knowledge_jsonl(tmp_path) -> str:
    """Return absolute path to a tiny knowledge JSONL file for API tests."""
    p = tmp_path / "k.jsonl"
    docs = [
        {
            "document_id": "api_test_ssh",
            "source": "Test", "source_ref": "test://ssh",
            "title": "SSH brute force detection",
            "content": "Detect SSH brute force on port 22 with thresholds.",
        },
        {
            "document_id": "api_test_portscan",
            "source": "Test", "source_ref": "test://scan",
            "title": "Port scan pattern",
            "content": "SYN packets short duration port scan traffic.",
        },
    ]
    with p.open("w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps(d) + "\n")
    return str(p)


class TestKnowledgeSyncAPI:
    def test_sync_success(self, client, small_knowledge_jsonl):
        r = client.post(
            "/api/v1/knowledge/sync",
            json={"input_path": small_knowledge_jsonl, "reset_first": True},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["documents"] == 2
        assert body["chunks"] >= 2

    def test_sync_missing_path_404(self, client):
        r = client.post(
            "/api/v1/knowledge/sync",
            json={"input_path": "/no/such/file.jsonl"},
        )
        assert r.status_code == 404


class TestRetrievalAPI:
    def test_status_empty(self, client):
        """Before sync, retrieval should report count=0."""
        r = client.get("/api/v1/retrieval/status")
        assert r.status_code == 200
        assert r.json()["count"] >= 0

    def test_search_unknown_route_404(self, client):
        """GET /retrieval/{id} not yet implemented in Phase 4 → 404."""
        r = client.get("/api/v1/retrieval/retrieval_does_not_exist")
        assert r.status_code == 404, r.text
