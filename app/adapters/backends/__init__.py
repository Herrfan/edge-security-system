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
    rule_handle: Optional[str] = None  # nft rule handle for atomic delete

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class ExecutionBackend(ABC):
    """Abstract base for enforcement backends."""

    name: str = "abstract"

    @staticmethod
    @abstractmethod
    def is_supported() -> bool: ...

    @abstractmethod
    def build(self, proposal: PolicyProposal, *, src_ip=None, dst_port=None) -> str: ...

    # Default run() — every backend can execute a single command
    def run(self, proposal, *, src_ip=None, dst_port=None, timeout=30.0) -> BackendResult:
        cmd = self.build(proposal, src_ip=src_ip, dst_port=dst_port)
        import shlex
        try:
            args = shlex.split(cmd)
        except ValueError:
            args = [cmd]
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            return BackendResult(
                returncode=r.returncode,
                stdout=(r.stdout or "")[:2000],
                stderr=(r.stderr or "")[:2000],
            )
        except Exception as e:
            return BackendResult(returncode=-1, stderr=str(e)[:2000])

    # Phase 12: atomic apply + rollback
    def run_atomic(self, proposal, *, src_ip=None, dst_port=None, timeout=30.0) -> BackendResult:
        """Attempt run(); on failure, attempt rollback. Base impl = run() only — override in
        backends that support rollback (nftables / netsh delete rule)."""
        result = self.run(proposal, src_ip=src_ip, dst_port=dst_port, timeout=timeout)
        if not result.ok and result.rule_handle:
            self.rollback(result.rule_handle, timeout=timeout)
        return result

    def rollback(self, rule_handle: str, *, timeout=10.0) -> BackendResult:
        """Delete a previously applied rule identified by handle. Returns its own result."""
        # Default no-op override in IptablesBackend / WindowsBackend
        return BackendResult(returncode=0)


# ============================================================================
# EchoBackend
# ============================================================================


class EchoBackend(ExecutionBackend):
    """No-op backend — always produces safe echo commands, never touches firewall.

    run() is a special-case: it does NOT call subprocess.run() (which would fail
    on Windows because ``echo`` is a cmd built-in, not a .exe).  Instead it returns
    a BackendResult with returncode=0 and stdout=plan, so downstream code (Executor
    / Observability / tests) all see SUCCEEDED regardless of platform.
    """

    name = "echo"

    @staticmethod
    def is_supported() -> bool:
        return True

    def build(self, proposal, *, src_ip=None, dst_port=None) -> str:
        a = proposal.action_type
        if a.value in ("ALERT_ONLY", "NO_ACTION"):
            ip = src_ip or "(no_src_ip)"
            port = dst_port if dst_port is not None else "(unknown)"
            return (
                f"echo '[ALERT_ONLY] policy_id={proposal.policy_id} "
                f"src_ip={ip} dst_port={port} severity={proposal.risk_level.value} "
                f"rationale={proposal.rationale[:80]}'"
            )
        target = f"block_ip:{proposal.parameters.ip}" if a.value == "BLOCK_IP" else \
                 f"block_port:{proposal.parameters.port}" if a.value == "BLOCK_PORT" else \
                 f"rate_limit:{proposal.parameters.ip}@{proposal.parameters.max_pps}"
        return f"echo '[GUARDRAIL] would have executed {target} on real backend — blocked by security boundary'"

    def run(self, proposal, *, src_ip=None, dst_port=None, timeout=30.0) -> BackendResult:
        """Override — never spawn subprocess.  Always succeeds with plan as stdout."""
        plan = self.build(proposal, src_ip=src_ip, dst_port=dst_port)
        return BackendResult(returncode=0, stdout=plan, stderr="")


# ============================================================================
# IptablesBackend (Linux)
# ============================================================================


