"""Tests for FlowRecord — positive and negative validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.common import Protocol
from app.domain.flow import FlowRecord


def _minimal_flow() -> dict:
    return {
        "src_ip": "192.168.1.10",
        "dst_ip": "10.0.0.5",
        "src_port": 54321,
        "dst_port": 443,
        "protocol": Protocol.TCP,
        "duration_ms": 123.45,
        "packets_src_to_dst": 10,
        "packets_dst_to_src": 8,
        "bytes_src_to_dst": 5000,
        "bytes_dst_to_src": 2000,
    }


class TestFlowRecordPositive:
    def test_minimal(self):
        fr = FlowRecord(**_minimal_flow())
        assert fr.src_port == 54321
        assert fr.flow_id.startswith("flow_")
        assert fr.feature_schema_version == "v1"
        assert fr.features == {}

    def test_with_features_and_metadata(self):
        data = _minimal_flow()
        data.update({
            "features": {"pkt_count": 18.0, "byte_rate": 50.0},
            "dataset_id": "cicids2017-v1",
            "source_ref": "flow_001.csv",
            "feature_schema_version": "v2",
        })
        fr = FlowRecord(**data)
        assert fr.features["pkt_count"] == 18.0
        assert fr.dataset_id == "cicids2017-v1"
        assert fr.feature_schema_version == "v2"


class TestFlowRecordNegative:
    def test_missing_required_field(self):
        bad = _minimal_flow()
        del bad["src_ip"]
        with pytest.raises(ValidationError):
            FlowRecord(**bad)

    def test_port_out_of_range_low(self):
        bad = _minimal_flow()
        bad["dst_port"] = -1
        with pytest.raises(ValidationError):
            FlowRecord(**bad)

    def test_port_out_of_range_high(self):
        bad = _minimal_flow()
        bad["dst_port"] = 70000
        with pytest.raises(ValidationError):
            FlowRecord(**bad)

    def test_negative_duration(self):
        bad = _minimal_flow()
        bad["duration_ms"] = -10.0
        with pytest.raises(ValidationError):
            FlowRecord(**bad)

    def test_negative_packet_count(self):
        bad = _minimal_flow()
        bad["packets_src_to_dst"] = -1
        with pytest.raises(ValidationError):
            FlowRecord(**bad)

    def test_empty_ip(self):
        bad = _minimal_flow()
        bad["src_ip"] = "   "
        with pytest.raises(ValidationError):
            FlowRecord(**bad)

    def test_unknown_enum_protocol(self):
        bad = _minimal_flow()
        bad["protocol"] = "TCPX"  # Not in enum
        with pytest.raises(ValidationError):
            FlowRecord(**bad)

    def test_rejects_extra_fields(self):
        bad = _minimal_flow()
        bad["unknown_field"] = "should_be_rejected"
        with pytest.raises(ValidationError):
            FlowRecord(**bad)
