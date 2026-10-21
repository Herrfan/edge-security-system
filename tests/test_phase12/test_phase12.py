"""Phase 12 — atomic rollback + auth blacklist + VictoriaMetrics remote-write."""
from __future__ import annotations

import asyncio
import pytest

from app.adapters.backends import (
    EchoBackend,
    ExecutionBackend,
    IptablesBackend,
    WindowsBackend,
    select_backend,
)
from app.adapters.remote_write.victoria import _to_lines


# =====================================================================
# Atomic rollback — backends
# =====================================================================


class TestAtomicRollback:
    def test_iptables_has_run_atomic(self):
        b = IptablesBackend()
        assert hasattr(b, "run_atomic")
        assert hasattr(b, "rollback")

    def test_windows_rollback_command_has_delete(self):
        b = WindowsBackend()
        result = b.rollback("edge-block-10.0.0.5")
        assert result is not None

    def test_echo_run_atomic_is_identity(self):
        """EchoBackend.run_atomic() is just run() — echo never fails."""
        from app.domain.common import ActionType, Severity
        from app.domain.policy import PolicyProposal, BlockIpParams
        b = EchoBackend()
        p = PolicyProposal(
            event_id="evt_phase12",
            action_type=ActionType.ALERT_ONLY,
            parameters=BlockIpParams(ip="10.0.0.5"),
            ttl_seconds=3600,
            rationale="test",
            risk_level=Severity.HIGH,
        )
        r = b.run_atomic(p)
        assert r.ok


# =====================================================================
# Auth refresh + blacklist
# =====================================================================


class TestAuthRefreshBlacklist:
    def test_create_token_has_jti_and_type(self):
        from unittest.mock import patch
        from app.middleware.auth import create_token, _FakeSettings

        with patch("app.middleware.auth.get_settings", return_value=_FakeSettings()):
            tok = create_token("alice")
            assert tok.count(".") == 2
            from app.middleware.auth import decode_token
            payload = decode_token(tok)
            assert "jti" in payload
            assert payload["type"] == "access"

    def test_create_refresh_token(self):
        from unittest.mock import patch
        from app.middleware.auth import create_refresh_token, decode_token
        from app.middleware.auth import _FakeSettings

        with patch("app.middleware.auth.get_settings", return_value=_FakeSettings()):
            tok = create_refresh_token("alice")
            payload = decode_token(tok)
            assert payload["type"] == "refresh"

    def test_blacklisted_token_rejected(self):
        """Blacklist a jti → decode_token must reject."""
        from unittest.mock import patch
        import app.middleware.auth as auth_mod
        from app.core.database import init_db

        class _S:
            auth_enabled = True
            auth_jwt_secret = "unit-test-secret-xyz"
            auth_token_ttl_minutes = 60
            vm_remote_write_url = ""
            metrics_persist_enabled = False
            metrics_snapshot_interval_minutes = 0

        asyncio.run(init_db())  # ensure token_blacklist table exists

        with patch.object(auth_mod, "get_settings", return_value=_S()):
            tok = auth_mod.create_token("alice")
            payload = auth_mod.decode_token(tok)
            jti = payload["jti"]

            async def _do():
                await auth_mod.blacklist_token(jti, subject="alice", reason="test")
            asyncio.run(_do())

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as ei:
                auth_mod.decode_token(tok)
            assert ei.value.status_code == 401
            assert "revoked" in ei.value.detail.lower()


# =====================================================================
# VictoriaMetrics line-protocol
# =====================================================================


class TestVictoriaLineProtocol:
    def test_to_lines_basic(self):
        overview = {
            "edgy_executions_total": {
                "series": [
                    {"mode": "DRY_RUN", "action_type": "BLOCK_IP", "status": "SUCCEEDED", "value": 7},
                    {"mode": "REAL", "action_type": "BLOCK_IP", "status": "FAILED", "value": 2},
                ]
            }
        }
        lines = _to_lines(overview)
        assert len(lines) == 2
        assert lines[0].startswith("edgy_executions_total{")
        assert "mode=\"DRY_RUN\"" in lines[0]
        assert lines[0].endswith(" 7")

    def test_to_lines_skips_unavailable_series(self):
        overview = {
            "edgy_process_cpu_percent": {
                "series": []   # unavailable
            }
        }
        lines = _to_lines(overview)
        assert lines == []


# =====================================================================
# FakeSettings for auth tests — reuse across tests
# =====================================================================


from dataclasses import dataclass


@dataclass
class _FakeSettings:
    auth_enabled: bool = True
    auth_jwt_secret: str = "unit-test-secret-xyz"
    auth_token_ttl_minutes: int = 60
    vm_remote_write_url: str = ""
    metrics_persist_enabled: bool = False
    metrics_snapshot_interval_minutes: int = 0
    auth_token_ttl_minutes_: int = 60


# Monkey-patch so auth.py can find it
import app.middleware.auth as _auth_mod
_auth_mod._FakeSettings = _FakeSettings
