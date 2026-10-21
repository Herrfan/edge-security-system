"""SecurityEvent — detector output converted into a queryable event."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from .common import DomainModel, PolicyStatus, Severity, _new_id, utcnow


class SecurityEvent(DomainModel):
    """A single alert produced by the detection pipeline."""

    event_id: str = Field(default_factory=lambda: _new_id("evt"))
    created_at: datetime = Field(default_factory=utcnow)
    asset_id: str = Field(..., description="The asset under protection.")

    # Link back to the flow that triggered this event
    flow_id: Optional[str] = None
    flow_summary: Optional[str] = None

    # Detector output
    predicted_label: str = Field(..., description="Detected class label.")
    score: float = Field(..., ge=0.0, le=1.0)
    severity: Severity

    # Detector provenance
    model_id: Optional[str] = None
    model_version: Optional[str] = None

    # Event lifecycle
    evidence_summary: Optional[str] = None
    status: PolicyStatus = PolicyStatus.DRAFT
    trace_id: Optional[str] = None
