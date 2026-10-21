"""PolicyProposal repository."""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import PolicyProposalORM
from app.domain.common import PolicyStatus, Severity, utcnow
from app.domain.policy import PolicyProposal


class PolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, p: PolicyProposal) -> PolicyProposal:
        self._s.add(PolicyProposalORM(
            policy_id=p.policy_id,
            created_at=p.created_at.isoformat(),
            event_id=p.event_id,
            action_type=p.action_type.value,
            parameters_json=p.parameters.model_dump_json(),
            risk_level=p.risk_level.value,
            rationale=p.rationale,
            evidence_ids_json=json.dumps(p.evidence_ids),
            ttl_seconds=p.ttl_seconds,
            status=p.status.value,
            requires_approval=p.requires_approval,
            expires_at=p.expires_at.isoformat() if p.expires_at else None,
        ))
        await self._s.flush()
        return p

    async def get(self, policy_id: str) -> Optional[PolicyProposal]:
        r = (await self._s.execute(
            select(PolicyProposalORM).where(PolicyProposalORM.policy_id == policy_id)
        )).scalar_one_or_none()
        return self._to_domain(r) if r else None

    async def list(self, *, status: Optional[PolicyStatus] = None, limit: int = 50) -> List[PolicyProposal]:
        stmt = select(PolicyProposalORM)
        if status:
            stmt = stmt.where(PolicyProposalORM.status == status.value)
        stmt = stmt.order_by(PolicyProposalORM.created_at.desc()).limit(limit)
        rows = (await self._s.execute(stmt)).scalars().all()
        return [self._to_domain(r) for r in rows]

    async def update_status(self, policy_id: str, status: PolicyStatus) -> None:
        r = (await self._s.execute(
            select(PolicyProposalORM).where(PolicyProposalORM.policy_id == policy_id)
        )).scalar_one_or_none()
        if r is None:
            raise ValueError(f"policy_id {policy_id!r} not found")
        r.status = status.value
        await self._s.flush()

    @staticmethod
    def _to_domain(r: PolicyProposalORM) -> PolicyProposal:
        from app.domain.common import ActionType, PolicyStatus, Severity
        from app.domain.policy import (
            BlockIpParams, BlockPortParams, PolicyProposal, RateLimitParams,
        )

        action = ActionType(r.action_type)
        params_cls = {
            ActionType.BLOCK_IP: BlockIpParams,
            ActionType.RATE_LIMIT: RateLimitParams,
            ActionType.BLOCK_PORT: BlockPortParams,
        }.get(action, BlockPortParams)  # default — ALERT_ONLY / NO_ACTION carry any params
        params_data = json.loads(r.parameters_json or "{}")
        params = params_cls.model_validate(params_data)

        return PolicyProposal(
            policy_id=r.policy_id,
            created_at=datetime.fromisoformat(r.created_at),
            event_id=r.event_id,
            action_type=action,
            parameters=params,
            risk_level=Severity(r.risk_level),
            rationale=r.rationale,
            evidence_ids=json.loads(r.evidence_ids_json or "[]"),
            ttl_seconds=r.ttl_seconds,
            status=PolicyStatus(r.status),
            requires_approval=r.requires_approval,
            expires_at=datetime.fromisoformat(r.expires_at) if r.expires_at else None,
        )
