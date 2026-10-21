"""FlowRecord repository."""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import FlowRecordORM
from app.domain.common import _new_id, utcnow
from app.domain.flow import FlowRecord


class FlowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def bulk_create(self, flows: List[FlowRecord]) -> int:
        if not flows:
            return 0
        rows = []
        for f in flows:
            rows.append(FlowRecordORM(
                flow_id=f.flow_id,
                created_at=f.created_at.isoformat(),
                src_ip=f.src_ip,
                dst_ip=f.dst_ip,
                src_port=f.src_port,
                dst_port=f.dst_port,
                protocol=f.protocol.value,
                duration_ms=f.duration_ms,
                packets_src_to_dst=f.packets_src_to_dst,
                packets_dst_to_src=f.packets_dst_to_src,
                bytes_src_to_dst=f.bytes_src_to_dst,
                bytes_dst_to_src=f.bytes_dst_to_src,
                feature_schema_version=f.feature_schema_version,
                features_json=json.dumps(f.features or {}),
                dataset_id=f.dataset_id,
                source_ref=f.source_ref,
            ))
        self._s.add_all(rows)
        await self._s.flush()
        return len(rows)

    async def get(self, flow_id: str) -> Optional[FlowRecord]:
        r = (await self._s.execute(
            select(FlowRecordORM).where(FlowRecordORM.flow_id == flow_id)
        )).scalar_one_or_none()
        return self._to_domain(r) if r else None

    @staticmethod
    def _to_domain(r: FlowRecordORM) -> FlowRecord:
        from app.domain.common import Protocol
        return FlowRecord(
            flow_id=r.flow_id,
            created_at=datetime.fromisoformat(r.created_at),
            src_ip=r.src_ip,
            dst_ip=r.dst_ip,
            src_port=r.src_port,
            dst_port=r.dst_port,
            protocol=Protocol(r.protocol),
            duration_ms=r.duration_ms,
            packets_src_to_dst=r.packets_src_to_dst,
            packets_dst_to_src=r.packets_dst_to_src,
            bytes_src_to_dst=r.bytes_src_to_dst,
            bytes_dst_to_src=r.bytes_dst_to_src,
            feature_schema_version=r.feature_schema_version,
            features=json.loads(r.features_json or "{}"),
            dataset_id=r.dataset_id,
            source_ref=r.source_ref,
        )
