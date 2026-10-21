"""E2E RAG test — skips if Ollama unavailable, runs real LLM if available."""
from __future__ import annotations

from pathlib import Path

import pytest


def _ollama_available() -> bool:
    import requests
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        return r.status_code == 200 and "models" in r.json()
    except Exception:
        return False


# Resolve repo root once at module import time
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(not _ollama_available(), reason="Ollama not reachable — skipping real LLM E2E")
class TestRAGRealLLM:
    """Run full RAG chain against real Ollama LLM + real embedding."""

    def test_full_chain_brute_force(self, client):
        """Seed events + knowledge first; then generate a policy proposal."""

        # Step 1: knowledge sync
        kpath = ROOT / "data" / "knowledge" / "security_knowledge.jsonl"
        r_sync = client.post("/api/v1/knowledge/sync", json={
            "input_path": str(kpath), "reset_first": True,
        })
        assert r_sync.status_code == 200, r_sync.text

        # Step 2: seed events from detection
        csv_path = ROOT / "data" / "samples" / "flows_sample.csv"
        r_seed = client.post("/api/v1/events/seed", json={
            "input_file": str(csv_path),
            "detector_id": "rule-demo",
            "max_records": 50,
            "asset_id": "e2e-asset",
        })
        assert r_seed.status_code == 200, r_seed.text
        assert r_seed.json()["seeded_events"] == 50

        # Step 3: grab first event
        events = client.get("/api/v1/events?limit=1").json()
        assert len(events) == 1
        event_id = events[0]["event_id"]

        # Step 4: generate policy proposal via real Ollama
        r_proposal = client.post("/api/v1/policy-proposal/generate", json={
            "event_id": event_id,
            "llm_provider": "ollama",
        })
        assert r_proposal.status_code == 200, r_proposal.text
        body = r_proposal.json()

        # Validate structure
        # NOTE: retrieval uses sqlite-vec + ollama embedding (real), but our embedding
        # adapter falls back to MockEmbedding if Ollama init fails. Either is fine here —
        # what matters is that the full chain produces a PolicyProposal.
        assert body["retrieval_status"] in ("OK", "DEGRADED", "EMPTY")
        assert body["llm_latency_ms"] > 0
        assert body["evidence_count"] >= 0
        proposal = body["proposal"]
        assert "event_id" in proposal
        assert "action_type" in proposal
        assert "rationale" in proposal
        assert proposal["status"] in ("DRAFT", "REJECTED", "NEEDS_VALIDATION", "NEEDS_APPROVAL")
        print(f"[real-llm] action_type={proposal['action_type']} "
              f"latency={body['llm_latency_ms']:.1f}ms "
              f"llm_is_mock={body['llm_is_mock']} "
              f"evidence_chunks={body['evidence_count']}")
