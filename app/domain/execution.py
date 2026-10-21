"""ExecutionRecord — the outcome of attempting to apply a PolicyProposal.

Dry-run and real execution share this contract. The Executor MUST record
before/after snapshots and rollback status so auditors can see what
would have changed.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from .common import DomainModel, ExecutionMode, ExecutionStatus, _new_id, utcnow


class ExecutionRecord(DomainModel):
    """Attempt to apply a PolicyProposal."""

    execution_id: str = Field(default_factory=lambda: _new_id("exe"))
    policy_id: str  # Must reference a real PolicyProposal
    mode: ExecutionMode = ExecutionMode.DRY_RUN

    started_at: datetime = Field(default_factory=utcnow)
    finished_at: Optional[datetime] = None

    status: ExecutionStatus = ExecutionStatus.UNKNOWN

    # Snapshot refs (files or hashes, not raw payloads)
    before_state_ref: Optional[str] = None
    after_state_ref: Optional[str] = None

    # Log outputs — MASKED and length-limited
    stdout_summary: Optional[str] = Field(default=None, max_length=2000)
    stderr_summary: Optional[str] = Field(default=None, max_length=2000)

    rollback_status: Optional[str] = None  # SUCCEEDED | FAILED | N/A

    trace_id: Optional[str] = None
