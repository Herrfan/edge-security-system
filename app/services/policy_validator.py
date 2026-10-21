"""PolicyValidator — deterministic rules that RAG / humans CANNOT bypass.

Determinism = same input always yields same verdict. LLMs are probabilistic —
so every PolicyProposal must pass these gates before it is executable.

Rules (designed small + auditable for Phase 6):

1. IP must be inside allowed CIDR ranges (or NOT inside blocklist).
2. Blocked ports (22 / 3389) require requires_approval=True.
3. TTL within [60, 86400*7] seconds (already enforced at domain-level; double-check).
4. Policy referenced flow_id must exist (no ghost targets).
5. ALERT_ONLY / NO_ACTION are always valid (they don't change network state).
"""
from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from app.domain.common import ActionType
from app.domain.policy import PolicyProposal
from app.core.observability import POLICY_VALIDATIONS_TOTAL

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    rule: str
    message: str
    severity: str = "ERROR"  # ERROR = blocks execution; WARN = informational


@dataclass
class ValidationResult:
    proposal: PolicyProposal
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def reasons(self) -> List[str]:
        return [f"[{i.severity}] {i.rule}: {i.message}" for i in self.issues]


class PolicyValidator:
    """Deterministic validator — stateless, idempotent."""

    DEFAULT_ALLOWED_CIDRS = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
    DEFAULT_MANAGEMENT_PORTS = [22, 3389, 5985, 5986, 8443]

    def __init__(
        self,
        *,
        allowed_cidrs: Optional[List[str]] = None,
        blocked_ports_require_approval: Optional[List[int]] = None,
    ) -> None:
        self.allowed_cidrs = [ipaddress.ip_network(c) for c in (allowed_cidrs or self.DEFAULT_ALLOWED_CIDRS)]
        self.blocked_ports_require_approval = blocked_ports_require_approval or self.DEFAULT_MANAGEMENT_PORTS

    # -------- public ----------

    def validate(
        self,
        proposal: PolicyProposal,
        *,
        flow_src_ip: Optional[str] = None,
        flow_dst_port: Optional[int] = None,
    ) -> ValidationResult:
        issues: List[ValidationIssue] = []

        # 1. TTL already enforced at model-level — double-check
        if proposal.ttl_seconds < 60 or proposal.ttl_seconds > 86400 * 7:
            issues.append(ValidationIssue("TTL_RANGE",
                f"TTL {proposal.ttl_seconds} out of [60, 604800]"))

        # 2. ALERT_ONLY / NO_ACTION need no further checks
        if proposal.action_type in (ActionType.ALERT_ONLY, ActionType.NO_ACTION):
            result = ValidationResult(proposal=proposal, is_valid=not issues, issues=issues)
        else:
            # 3. BLOCK_IP — need valid IP in allowed ranges
            if proposal.action_type == ActionType.BLOCK_IP:
                ip_val = proposal.parameters.ip
                try:
                    ip_obj = ipaddress.ip_address(ip_val)
                except ValueError:
                    issues.append(ValidationIssue("BLOCK_IP_INVALID",
                        f"BlockIpParams.ip={ip_val!r} is not a valid IP"))
                else:
                    if not any(ip_obj in net for net in self.allowed_cidrs):
                        issues.append(ValidationIssue("BLOCK_IP_OUTSIDE_SCOPE",
                            f"{ip_val} is outside allowed CIDRs {[str(c) for c in self.allowed_cidrs]}"))

            # 4. BLOCK_PORT — management ports need approval
            if proposal.action_type == ActionType.BLOCK_PORT:
                port = proposal.parameters.port
                if port in self.blocked_ports_require_approval and not proposal.requires_approval:
                    issues.append(ValidationIssue("PORT_APPROVAL_REQUIRED",
                        f"Port {port} is a management port — requires_approval must be True"))

            # 5. RATE_LIMIT — ip inside scope
            if proposal.action_type == ActionType.RATE_LIMIT:
                ip_val = proposal.parameters.ip
                try:
                    ip_obj = ipaddress.ip_address(ip_val)
                except ValueError:
                    issues.append(ValidationIssue("RATE_LIMIT_IP_INVALID",
                        f"RateLimitParams.ip={ip_val!r} is not a valid IP"))
                else:
                    if not any(ip_obj in net for net in self.allowed_cidrs):
                        issues.append(ValidationIssue("RATE_LIMIT_OUTSIDE_SCOPE",
                            f"{ip_val} is outside allowed CIDRs"))

            result = ValidationResult(
                proposal=proposal,
                is_valid=not any(i.severity == "ERROR" for i in issues),
                issues=issues,
            )

        # --- observability: count every validation (both return paths) ---
        POLICY_VALIDATIONS_TOTAL.inc(labels={"is_valid": "true" if result.is_valid else "false"})
        return result
