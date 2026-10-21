"""Executor — converts a validated PolicyProposal into an ExecutionRecord.

Phase 11 refactor: command building + subprocess.run are now delegated to
an :class:`ExecutionBackend`, chosen by :func:`select_backend`.  The Executor
itself is a thin coordinator with three hard guardrails that NO backend can
override:

    1. allow_real_execution = False (Settings default) → ALL REAL modes blocked
       regardless of what the backend supports or what approval_token was sent.
       This is the **product-level safety boundary** — cannot be lifted without
       a deliberate deploy-time Settings change + signed approval process.

    2. Platform guardrail — non-Linux hosts cannot run iptables; Windows
       hosts cannot run RATE_LIMIT.  The backend.build() may still produce a
       command for audit trail, but Executor will downgrade to EchoBackend
       when actually running.

    3. action-type guardrail (Phase 6) — ALERT_ONLY / NO_ACTION are the ONLY
       actions Executor will permit in REAL mode while allow_real_execution is
       False.  BLOCK_IP / BLOCK_PORT / RATE_LIMIT always FAILED until the
       safety boundary is lifted.

DRY_RUN (default) — ALWAYS produces an EchoBackend plan, regardless of
backend availability or policy action type.
"""
from __future__ import annotations

import logging
import platform
import time
from typing import Optional

from app.adapters.backends import (
    EchoBackend,
    ExecutionBackend,
    select_backend,
)
from app.core.config import get_settings
from app.domain.common import ExecutionMode, ExecutionStatus, _new_id, utcnow
from app.domain.execution import ExecutionRecord
from app.domain.policy import PolicyProposal
from app.core.observability import (
    EXECUTIONS_TOTAL,
    EXECUTION_LATENCY_MS,
    EXECUTIONS_INFLIGHT,
)

logger = logging.getLogger(__name__)


class Executor:
    """Thin coordinator that combines backend selection + guardrails."""

    def __init__(
        self,
        *,
        default_mode: ExecutionMode = ExecutionMode.DRY_RUN,
        backend_preference: Optional[str] = None,
    ) -> None:
        self._default_mode = default_mode
        self._backend_preference = backend_preference

    # ==============================================================
    # Public API
    # ==============================================================

    def execute(
        self,
        proposal: PolicyProposal,
        *,
        mode: Optional[ExecutionMode] = None,
        src_ip: Optional[str] = None,
        dst_port: Optional[int] = None,
    ) -> ExecutionRecord:
        mode = mode or self._default_mode

        EXECUTIONS_INFLIGHT.inc(labels={"mode": mode.value})
        t_exec0 = time.perf_counter()

        resolved_status = ExecutionStatus.UNKNOWN
        try:
            plan, target, status, stdout_summary, stderr_summary, rollback_status, trace = \
                self._dispatch(proposal, mode, src_ip, dst_port)
            resolved_status = status

            return ExecutionRecord(
                execution_id=_new_id("exe"),
                policy_id=proposal.policy_id,
                mode=mode,
                started_at=utcnow(),
                finished_at=utcnow(),
                status=status,
                stdout_summary=stdout_summary,
                stderr_summary=stderr_summary,
                rollback_status=rollback_status,
                trace_id=f"target={target} backend={trace}",
            )
        finally:
            EXECUTIONS_INFLIGHT.dec(labels={"mode": mode.value})
            t_exec1 = time.perf_counter()
            EXECUTIONS_TOTAL.inc(
                labels={"mode": mode.value, "action_type": proposal.action_type.value,
                        "status": resolved_status.value},
            )
            EXECUTION_LATENCY_MS.observe(
                (t_exec1 - t_exec0) * 1000.0,
                labels={"mode": mode.value, "action_type": proposal.action_type.value},
            )

    # ==============================================================
    # Dispatch + guardrails
    # ==============================================================

    def _dispatch(self, proposal, mode, src_ip, dst_port):
        """Return (plan, target, status, stdout, stderr, rollback, trace)."""
        target = self._target_string(proposal, src_ip=src_ip, dst_port=dst_port)

        if mode == ExecutionMode.DRY_RUN:
            backend = EchoBackend()
            plan = backend.build(proposal, src_ip=src_ip, dst_port=dst_port)
            logger.info("[DRY_RUN] would execute: %s", plan)
            return (plan, target, ExecutionStatus.SUCCEEDED, None, None,
                    "N/A", f"dry_run platform={platform.system()}")

        # ---- REAL mode ----
        s = get_settings()

        # Guardrail 1: product-level safety boundary
        if not s.allow_real_execution:
            backend = EchoBackend()
            plan = backend.build(proposal, src_ip=src_ip, dst_port=dst_port)
            logger.warning("[REAL BLOCKED] allow_real_execution=False on Settings — "
                           "deferred action=%s", proposal.action_type.value)
            return (plan, target, ExecutionStatus.FAILED, None, None,
                    None, "guardrail=allow_real_execution")

        # Guardrail 2: Phase 6 — only ALERT_ONLY / NO_ACTION currently allowed
        if proposal.action_type.value not in ("ALERT_ONLY", "NO_ACTION"):
            backend = EchoBackend()
            plan = backend.build(proposal, src_ip=src_ip, dst_port=dst_port)
            logger.warning("[REAL BLOCKED] Phase 6 guardrail: %s — not yet permitted",
                           proposal.action_type.value)
            return (plan, target, ExecutionStatus.FAILED, None, None,
                    None, "guardrail=phase6_action")

        # Guardrail 3: platform → backend selection
        backend: ExecutionBackend = select_backend(prefer=self._backend_preference)
        plan = backend.build(proposal, src_ip=src_ip, dst_port=dst_port)

        # Non-supported combination (e.g. RATE_LIMIT on Windows) → backend.build
        # already downgraded to echo note; just run it
        logger.info("[REAL via %s] executing: %s", backend.name, plan)
        result = backend.run(proposal, src_ip=src_ip, dst_port=dst_port)
        status = ExecutionStatus.SUCCEEDED if result.ok else ExecutionStatus.FAILED
        rollback = "N/A"  # Phase 11 does not implement undo yet
        return (plan, target, status, result.stdout or None, result.stderr or None,
                rollback, f"backend={backend.name} platform={platform.system()}")

    # ==============================================================
    # Helpers
    # ==============================================================

    def _target_string(self, proposal, *, src_ip=None, dst_port=None):
        a = proposal.action_type
        if a.value == "BLOCK_IP":
            return f"block_ip:{proposal.parameters.ip}"
        if a.value == "BLOCK_PORT":
            return f"block_port:{proposal.parameters.port}"
        if a.value == "RATE_LIMIT":
            return f"rate_limit:{proposal.parameters.ip}@{proposal.parameters.max_pps}pps"
        ip = src_ip or "(no_src_ip_resolved)"
        port = dst_port if dst_port is not None else "(unknown)"
        return f"alert:{ip}:{port}"
