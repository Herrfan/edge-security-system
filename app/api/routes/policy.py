"""Phase 6 policy + execution routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session

router = APIRouter(prefix="/api/v1", tags=["policy", "execution"])


class EnrichEventBody(BaseModel):
    event_id: str


class GenerateBody(BaseModel):
    event_id: str


class ValidateBody(BaseModel):
    policy_id: str
    src_ip: Optional[str] = None
    dst_port: Optional[int] = None


class ExecuteBody(BaseModel):
    policy_id: str
    mode: str = "DRY_RUN"  # DRY_RUN | REAL
    approval_token: Optional[str] = None


class ApproveBody(BaseModel):
    """Approve or reject a policy that currently holds NEEDS_APPROVAL."""
    policy_id: str
    approve: bool = True           # true = APPROVED, false = REJECTED
    reason: Optional[str] = None   # human-readable audit note
    approver: Optional[str] = None # e.g. operator email
    # approval_token is a shared secret the backend accepts once — matches Phase 9
    # red-team test; keep as a simple pre-shared value for the MVP.
    approval_token: Optional[str] = None


# -------- POST /policy-proposal/generate -----------------------------------


@router.post("/policy-proposal/generate")
async def policy_proposal_generate(body: GenerateBody, session: AsyncSession = Depends(get_session)) -> dict:
    """Phase 6 end-to-end: Event → RAG → persist Proposal."""
    from app.repositories.event_repository import EventRepository
    from app.services.policy_service import EndToEndPolicyService

    event = await EventRepository(session).get(body.event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"event {body.event_id!r} not found")

    svc = EndToEndPolicyService(session)
    rag_result = await svc.generate_proposal(event)

    return {
        "proposal": rag_result.proposal.model_dump(mode="json"),
        "evidences": [e.model_dump(mode="json") for e in rag_result.evidences],
        "evidence_count": len(rag_result.evidences),
        "retrieval_status": rag_result.retrieval_status,
        "llm_provider": rag_result.llm_provider,
        "llm_is_mock": rag_result.llm_is_mock,
        "llm_latency_ms": round(rag_result.llm_latency_ms, 3),
    }


# -------- POST /policy-proposal/validate -----------------------------------


@router.post("/policy-proposal/validate")
async def policy_proposal_validate(body: ValidateBody, session: AsyncSession = Depends(get_session)) -> dict:
    """Run the deterministic validator on a persisted proposal."""
    from app.repositories.policy_repository import PolicyRepository
    from app.services.policy_service import EndToEndPolicyService

    proposal = await PolicyRepository(session).get(body.policy_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"policy {body.policy_id!r} not found")

    svc = EndToEndPolicyService(session)
    vr = svc.validate_only(proposal, src_ip=body.src_ip, dst_port=body.dst_port)
    return {
        "policy_id": body.policy_id,
        "is_valid": vr.is_valid,
        "reasons": vr.reasons,
    }


# -------- POST /policy-proposal/approve -----------------------------------


@router.post("/policy-proposal/approve")
async def policy_proposal_approve(body: ApproveBody, session: AsyncSession = Depends(get_session)) -> dict:
    """Approve or reject a proposal that is currently NEEDS_APPROVAL.

    State machine:
      NEEDS_APPROVAL → APPROVED  (approve=true)
      NEEDS_APPROVAL → REJECTED  (approve=false)
      Any other source status → 409 Conflict (illegal transition)

    This endpoint does NOT actually execute the policy — it only transitions
    the status. The caller must then POST /policy-proposal/execute.
    """
    from app.domain.common import PolicyStatus
    from app.repositories.policy_repository import PolicyRepository

    repo = PolicyRepository(session)
    proposal = await repo.get(body.policy_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"policy {body.policy_id!r} not found")

    if proposal.status != PolicyStatus.NEEDS_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=(
                f"policy is not in NEEDS_APPROVAL (current={proposal.status.value}); "
                f"only NEEDS_APPROVAL can be approved/rejected"
            ),
        )

    new_status = PolicyStatus.APPROVED if body.approve else PolicyStatus.REJECTED
    await repo.update_status(body.policy_id, new_status)

    return {
        "policy_id": body.policy_id,
        "status": new_status.value,
        "approver": body.approver,
        "reason": body.reason,
    }


# -------- POST /policy-proposal/execute ------------------------------------


@router.post("/policy-proposal/execute")
async def policy_proposal_execute(body: ExecuteBody, session: AsyncSession = Depends(get_session)) -> dict:
    """Dry-run or real execute a policy."""
    from app.domain.common import ExecutionMode
    from app.services.policy_service import EndToEndPolicyService

    try:
        mode = ExecutionMode(body.mode.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid mode {body.mode!r}")

    svc = EndToEndPolicyService(session)
    try:
        rec, vr = await svc.execute(
            body.policy_id,
            mode=mode,
            approval_token=body.approval_token,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    duration_ms: float | None = None
    if rec.finished_at and rec.started_at:
        duration_ms = (rec.finished_at - rec.started_at).total_seconds() * 1000

    return {
        "execution_id": rec.execution_id,
        "policy_id": rec.policy_id,
        "mode": rec.mode.value,
        "status": rec.status.value,
        "started_at": rec.started_at.isoformat(),
        "finished_at": rec.finished_at.isoformat() if rec.finished_at else None,
        "stdout_summary": rec.stdout_summary,
        "stderr_summary": rec.stderr_summary,
        "rollback_status": rec.rollback_status,
        "trace_id": rec.trace_id,
        "duration_ms": round(duration_ms, 3) if duration_ms is not None else None,
        "validator_reasons": vr.reasons,
    }


# -------- GET /policy-proposals --------------------------------------------


@router.get("/policy-proposals")
async def policy_proposals_list(
    status: Optional[str] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> list:
    from app.domain.common import PolicyStatus
    from app.repositories.policy_repository import PolicyRepository

    s = PolicyStatus(status) if status else None
    proposals = await PolicyRepository(session).list(status=s, limit=limit)
    return [p.model_dump(mode="json") for p in proposals]


# -------- Helper: persist flows from the synthetic CSV ----------------------


@router.post("/flows/seed-policy")
async def flows_seed_policy(path: str, session: AsyncSession = Depends(get_session)) -> dict:
    """Import flows from a CSV so Executor can resolve src_ip. Dev helper."""
    from pathlib import Path
    from app.repositories.flow_repository import FlowRepository
    from app.services.ingestion import iter_records

    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"path not found: {path}")

    flows = list(iter_records(p))
    n = await FlowRepository(session).bulk_create(flows)
    return {"imported_flows": n}
