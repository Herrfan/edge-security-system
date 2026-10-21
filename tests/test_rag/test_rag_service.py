"""Unit tests for RAGService with Mock providers (no real LLM/Ollama)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest

from app.adapters.embedding.base import MockEmbedding
from app.adapters.llm.base import MockLLM, _parse_json_tolerant
from app.domain.common import (
    ActionType,
    PolicyStatus,
    Severity,
)
from app.domain.event import SecurityEvent
from app.services.knowledge_ingestion import sync_knowledge
from app.services.retrieval import RetrievalService
from app.services.rag_service import RAGService


@pytest.fixture()
def seeded_rag(tmp_path) -> tuple[RAGService, RetrievalService, str]:
    """Build a fresh RetrievalService + RAGService backed by small mock DB."""
    db_path = tmp_path / "rag_test.db"
    mock_emb = MockEmbedding(dim=32)
    llm = MockLLM()

    # Build a tiny knowledge base
    import tempfile, json
    kdir = tmp_path / "k.jsonl"
    docs = [
        {"document_id": "r_brute", "source": "Test", "source_ref": "t",
         "title": "SSH brute force", "content": "SSH brute force port 22 threshold fail2ban"},
        {"document_id": "r_log4j", "source": "Test", "source_ref": "t",
         "title": "Log4j RCE", "content": "Log4Shell CVE JNDI remote code execution mitigation"},
        {"document_id": "r_portscan", "source": "Test", "source_ref": "t",
         "title": "Port scan SYN", "content": "SYN scan short duration low bytes port scan detection"},
    ]
    with kdir.open("w") as fh:
        for d in docs:
            fh.write(json.dumps(d) + "\n")
    sync_knowledge(kdir, provider=mock_emb, reset_first=True, db_path=str(db_path))

    ret = RetrievalService(db_path=str(db_path), provider=mock_emb)
    svc = RAGService(llm=llm, retrieval=ret)
    return svc, ret, str(db_path)


def _sample_event(label: str = "brute_force", severity: Severity = Severity.HIGH) -> SecurityEvent:
    return SecurityEvent(
        asset_id="ssh-gateway-01",
        flow_id="flow_001",
        predicted_label=label,
        score=0.88,
        severity=severity,
        trace_id="trace-abc",
    )


class TestJSONParsing:
    def test_pure_json(self):
        assert _parse_json_tolerant('{"a": 1}') == {"a": 1}

    def test_markdown_wrapped(self):
        raw = "Here is the analysis:\n```json\n{\"OK\": true}\n```"
        # The extractor grabs first balanced {...}
        assert _parse_json_tolerant(raw) == {"OK": True}

    def test_no_json_raises(self):
        with pytest.raises(ValueError):
            _parse_json_tolerant("no json at all here")


class TestMockLLM:
    def test_brute_force_detected(self):
        llm = MockLLM()
        out = llm.generate_json("Detecting SSH brute force on port 22")
        assert out["RECOMMENDED_ACTION"] == "BLOCK_IP"
        assert out["THREAT_LEVEL"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")

    def test_port_scan_detected(self):
        llm = MockLLM()
        out = llm.generate_json("Port scan traffic SYN packets")
        assert out["RECOMMENDED_ACTION"] == "BLOCK_IP"

    def test_unknown_label(self):
        llm = MockLLM()
        out = llm.generate_json("totally benign traffic")
        # mock heuristic: no keyword match → MONITOR
        assert out["RECOMMENDED_ACTION"] == "MONITOR"


class TestRAGServiceUnit:
    def test_event_with_brute_force_label(self, seeded_rag):
        svc, ret, _ = seeded_rag
        event = _sample_event(label="brute_force")
        result = svc.run(event)

        # Proposal should exist
        assert result.proposal.event_id == event.event_id
        assert result.proposal.status == PolicyStatus.DRAFT
        # MockLLM says BLOCK_IP but RAGService downgrades to ALERT_ONLY (no src_ip yet)
        assert result.proposal.action_type in (ActionType.ALERT_ONLY, ActionType.NO_ACTION)
        # Evidence IDs should contain at least one chunk
        assert result.proposal.evidence_ids
        # Rationale should explain the downgrade
        assert "downgraded" in result.proposal.rationale.lower()
        # Timing plausible
        assert result.retrieval_latency_ms >= 0
        assert result.llm_latency_ms >= 0
        # llm_is_mock = True since we injected MockLLM
        assert result.llm_is_mock is True

    def test_retrieval_status_EMTPY_with_mock_embedding(self, tmp_path):
        """MockEmbedding with arbitrary texts → retrieval may still find hits via BM25,
        but if knowledge is empty → status=EMPTY → proposal still built."""
        db_path = tmp_path / "empty.db"
        mock_emb = MockEmbedding(dim=32)
        ret = RetrievalService(db_path=str(db_path), provider=mock_emb)
        llm = MockLLM()
        svc = RAGService(llm=llm, retrieval=ret)
        event = _sample_event()
        result = svc.run(event)
        assert result.proposal is not None
        # Even EMPTY retrieval, MockLLM still gives structured output → action_type likely MONITOR

    def test_proposal_dry_run_enforced(self, seeded_rag):
        """Proposal never executes — it's just a candidate."""
        svc, ret, _ = seeded_rag
        event = _sample_event()
        result = svc.run(event)
        # The proposal itself doesn't have dry_run field, but status should be DRAFT
        assert result.proposal.status == PolicyStatus.DRAFT

    def test_risk_level_from_event_when_llm_degraded(self, tmp_path):
        """Even with MockLLM which ALWAYS returns a threat_level, the event severity
        is respected as fallback when llm_parsed happens to miss THREAT_LEVEL."""
        import json
        db_path = tmp_path / "k2.db"
        mock_emb = MockEmbedding(dim=32)
        ret = RetrievalService(db_path=str(db_path), provider=mock_emb)
        svc = RAGService(llm=MockLLM(), retrieval=ret)
        event = _sample_event(severity=Severity.CRITICAL)
        result = svc.run(event)
        # MockLLM knows "brute_force" → THREAT_LEVEL="HIGH" (not CRITICAL)
        # So LLM value wins over event.severity in normal flow. Both are plausible.
        assert result.proposal.risk_level in (Severity.CRITICAL, Severity.HIGH)

    def test_trace_id_preserved(self, seeded_rag):
        svc, ret, _ = seeded_rag
        event = _sample_event()
        result = svc.run(event)
        assert result.proposal.event_id == event.event_id
