"""FlowRecord — normalised network flow observation.

This is the single entry contract between off-line data sources
(CSV / PCAP / JSON) and the detection pipeline. Detectors MUST NOT
invent or silently drop unknown fields — feature schema mismatch is
a hard error.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import Field, field_validator

from .common import DomainModel, Protocol, _new_id, utcnow


class FlowRecord(DomainModel):
    """One bidirectional network flow observation."""

    flow_id: str = Field(default_factory=lambda: _new_id("flow"))
    timestamp: datetime = Field(default_factory=utcnow)

    # 5-tuple
    src_ip: str = Field(..., description="Source IP in the test/experimental range.")
    dst_ip: str
    src_port: int = Field(..., ge=0, le=65535)
    dst_port: int = Field(..., ge=0, le=65535)
    protocol: Protocol

    # Flow-level counters
    duration_ms: float = Field(..., ge=0.0)
    packets_src_to_dst: int = Field(..., ge=0)
    packets_dst_to_src: int = Field(..., ge=0)
    bytes_src_to_dst: int = Field(..., ge=0)
    bytes_dst_to_src: int = Field(..., ge=0)

    # Detector contract
    feature_schema_version: str = Field(
        default="v1",
        description="Version of the feature schema this record conforms to.",
    )
    features: Dict[str, float] = Field(
        default_factory=dict,
        description="Numeric feature vector keyed by feature name.",
    )

    # Provenance
    dataset_id: Optional[str] = None
    source_ref: Optional[str] = None

    @field_validator("src_ip", "dst_ip")
    @classmethod
    def _must_not_be_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("IP address must not be empty")
        return v
