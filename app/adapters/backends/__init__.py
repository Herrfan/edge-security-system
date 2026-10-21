"""ExecutionBackend ABC — abstract interface for firewall / policy enforcement backends.

Phase 11 adapter layer. The Executor should never call subprocess directly
against iptables / netsh / nft — it asks a Backend to build + optionally run
the command, based on the platform + the policy action type.

Concrete backends:

- ``EchoBackend``   — always echo-safe no-ops.  Used by DRY_RUN mode or
                      ALERT_ONLY / NO_ACTION in REAL mode on non-Linux hosts.
- ``IptablesBackend`` — builds iptables / nft commands for BLOCK_IP, BLOCK_PORT,
                      RATE_LIMIT.  Linux only.  Executor's REAL guardrail still
                      blocks these until allow_real_execution=True + approval_token.
- ``WindowsBackend`` — builds netsh advfirewall firewall commands. Windows only.

All backends are **builders** first, runners second. Executor calls
``backend.build(proposal)`` to get the command string (for audit), and
``backend.run(proposal)`` only after all guardrails have passed.
"""
from __future__ import annotations

import platform
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from app.domain.policy import PolicyProposal


@dataclass
class BackendResult:
    """Outcome of a single backend.run() call."""
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class ExecutionBackend(ABC):
    """Abstract base for enforcement backends."""

    name: str = "abstract"

    # ---- platform detection ----

    @staticmethod
    @abstractmethod
    def is_supported() -> bool:
        """Does this backend make sense on the current host?"""
        ...

    # ---- build + run ----

    @abstractmethod
    def build(self, proposal: PolicyProposal, *, src_ip: Optional[str] = None,
              dst_port: Optional[int] = None) -> str:
        """Return the command string that ``run`` would execute."""
        ...

    def run(self, proposal: PolicyProposal, *, src_ip: Optional[str] = None,
            dst_port: Optional[int] = None, timeout: float = 30.0) -> BackendResult:
        """Execute self.build(proposal) via subprocess. Override for tests."""
        cmd = self.build(proposal, src_ip=src_ip, dst_port=dst_port)
        import shlex
        try:
            args = shlex.split(cmd)
        except ValueError:
            args = [cmd]
        try:
            r = subprocess.run(
                args, capture_output=True, text=True, timeout=timeout,
            )
            return BackendResult(
                returncode=r.returncode,
                stdout=(r.stdout or "")[:2000],
                stderr=(r.stderr or "")[:2000],
            )
        except Exception as e:
            return BackendResult(returncode=-1, stderr=str(e)[:2000])


# ============================================================================
# EchoBackend
# ============================================================================


class EchoBackend(ExecutionBackend):
    """No-op backend — always produces safe echo commands, never touches firewall.

    Used by:
    - All DRY_RUN proposals
    - ALERT_ONLY / NO_ACTION in REAL mode
    - Any proposal on a platform that has no native firewall backend
    """

    name = "echo"

    @staticmethod
    def is_supported() -> bool:
        # Echo works EVERYWHERE — fallback default
        return True

    def build(self, proposal: PolicyProposal, *, src_ip=None, dst_port=None) -> str:
        a = proposal.action_type
        if a.value in ("ALERT_ONLY", "NO_ACTION"):
            ip = src_ip or "(no_src_ip)"
            port = dst_port if dst_port is not None else "(unknown)"
            return (
                f"echo '[ALERT_ONLY] policy_id={proposal.policy_id} "
                f"src_ip={ip} dst_port={port} severity={proposal.risk_level.value} "
                f"rationale={proposal.rationale[:80]}'"
            )
        # BLOCK_* / RATE_LIMIT — we still echo, but Executor guardrail should have
        # blocked this before we get here. If it leaks through, at least we
        # don't run a dangerous command.
        target = f"block_ip:{proposal.parameters.ip}" if a.value == "BLOCK_IP" else \
                 f"block_port:{proposal.parameters.port}" if a.value == "BLOCK_PORT" else \
                 f"rate_limit:{proposal.parameters.ip}@{proposal.parameters.max_pps}"
        return f"echo '[GUARDRAIL] would have executed {target} on real backend — blocked by security boundary'"