class IptablesBackend(ExecutionBackend):
    """Linux iptables / nft backend. Phase 12 adds atomic rollback via rule_handle.

    nft list ruleset -h 输出中每条规则前面带一个数字 handle（例如 `handle 42`），
    我们在 run() 执行完后 parse 一次 list 找到 handle，存进 BackendResult.rule_handle。
    失败时 Executor 会调 rollback(handle) 用 `nft delete rule inet filter input handle N`
    原子删除 — 不会残留半条规则。
    """

    name = "iptables"

    @staticmethod
    def is_supported() -> bool:
        return platform.system() == "Linux"

    def build(self, proposal, *, src_ip=None, dst_port=None) -> str:
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
        return EchoBackend().build(proposal, src_ip=src_ip, dst_port=dst_port)

    def run(self, proposal, *, src_ip=None, dst_port=None, timeout=30.0) -> BackendResult:
        result = super().run(proposal, src_ip=src_ip, dst_port=dst_port, timeout=timeout)
        if result.ok:
            # 找 rule_handle — 从 proposal 的 target ip / port 倒推
            handle = self._find_handle(proposal)
            if handle:
                result.rule_handle = handle
        return result

    def rollback(self, rule_handle: str, *, timeout=10.0) -> BackendResult:
        import shlex
        cmd = f"sudo nft delete rule inet filter input handle {rule_handle}"
        try:
            args = shlex.split(cmd)
        except ValueError:
            args = [cmd]
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            return BackendResult(returncode=r.returncode, stdout=(r.stdout or "")[:500],
                                 stderr=(r.stderr or "")[:500])
        except Exception as e:
            return BackendResult(returncode=-1, stderr=str(e)[:500])

    # --- internal ---

    def _find_handle(self, proposal) -> Optional[str]:
        """Parse `nft list ruleset -h` and return the handle that matches this proposal."""
        try:
            r = subprocess.run(
                ["sudo", "nft", "list", "ruleset", "-h"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                return None
        except Exception:
            return None

        a = proposal.action_type
        needle = ""
        if a.value == "BLOCK_IP":
            needle = f"ip saddr {proposal.parameters.ip}"
        elif a.value == "BLOCK_PORT":
            needle = f"dport {proposal.parameters.port}"
        elif a.value == "RATE_LIMIT":
            needle = f"ip saddr {proposal.parameters.ip} limit rate"
        else:
            return None

        for line in (r.stdout or "").splitlines():
            if needle in line:
                # format: ... handle 42 drop counter
                for tok in line.split():
                    if tok == "handle":
                        try:
                            return line.split("handle", 1)[1].split()[0]
                        except (IndexError, ValueError):
                            return None
        return None


# ============================================================================
# WindowsBackend (netsh advfirewall)
# ============================================================================


class WindowsBackend(ExecutionBackend):
    """Windows netsh advfirewall firewall backend. BLOCK_IP / BLOCK_PORT supported.
    RATE_LIMIT downgraded to echo note (no native support).
    Phase 12: rollback via `netsh advfirewall firewall delete rule name=...`.
    """

    name = "windows"

    @staticmethod
    def is_supported() -> bool:
        return platform.system() == "Windows"

    @staticmethod
    def _rule_name(proposal) -> str:
        a = proposal.action_type
        if a.value == "BLOCK_IP":
            return f"edge-block-{proposal.parameters.ip}"
        if a.value == "BLOCK_PORT":
            return f"edge-block-port-{proposal.parameters.port}"
        return "edge-rule"

    def build(self, proposal, *, src_ip=None, dst_port=None) -> str:
        a = proposal.action_type
        if a.value == "BLOCK_IP":
            return (
                f'netsh advfirewall firewall add rule name="{self._rule_name(proposal)}" '
                f'dir=in action=block enable=yes remoteip={proposal.parameters.ip}'
            )
        if a.value == "BLOCK_PORT":
            return (
                f'netsh advfirewall firewall add rule name="{self._rule_name(proposal)}" '
                f'dir=in action=block enable=yes protocol=TCP localport={proposal.parameters.port}'
            )
        if a.value == "RATE_LIMIT":
            return (
                f"echo '[RATE_LIMIT UNSUPPORTED] Windows Firewall cannot do per-IP rate limits; "
                f"proposal ip={proposal.parameters.ip} pps={proposal.parameters.max_pps}'"
            )
        return EchoBackend().build(proposal, src_ip=src_ip, dst_port=dst_port)

    def run(self, proposal, *, src_ip=None, dst_port=None, timeout=30.0) -> BackendResult:
        result = super().run(proposal, src_ip=src_ip, dst_port=dst_port, timeout=timeout)
        if result.ok and proposal.action_type.value in ("BLOCK_IP", "BLOCK_PORT"):
            result.rule_handle = self._rule_name(proposal)  # use rule name as handle
        return result

    def rollback(self, rule_handle: str, *, timeout=10.0) -> BackendResult:
        cmd = f'netsh advfirewall firewall delete rule name="{rule_handle}"'
        import shlex
        try:
            args = shlex.split(cmd, posix=False)
        except ValueError:
            args = [cmd]
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, shell=True)
            return BackendResult(returncode=r.returncode, stdout=(r.stdout or "")[:500],
                                 stderr=(r.stderr or "")[:500])
        except Exception as e:
            return BackendResult(returncode=-1, stderr=str(e)[:500])


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
