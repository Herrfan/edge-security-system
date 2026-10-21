"""Phase 11 — ExecutionBackend registry + RBAC 测试。"""
from __future__ import annotations

import platform
import pytest

from app.adapters.backends import (
    EchoBackend,
    ExecutionBackend,
    IptablesBackend,
    WindowsBackend,
    select_backend,
)
from app.domain.common import ActionType, ExecutionMode, Severity
from app.domain.policy import (
    BlockIpParams,
    BlockPortParams,
    PolicyProposal,
    RateLimitParams,
)
from app.services.executor import Executor


def _prop(*, action=ActionType.BLOCK_IP, ip="10.0.0.5", port=80, ttl=3600,
          requires_approval=False) -> PolicyProposal:
    if action == ActionType.BLOCK_IP:
        params = BlockIpParams(ip=ip)
    elif action == ActionType.BLOCK_PORT:
        params = BlockPortParams(port=port)
    elif action == ActionType.RATE_LIMIT:
        params = RateLimitParams(ip=ip, max_pps=1000)
    else:
        params = BlockIpParams(ip=ip)
    return PolicyProposal(
        event_id="evt_phase11",
        action_type=action,
        parameters=params,
        ttl_seconds=ttl,
        rationale="phase11 test",
        requires_approval=requires_approval,
        risk_level=Severity.HIGH,
    )


# =====================================================================
# Backend selection
# =====================================================================


class TestBackendSelection:
    def test_select_returns_backend_instance(self):
        b = select_backend()
        assert isinstance(b, ExecutionBackend)
        # Fallback guarantee — something is always selectable
        assert b.name in ("echo", "iptables", "windows")

    def test_select_prefer_echo(self):
        b = select_backend(prefer="echo")
        assert isinstance(b, EchoBackend)

    def test_select_prefer_nonexistent_ignored(self):
        b = select_backend(prefer="nonexistent-backend")
        # should fallback to auto-detect, not raise
        assert isinstance(b, ExecutionBackend)


# =====================================================================
# EchoBackend
# =====================================================================


class TestEchoBackend:
    def test_echo_is_always_supported(self):
        assert EchoBackend.is_supported() is True

    def test_echo_alert_only_command_contains_echo(self):
        b = EchoBackend()
        p = _prop(action=ActionType.ALERT_ONLY)
        cmd = b.build(p, src_ip="10.0.0.5", dst_port=80)
        assert "echo" in cmd
        assert "ALERT_ONLY" in cmd

    def test_echo_block_ip_command_contains_guardrail(self):
        """即便 EchoBackend 收到 BLOCK_IP，也只能 echo guardrail note — 不能产真实命令."""
        b = EchoBackend()
        p = _prop(action=ActionType.BLOCK_IP, ip="10.0.0.5")
        cmd = b.build(p)
        assert "echo" in cmd
        assert "GUARDRAIL" in cmd

    def test_echo_no_shell_metachar(self):
        b = EchoBackend()
        p = _prop(action=ActionType.BLOCK_IP, ip="10.0.0.5")
        cmd = b.build(p)
        for bad in [";", "|", "&", "`", "$("]:
            assert bad not in cmd


# =====================================================================
# IptablesBackend (Linux-only behavior)
# =====================================================================


class TestIptablesBackendBuild:
    def test_iptables_block_ip_build(self):
        if not IptablesBackend.is_supported() and platform.system() != "Linux":
            pytest.skip("IptablesBackend only builds on Linux; but build() is pure string op")
        # Even on Windows, build() returns a deterministic nft command (but is_supported=False)
        b = IptablesBackend()
        p = _prop(action=ActionType.BLOCK_IP, ip="10.0.0.5")
        cmd = b.build(p)
        assert "nft" in cmd
        assert "10.0.0.5" in cmd

    def test_iptables_rate_limit_has_limit_phrase(self):
        b = IptablesBackend()
        p = _prop(action=ActionType.RATE_LIMIT, ip="10.0.0.5")
        cmd = b.build(p)
        assert "limit rate" in cmd


# =====================================================================
# WindowsBackend — RATE_LIMIT unsupported
# =====================================================================


