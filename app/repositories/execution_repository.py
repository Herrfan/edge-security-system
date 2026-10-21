"""ExecutionRecord repository."""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import ExecutionRecordORM
from app.domain.common import ExecutionMode, ExecutionStatus, _new_id, utcnow
from app.domain.execution import ExecutionRecord


class ExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, rec: ExecutionRecord) -> ExecutionRecord:
        self._s.add(ExecutionRecordORM(
            execution_id=rec.execution_id,
            created_at=rec.started_at.isoformat(),
            policy_id=rec.policy_id,
            event_id=None,  # filled at higher level if known
            mode=rec.mode.value,
            status=rec.status.value,
            target=rec.trace_id or "",  # not a perfect fit — store as trace stub for Phase 6
            planned_command=None,        # command lives in Executor; not persisted yet
            stdout=rec.stdout_summary,
            stderr=rec.stderr_summary,
            duration_ms=0.0,             # compute as (finished - started).total_seconds()*1000
            error_message=None,          # captured via stderr_summary; not a dedicated field
        ))
        await self._s.flush()
        return rec

    async def get(self, execution_id: str) -> Optional[ExecutionRecord]:
        r = (await self._s.execute(
            select(ExecutionRecordORM).where(ExecutionRecordORM.execution_id == execution_id)
        )).scalar_one_or_none()
        return self._to_domain(r) if r else None

    @staticmethod
    def _to_domain(r: ExecutionRecordORM) -> ExecutionRecord:
        return ExecutionRecord(
            execution_id=r.execution_id,
            mode=ExecutionMode(r.mode),
            status=ExecutionStatus(r.status),
            trace_id=r.target,  # imperfect mapping
        )
