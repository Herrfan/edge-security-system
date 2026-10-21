"""Database plumbing — SQLAlchemy 2.0 async engine + session factories.

Phase 3 only wires the SecurityEvent table. Later phases add FlowRecord,
PolicyProposal, ExecutionRecord etc. via Alembic or declarative re-init.
"""
from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings


# ---- ORM base ------------------------------------------------------------

class Base(DeclarativeBase):
    """All ORM models inherit this so metadata.gather works at init."""
    pass


# ---- Concrete ORM models (Phase 3-6) --------------------------------------


class SecurityEventORM(Base):
    """SQLite-persisted event row. One-to-one with domain.SecurityEvent."""

    __tablename__ = "security_events"

    event_id: Mapped[str] = mapped_column(primary_key=True, index=True)
    created_at: Mapped[str]
    asset_id: Mapped[str]
    flow_id: Mapped[str | None]
    flow_summary: Mapped[str | None]
    predicted_label: Mapped[str]
    score: Mapped[float]
    severity: Mapped[str]
    model_id: Mapped[str | None]
    model_version: Mapped[str | None]
    evidence_summary: Mapped[str | None]
    status: Mapped[str]
    trace_id: Mapped[str | None]


class FlowRecordORM(Base):
    """Phase 6 — persisted flow record so Executor can resolve src_ip / dst_port."""

    __tablename__ = "flows"

    flow_id: Mapped[str] = mapped_column(primary_key=True, index=True)
    created_at: Mapped[str]
    src_ip: Mapped[str]
    dst_ip: Mapped[str]
    src_port: Mapped[int]
    dst_port: Mapped[int]
    protocol: Mapped[str]
    duration_ms: Mapped[float]
    packets_src_to_dst: Mapped[int]
    packets_dst_to_src: Mapped[int]
    bytes_src_to_dst: Mapped[int]
    bytes_dst_to_src: Mapped[int]
    feature_schema_version: Mapped[str]
    features_json: Mapped[str]          # JSON blob — SQLite has no native JSON; store as text
    dataset_id: Mapped[str | None]
    source_ref: Mapped[str | None]


class PolicyProposalORM(Base):
    """Phase 6 — persisted RAG candidate."""

    __tablename__ = "policy_proposals"

    policy_id: Mapped[str] = mapped_column(primary_key=True, index=True)
    created_at: Mapped[str]
    event_id: Mapped[str]
    action_type: Mapped[str]
    parameters_json: Mapped[str]        # Pydantic BaseModel → json.dumps
    risk_level: Mapped[str]
    rationale: Mapped[str]
    evidence_ids_json: Mapped[str]
    ttl_seconds: Mapped[int]
    status: Mapped[str]
    requires_approval: Mapped[bool]
    expires_at: Mapped[str | None]


class ExecutionRecordORM(Base):
    """Phase 6 — dry-run / real execution outcome."""

    __tablename__ = "executions"

    execution_id: Mapped[str] = mapped_column(primary_key=True, index=True)
    created_at: Mapped[str]
    policy_id: Mapped[str]
    event_id: Mapped[str | None]
    mode: Mapped[str]                    # DRY_RUN | REAL
    status: Mapped[str]                 # SUCCEEDED | FAILED | ROLLED_BACK
    target: Mapped[str]                  # e.g. "block_ip:192.168.100.5"
    planned_command: Mapped[str | None]
    stdout: Mapped[str | None]
    stderr: Mapped[str | None]
    duration_ms: Mapped[float]
    error_message: Mapped[str | None]


class TokenBlacklistORM(Base):
    """Phase 12 — revoked JWT refresh tokens (or any token by jti).

    We store the jti (token id claim) + exp so we can purge expired rows.
    Signature verification still happens in decode_token(); this is an
    ADDITIONAL check after HS256 passes, so revoked tokens are rejected even
    before we inspect role / exp.
    """

    __tablename__ = "token_blacklist"

    jti_hash: Mapped[str] = mapped_column(primary_key=True, index=True)  # sha256(jti) — never store raw
    jti: Mapped[str] = mapped_column(index=True)
    subject: Mapped[str]
    exp_at: Mapped[str | None]         # ISO-8601 expiry — may be None if revocation not tied to exp
    revoked_at: Mapped[str]           # ISO-8601 now
    reason: Mapped[str | None]
    revoked_by: Mapped[str | None]


# ---- Engine / session factories ------------------------------------------

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_sqlite_path(database_url: str) -> None:
    """sqlite:///./data/app.db → ensure parent dir exists."""
    if not database_url.startswith("sqlite"):
        return
    # sqlite:///abs/path or sqlite:///rel/path
    rest = database_url.split("sqlite", 1)[1].lstrip(":")
    rest = rest.lstrip("/")  # triple-slash abs → rest is abs path; relative → rest is rel path
    if rest.startswith("memory"):
        return
    p = Path(rest)
    if not p.is_absolute():
        from app.core.config import REPO_ROOT
        p = REPO_ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is not None:
        return _engine
    settings = get_settings()
    _ensure_sqlite_path(settings.database_url)
    # sqlite+aiosqlite:///...  — SQLAlchemy 2.0 with async driver
    url = settings.database_url
    if url.startswith("sqlite:///") and "+aiosqlite" not in url:
        url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    _engine = create_async_engine(url, echo=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is not None:
        return _session_factory
    _session_factory = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _session_factory


async def init_db() -> None:
    """Create tables if missing. Safe to call repeatedly."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a scoped async session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
