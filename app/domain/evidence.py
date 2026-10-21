"""Evidence — a single retrievable chunk of security knowledge.

An Evidence instance is ONLY valid if it was produced by importing a
real document and can be traced back to that source. RAG policies
reference evidence_ids; any id that does not exist in the knowledge
base MUST be rejected at validation time.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, field_validator

from .common import DomainModel, _new_id, utcnow


class Evidence(DomainModel):
    """A single retrievable chunk sourced from a real knowledge document."""

    evidence_id: str = Field(default_factory=lambda: _new_id("evd"))
    document_id: str
    chunk_id: str

    # Document provenance (non-negotiable for auditors)
    source: str = Field(..., description="Origin e.g. 'CVE', 'ATT&CK', 'vendor-advisory'.")
    source_ref: str = Field(..., description="External reference or URL.")
    title: str = Field(..., min_length=1)

    published_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=utcnow)
    version: str = "1"

    content: str = Field(..., min_length=1, max_length=20000)

    @field_validator("content", "title")
    @classmethod
    def _non_empty_after_strip(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must contain non-whitespace content")
        return v

    # Retrieval metadata (populated at query time)
    retrieval_method: Optional[str] = Field(default=None, description="keyword | vector | hybrid")
    retrieval_score: Optional[float] = None

    # Integrity
    checksum: Optional[str] = None
