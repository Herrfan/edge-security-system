"""Tests for SecurityEvent."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.common import PolicyStatus, Severity
from app.domain.event import SecurityEvent


def _minimal_event() -> dict:
    return {
        "asset_id": "web-server-01",
        "predicted_label": "port_scan",
        "score": 0.87,
        "severity": Severity.HIGH,
    }


class TestSecurityEventPositive:
    def test_minimal(self):
        e = SecurityEvent(**_minimal_event())
        assert e.event_id.startswith("evt_")
        assert e.status == PolicyStatus.DRAFT

    def test_full(self):
        data = _minimal_event()
        data.update({
            "flow_id": "flow_abc123",
            "flow_summary": "50 unique ports from 192.168.1.99",
            "model_id": "rule-demo",
            "model_version": "v1",
            "evidence_summary": "Multiple SYN packets to distinct ports",
            "trace_id": "trace-xyz",
            "status": PolicyStatus.NEEDS_VALIDATION,
        })
        e = SecurityEvent(**data)
        assert e.flow_id == "flow_abc123"
        assert e.status == PolicyStatus.NEEDS_VALIDATION


class TestSecurityEventNegative:
    def test_missing_required(self):
        bad = _minimal_event()
        del bad["predicted_label"]
        with pytest.raises(ValidationError):
            SecurityEvent(**bad)

    def test_score_out_of_range(self):
        bad = _minimal_event()
        bad["score"] = 1.5
        with pytest.raises(ValidationError):
            SecurityEvent(**bad)

    def test_negative_score(self):
        bad = _minimal_event()
        bad["score"] = -0.1
        with pytest.raises(ValidationError):
            SecurityEvent(**bad)

    def test_invalid_severity_enum(self):
        bad = _minimal_event()
        bad["severity"] = "EXTREME"
        with pytest.raises(ValidationError):
            SecurityEvent(**bad)

    def test_rejects_extra_fields(self):
        bad = _minimal_event()
        bad["hack"] = "inject"
        with pytest.raises(ValidationError):
            SecurityEvent(**bad)
