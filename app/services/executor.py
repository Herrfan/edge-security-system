"""Executor — converts a validated PolicyProposal into an ExecutionRecord.

Two modes:
  * DRY_RUN (default) — produce the plan but do NOT touch system state.
  * REAL   — actually attempt the command. Phase 6 restricts this to a
             handfull of safe, audit-friendly system calls (ALERT_ONLY echo).
             BLOCK_IP / BLOCK_PORT / RATE_LIMIT are blocked by a guardrail
             — those land when we integrate with real iptables / nft.

ALWAYS surfaces the EXACT command we *would* run (dry_run=True) so a human
reviewer can sanity-check before approving REAL execution.
"""
from __future__ import annotations

import logging
import subprocess
import time
from typing import Optional

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
    """Pure local executor. No network device reach-out."""

    def __init__(self, default_mode: ExecutionMode = ExecutionMode.DRY_RUN) -> None:
        self._default_mode = default_mode

    def execute(
        self,
        proposal: PolicyProposal,
        *,
        mode: Optional[ExecutionMode] = None,
        src_ip: Optional[str] = None,
        dst_port: Optional[int] = None,
    ) -> ExecutionRecord:
        """Execute (or plan) a policy. Returns an ExecutionRecord."""
        mode = mode or self._default_mode

        # --- observability: inflight tracking + latency histogram ---
        EXECUTIONS_INFLIGHT.inc(labels={"mode": mode.value})
        t_exec0 = time.perf_counter()

        try:
            plan = self._build_command(proposal, src_ip=src_ip, dst_port=dst_port)
            target = self._target_string(proposal, src_ip=src_ip, dst_port=dst_port)

            status = ExecutionStatus.SUCCEEDED
            stdout_summary = None
            stderr_summary = None
            rollback_status = None
            guardrail_blocked = False

            if mode == ExecutionMode.DRY_RUN:
                logger.info("[DRY_RUN] would execute: %s", plan)
                rollback_status = "N/A"
            else:
                if not self._is_safe_to_execute(proposal):
                    guardrail_blocked = True
                    status = ExecutionStatus.FAILED
                    logger.warning("[REAL BLOCKED] Phase 6 guardrail: %s → deferred",
                                   proposal.action_type.value)
                else:
                    logger.info("[REAL] executing: %s", plan)
                    try:
                        r = subprocess.run(
                            self._shell_split(plan),
                            capture_output=True, text=True, timeout=30,
                        )
                        stdout_summary = (r.stdout or "")[:2000] or None
                        stderr_summary = (r.stderr or "")[:2000] or None
                        if r.returncode != 0:
                            status = ExecutionStatus.FAILED
                    except Exception as e:
                        status = ExecutionStatus.FAILED
                        stderr_summary = str(e)[:2000]

            finished = utcnow()
            return ExecutionRecord(
                execution_id=_new_id("exe"),
                policy_id=proposal.policy_id,
                mode=mode,
                started_at=utcnow(),
                finished_at=finished,
                status=status,
                stdout_summary=stdout_summary,
                stderr_summary=stderr_summary,
                rollback_status=rollback_status,
                trace_id=f"target={target} guardrail={guardrail_blocked}",
            )
        finally:
            EXECUTIONS_INFLIGHT.dec(labels={"mode": mode.value})
            t_exec1 = time.perf_counter()
            action_type = proposal.action_type.value
            EXECUTIONS_TOTAL.inc(
                labels={"mode": mode.value, "action_type": action_type, "status": status.value},
            )
            EXECUTION_LATENCY_MS.observe(
                (t_exec1 - t_exec0) * 1000.0,
                labels={"mode": mode.value, "action_type": action_type},
            )

    # -------- helpers ---------

    def _target_string(self, proposal: PolicyProposal, *, src_ip: Optional[str], dst_port: Optional[int]) -> str:
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

    def _build_command(self, proposal: PolicyProposal, *, src_ip: Optional[str], dst_port: Optional[int]) -> str:
        a = proposal.action_type
        if a.value == "BLOCK_IP":
            return f"sudo ip rule add from {proposal.parameters.ip} priority 100 reject"
        if a.value == "BLOCK_PORT":
            return f"sudo nft add rule inet filter input drop dport {proposal.parameters.port} counter"
        if a.value == "RATE_LIMIT":
            return (
                f"sudo nft add rule inet filter input ip saddr {proposal.parameters.ip} "
                f"limit rate over {proposal.parameters.max_pps}/second burst "
                f"{proposal.parameters.max_pps}/second drop counter"
            )
        ip = src_ip or "(no src_ip resolved)"
        port = dst_port if dst_port is not None else "(unknown)"
        return (
            f"echo '[ALERT_ONLY] policy_id={proposal.policy_id} src_ip={ip} "
            f"dst_port={port} severity={proposal.risk_level.value} "
            f"rationale={proposal.rationale[:80]}'"
        )

    def _is_safe_to_execute(self, proposal: PolicyProposal) -> bool:
        """REAL guardrail — Phase 6: only ALERT_ONLY / NO_ACTION are shell-safe."""
        return proposal.action_type.value in ("ALERT_ONLY", "NO_ACTION")

    @staticmethod
    def _shell_split(cmd: str) -> list[str]:
        import shlex
        try:
            return shlex.split(cmd)
        except ValueError:
            return [cmd]
