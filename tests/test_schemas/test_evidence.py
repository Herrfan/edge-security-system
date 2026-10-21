"""Tests for Evidence."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.evidence import Evidence


def _minimal_evidence() -> dict:
    return {
        "document_id": "doc_CVE_2024_1234",
        "chunk_id": "chunk_001",
        "source": "CVE",
        "source_ref": "https://nvd.nist.gov/vuln/detail/CVE-2024-1234",
        "title": "CVE-2024-1234: Example Vulnerability",
        "content": "This vulnerability allows remote attackers...",
    }


class TestEvidencePositive:
    def test_minimal(self):
        ev = Evidence(**_minimal_evidence())
        assert ev.evidence_id.startswith("evd_")
        assert ev.retrieval_method is None
        assert ev.checksum is None

    def test_with_retrieval_metadata(self):
        data = _minimal_evidence()
        data.update({
            "retrieval_method": "hybrid",
            "retrieval_score": 0.93,
            "checksum": "sha256:abc123",
        })
        ev = Evidence(**data)
        assert ev.retrieval_method == "hybrid"
        assert ev.retrieval_score == 0.93


class TestEvidenceNegative:
    def test_missing_required(self):
        bad = _minimal_evidence()
        del bad["source_ref"]
        with pytest.raises(ValidationError):
            Evidence(**bad)

    def test_empty_title(self):
        bad = _minimal_evidence()
        bad["title"] = ""
        with pytest.raises(ValidationError):
            Evidence(**bad)

    def test_empty_content(self):
        bad = _minimal_evidence()
        bad["content"] = "   "
        with pytest.raises(ValidationError):
            Evidence(**bad)

    def test_rejects_extra_fields(self):
        bad = _minimal_evidence()
        bad["fake_future_field"] = "hack"
        with pytest.raises(ValidationError):
            Evidence(**bad)
