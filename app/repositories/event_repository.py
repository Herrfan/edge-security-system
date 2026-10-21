"""Repository abstraction over SecurityEventORM.

Phase 3 only covers SecurityEvent — flows/policies/executions land later.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SecurityEventORM
from app.domain.common import PolicyStatus, Severity
from app.domain.event import SecurityEvent


class EventRepository:
    """Async CRUD for SecurityEvent."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ---------- Write ----------

    async def create(self, event: SecurityEvent) -> SecurityEvent:
        orm = self._to_orm(event)
        self._s.add(orm)
        await self._s.flush()
        # Reflect generated event_id back (it's already on domain model from the factory)
        return event

    async def bulk_create(self, events: List[SecurityEvent]) -> int:
        """Persist a batch. Returns count written."""
        if not events:
            return 0
        for e in events:
            self._s.add(self._to_orm(e))
        await self._s.flush()
        return len(events)

    # ---------- Read ----------

    async def get(self, event_id: str) -> Optional[SecurityEvent]:
        stmt = select(SecurityEventORM).where(SecurityEventORM.event_id == event_id)
        orm = (await self._s.execute(stmt)).scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def list(
        self,
        *,
        severity: Optional[Severity] = None,
        status: Optional[PolicyStatus] = None,
        label: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[SecurityEvent]:
        stmt = select(SecurityEventORM)
        if severity is not None:
            stmt = stmt.where(SecurityEventORM.severity == severity.value)
        if status is not None:
            stmt = stmt.where(SecurityEventORM.status == status.value)
        if label is not None:
            stmt = stmt.where(SecurityEventORM.predicted_label == label)
        stmt = stmt.order_by(SecurityEventORM.created_at.desc()).limit(limit).offset(offset)
        rows = (await self._s.execute(stmt)).scalars().all()
        return [self._to_domain(r) for r in rows]

    async def count(
        self,
        *,
        severity: Optional[Severity] = None,
        status: Optional[PolicyStatus] = None,
    ) -> int:
        from sqlalchemy import func, select as sel

        stmt = sel(func.count()).select_from(SecurityEventORM)
        if severity is not None:
            stmt = stmt.where(SecurityEventORM.severity == severity.value)
        if status is not None:
            stmt = stmt.where(SecurityEventORM.status == status.value)
        return (await self._s.execute(stmt)).scalar_one() or 0

    # ---------- Mappers ----------

    @staticmethod
    def _to_orm(e: SecurityEvent) -> SecurityEventORM:
        return SecurityEventORM(
            event_id=e.event_id,
            created_at=e.created_at.isoformat(),
            asset_id=e.asset_id,
            flow_id=e.flow_id,
            flow_summary=e.flow_summary,
            predicted_label=e.predicted_label,
            score=e.score,
            severity=e.severity.value,
            model_id=e.model_id,
            model_version=e.model_version,
            evidence_summary=e.evidence_summary,
            status=e.status.value,
            trace_id=e.trace_id,
        )

    @staticmethod
    def _to_domain(r: SecurityEventORM) -> SecurityEvent:
        return SecurityEvent(
            event_id=r.event_id,
            created_at=datetime.fromisoformat(r.created_at),
            asset_id=r.asset_id,
            flow_id=r.flow_id,
            flow_summary=r.flow_summary,
            predicted_label=r.predicted_label,
            score=r.score,
            severity=Severity(r.severity),
            model_id=r.model_id,
            model_version=r.model_version,
            evidence_summary=r.evidence_summary,
            status=PolicyStatus(r.status),
            trace_id=r.trace_id,
        )