class TestWindowsBackendBuild:
    def test_windows_block_ip_uses_netsh(self):
        b = WindowsBackend()
        p = _prop(action=ActionType.BLOCK_IP, ip="10.0.0.5")
        cmd = b.build(p)
        assert "netsh" in cmd
        assert "10.0.0.5" in cmd

    def test_windows_rate_limit_downgrades_to_echo(self):
        b = WindowsBackend()
        p = _prop(action=ActionType.RATE_LIMIT, ip="10.0.0.5")
        cmd = b.build(p)
        assert "echo" in cmd
        assert "RATE_LIMIT UNSUPPORTED" in cmd


# =====================================================================
# Executor + allow_real_execution boundary
# =====================================================================


class TestAllowRealExecutionBoundary:
    """Phase 11's PRODUCT-LEVEL guardrail: Settings.allow_real_execution=False
    must block ALL REAL actions regardless of backend or platform."""

    def test_real_blocked_when_setting_false(self, monkeypatch):
        from app.core.config import Settings
        s = Settings()
        s.allow_real_execution = False

        # Stub Executor's get_settings call to return our fake
        import app.services.executor as exec_mod
        monkeypatch.setattr(exec_mod, "get_settings", lambda: s)

        executor = Executor()
        p = _prop(action=ActionType.ALERT_ONLY)
        # ALERT_ONLY / NO_ACTION are allowed through platform check, but the
        # allow_real_execution guardrail comes FIRST in dispatch()
        rec = executor.execute(p, mode=ExecutionMode.REAL)
        assert rec.status.value == "FAILED"
        assert "allow_real_execution" in (rec.trace_id or "")

    def test_real_block_ip_still_blocked_after_setting_true(self, monkeypatch):
        """allow_real_execution=True + BLOCK_IP → Phase 6 guardrail still applies."""
        from app.core.config import Settings
        s = Settings()
        s.allow_real_execution = True
        import app.services.executor as exec_mod
        monkeypatch.setattr(exec_mod, "get_settings", lambda: s)

        executor = Executor()
        p = _prop(action=ActionType.BLOCK_IP, ip="10.0.0.5")
        rec = executor.execute(p, mode=ExecutionMode.REAL)
        assert rec.status.value == "FAILED"
        # Phase 6 guardrail comes after allow_real_execution gate
        assert rec.trace_id is not None


# =====================================================================
# RBAC
# =====================================================================


class TestRBAC:
    def test_role_ordering(self):
        from app.middleware.auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER
        assert ROLE_ADMIN == "admin"
        assert ROLE_OPERATOR == "operator"
        assert ROLE_VIEWER == "viewer"

    def test_require_roles_disabled_passthrough(self):
        from unittest.mock import patch
        from app.middleware.auth import require_roles, require_auth
        from app.middleware.auth import get_settings as _get_settings

        class _S:
            auth_enabled = False
            auth_jwt_secret = ""
            auth_token_ttl_minutes = 60

        with patch("app.middleware.auth.get_settings", return_value=_S()):
            checker = require_roles("admin")
            # payload is what require_auth returns when disabled
            result = checker({"sub": "anonymous", "auth_enabled": False})
            assert result["sub"] == "anonymous"

    def test_require_roles_enabled_admin_passes(self):
        from unittest.mock import patch
        from app.middleware.auth import require_roles

        class _S:
            auth_enabled = True
            auth_jwt_secret = "s3cret"
            auth_token_ttl_minutes = 60

        with patch("app.middleware.auth.get_settings", return_value=_S()):
            checker = require_roles("admin", "operator")
            result = checker({"sub": "alice", "role": "admin"})
            assert result["sub"] == "alice"

    def test_require_roles_enabled_viewer_blocked_from_execute(self):
        from unittest.mock import patch
        from fastapi import HTTPException
        from app.middleware.auth import require_roles

        class _S:
            auth_enabled = True
            auth_jwt_secret = "s3cret"
            auth_token_ttl_minutes = 60

        with patch("app.middleware.auth.get_settings", return_value=_S()):
            checker = require_roles("admin", "operator")
            with pytest.raises(HTTPException) as ei:
                checker({"sub": "bob", "role": "viewer"})
            assert ei.value.status_code == 403
            assert "viewer" in ei.value.detail
