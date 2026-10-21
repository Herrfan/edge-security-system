"""End-to-end service: RAG → Validate → Execute → Persist."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.common import ExecutionMode, ExecutionStatus, PolicyStatus
from app.domain.policy import PolicyProposal
from app.repositories.execution_repository import ExecutionRepository
from app.repositories.flow_repository import FlowRepository
from app.repositories.policy_repository import PolicyRepository
from app.services.executor import Executor
from app.services.policy_validator import PolicyValidator, ValidationResult
from app.services.rag_service import RAGService, RAGRunResult


class EndToEndPolicyService:
    """Tie Phase 5 RAG + Phase 6 validation + execution together."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        rag: Optional[RAGService] = None,
        validator: Optional[PolicyValidator] = None,
        executor: Optional[Executor] = None,
    ) -> None:
        self._session = session
        self._policies = PolicyRepository(session)
        self._flows = FlowRepository(session)
        self._executions = ExecutionRepository(session)
        self._rag = rag or RAGService()
        self._validator = validator or PolicyValidator()
        self._executor = executor or Executor(default_mode=ExecutionMode.DRY_RUN)

    # -------- Step 1: generate proposal via RAG ----------

    async def generate_proposal(self, event) -> RAGRunResult:
        """Run RAG for a SecurityEvent; persist the proposal to DB."""
        # Look up flow to enrich (optional — FlowRecord may not exist)
        flow = None
        if event.flow_id:
            flow = await self._flows.get(event.flow_id)

        # Run RAG (this is synchronous — LLM call)
        rag_result = self._rag.run(event)

        # If the proposal is ALERT_ONLY (Llm couldn't resolve specifics), try
        # to enrich params from the flow if available
        proposal = rag_result.proposal
        if flow and proposal.action_type.value in ("ALERT_ONLY", "NO_ACTION"):
            proposal = self._try_enrich_from_flow(proposal, flow)

        # Validate deterministically
        vr = self._validator.validate(
            proposal,
            flow_src_ip=flow.src_ip if flow else None,
            flow_dst_port=flow.dst_port if flow else None,
        )

        if vr.is_valid:
            proposal.status = PolicyStatus.NEEDS_VALIDATION
        else:
            proposal.status = PolicyStatus.REJECTED

        # Persist proposal
        await self._policies.create(proposal)
        return rag_result

    # -------- Step 2: validate only (no execution) ----------

    def validate_only(self, proposal: PolicyProposal, *, src_ip: Optional[str] = None, dst_port: Optional[int] = None) -> ValidationResult:
        return self._validator.validate(proposal, flow_src_ip=src_ip, flow_dst_port=dst_port)

    # -------- Step 3: execute (or dry-run) ----------

    async def execute(
        self,
        policy_id: str,
        *,
        mode: ExecutionMode = ExecutionMode.DRY_RUN,
        approval_token: Optional[str] = None,
    ):
        """Look up a persisted policy, optionally resolve flow context, run Executor."""
        proposal = await self._policies.get(policy_id)
        if proposal is None:
            raise ValueError(f"policy_id {policy_id!r} not found")

        # Resolve flow context for action params
        src_ip = dst_port = None
        if proposal.event_id:
            from app.repositories.event_repository import EventRepository
            ev = await EventRepository(self._session).get(proposal.event_id)
            if ev and ev.flow_id:
                flow = await self._flows.get(ev.flow_id)
                if flow:
                    src_ip = flow.src_ip
                    dst_port = flow.dst_port

        # Run validator again with full flow context
        vr = self._validator.validate(proposal, flow_src_ip=src_ip, flow_dst_port=dst_port)
        if not vr.is_valid:
            raise ValueError(f"Policy {policy_id} failed validation: {vr.reasons}")

        # Real mode requires approval_token
        if mode == ExecutionMode.REAL:
            if not approval_token:
                raise ValueError("REAL mode requires approval_token")
            if proposal.requires_approval and not approval_token:
                raise ValueError(f"Policy {policy_id} requires_approval=True — missing approval_token")

        # Execute — Executor.execute is synchronous
        rec = self._executor.execute(
            proposal,
            mode=mode,
            src_ip=src_ip,
            dst_port=dst_port,
        )
        await self._executions.create(rec)

        # Update policy status
        if rec.status == ExecutionStatus.SUCCEEDED:
            if mode == ExecutionMode.DRY_RUN:
                proposal.status = PolicyStatus.NEEDS_APPROVAL
            else:
                proposal.status = PolicyStatus.EXECUTED
        else:
            proposal.status = PolicyStatus.REJECTED
        await self._policies.update_status(policy_id, proposal.status)
        await self._session.commit()

        return rec, vr

    # -------- helpers ----------

    @staticmethod
    def _try_enrich_from_flow(proposal: PolicyProposal, flow) -> PolicyProposal:
        """If flow has src_ip, try upgrading ALERT_ONLY → BLOCK_IP safely."""
        if flow.src_ip.startswith("192.168.250."):
            # Known attacker subnet (from Phase 2 synthetic data). Mark.
            proposal.rationale += f" Attacker subnet detected: {flow.src_ip}."
        return proposal