# ============================================================================
# IptablesBackend (Linux)
# ============================================================================


class IptablesBackend(ExecutionBackend):
    """Linux iptables / nft backend. Builds real firewall commands but Executor
    guardrail still blocks them unless allow_real_execution=True + approval_token.
    """

    name = "iptables"

    @staticmethod
    def is_supported() -> bool:
        return platform.system() == "Linux"

    def build(self, proposal: PolicyProposal, *, src_ip=None, dst_port=None) -> str:
        a = proposal.action_type
        if a.value == "BLOCK_IP":
            return f"sudo nft add rule inet filter input ip saddr {proposal.parameters.ip} drop counter"
        if a.value == "BLOCK_PORT":
            return f"sudo nft add rule inet filter input dport {proposal.parameters.port} drop counter"
        if a.value == "RATE_LIMIT":
            pps = proposal.parameters.max_pps
            return (
                f"sudo nft add rule inet filter input ip saddr {proposal.parameters.ip} "
                f"limit rate over {pps}/second burst {pps}/second drop counter"
            )
        # ALERT_ONLY / NO_ACTION — echo fallback
        return EchoBackend().build(proposal, src_ip=src_ip, dst_port=dst_port)


# ============================================================================
# WindowsBackend (netsh advfirewall)
# ============================================================================


class WindowsBackend(ExecutionBackend):
    """Windows netsh advfirewall firewall backend. BLOCK_IP / BLOCK_PORT supported.

    RATE_LIMIT is NOT supported — Windows Firewall doesn't do per-IP rate limits.
    """

    name = "windows"

    @staticmethod
    def is_supported() -> bool:
        return platform.system() == "Windows"

    def build(self, proposal: PolicyProposal, *, src_ip=None, dst_port=None) -> str:
        a = proposal.action_type
        if a.value == "BLOCK_IP":
            return (
                f'netsh advfirewall firewall add rule name="edge-block-{proposal.parameters.ip}" '
                f'dir=in action=block enable=yes remoteip={proposal.parameters.ip}'
            )
        if a.value == "BLOCK_PORT":
            return (
                f'netsh advfirewall firewall add rule name="edge-block-port-{proposal.parameters.port}" '
                f'dir=in action=block enable=yes protocol=TCP localport={proposal.parameters.port}'
            )
        if a.value == "RATE_LIMIT":
            # Windows has no native rate-limit — downgrade to EchoBackend note
            return (
                f"echo '[RATE_LIMIT UNSUPPORTED] Windows Firewall cannot do per-IP rate limits; "
                f"proposal ip={proposal.parameters.ip} pps={proposal.parameters.max_pps}'"
            )
        return EchoBackend().build(proposal, src_ip=src_ip, dst_port=dst_port)


# ============================================================================
# Registry
# ============================================================================


_BACKENDS: list[type[ExecutionBackend]] = [
    IptablesBackend,
    WindowsBackend,
    EchoBackend,  # fallback last
]


def select_backend(*, prefer: Optional[str] = None) -> ExecutionBackend:
    """Pick a concrete backend for the current host.

    Priority:
    1. If ``prefer`` is given and matches a supported backend → that one
    2. First backend whose ``is_supported()`` returns True
    3. EchoBackend always available as ultimate fallback
    """
    if prefer:
        for cls in _BACKENDS:
            if cls.name == prefer and cls.is_supported():
                return cls()
        # requested but not available — fall through to auto-detect

    for cls in _BACKENDS:
        if cls.is_supported():
            return cls()

    # unreachable — EchoBackend.is_supported() is always True
    return EchoBackend()
