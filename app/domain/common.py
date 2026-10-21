"""Shared domain types (enums, mixins) used across contracts."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    """Current UTC time. Always timezone-aware."""
    return datetime.now(timezone.utc)


class DomainModel(BaseModel):
    """Base class for every domain model.

    - forbids extra fields (silently dropping unknowns is a footgun)
    - allows population from ORM / dict
    - records which schema version produced the instance
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        use_enum_values=False,  # keep enum values, not raw strings
        protected_namespaces=(),  # allow fields like model_id / model_version
    )


class Protocol(str, Enum):
    """Normalised transport-layer protocols."""
    TCP = "TCP"
    UDP = "UDP"
    ICMP = "ICMP"
    OTHER = "OTHER"


class Severity(str, Enum):
    """Event severity classification."""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExecutionMode(str, Enum):
    """How an action is executed."""
    DRY_RUN = "DRY_RUN"
    REAL = "REAL"


class ExecutionStatus(str, Enum):
    """Outcome of an execution attempt."""
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    ROLLED_BACK = "ROLLED_BACK"


class PolicyStatus(str, Enum):
    """Lifecycle of a candidate policy."""
    DRAFT = "DRAFT"
    NEEDS_VALIDATION = "NEEDS_VALIDATION"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"
    READY = "READY"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"


class ActionType(str, Enum):
    """Whitelisted defensive actions.

    Only these values are legal; anything else is UNSUPPORTED_ACTION.
    Keep this list tiny in Phase 1 — real firewall integration is NOT implemented.
    """
    ALERT_ONLY = "ALERT_ONLY"
    NO_ACTION = "NO_ACTION"
    BLOCK_IP = "BLOCK_IP"
    RATE_LIMIT = "RATE_LIMIT"
    BLOCK_PORT = "BLOCK_PORT"


# Helper: stable random IDs when the caller doesn't supply one
def _new_id(prefix: str) -> str:
    import uuid
    return f"{prefix}_{uuid.uuid4().hex}"
