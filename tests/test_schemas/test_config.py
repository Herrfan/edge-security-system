"""Tests for config + logging redaction filter."""
from __future__ import annotations

import logging

import pytest

from app.core.config import Settings, get_settings
from app.core.logging import RedactionFilter, _redact_value


class TestSettingsLoads:
    def test_defaults(self):
        # get_settings caches; clear for isolation
        import app.core.config as cfg_mod
        cfg_mod.get_settings.cache_clear()
        s = get_settings()
        assert s.app_name == "edge-security-system"
        assert s.app_port == 8000
        assert s.allow_real_execution is False
        assert "127.0.0.0/8" in s.authorized_assets


class TestLoggingRedaction:
    def test_ip_masked(self):
        filt = RedactionFilter()
        record = logging.LogRecord(
            "test", logging.INFO, "file", 1,
            "Flow from 192.168.1.10 to 10.0.0.5", args=(), exc_info=None,
        )
        filt.filter(record)
        assert "*.*.*.*" in record.msg
        assert "192.168.1.10" not in record.msg
        assert "10.0.0.5" not in record.msg

    def test_secret_kv_masked(self):
        s = "api_key=sk-abcdef0123456789 secret=mysecret123"
        out = _redact_value(s)
        assert "***REDACTED***" in out
        assert "sk-abcdef0123456789" not in out

    def test_port_masked(self):
        s = "listening on port=4433"
        out = _redact_value(s)
        assert "***" in out
        assert "4433" not in out

    def test_dict_recursive(self):
        d = {"msg": "conn 10.0.0.1:22", "nested": {"token": "abc123"}}
        out = _redact_value(d)
        assert "*.*.*.*" in out["msg"]
        assert "***REDACTED***" in out["nested"]["token"]

    def test_non_string_passthrough(self):
        assert _redact_value(42) == 42
        assert _redact_value(None) is None


class TestHealthEndpoint:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "edge-security-system"
        assert "version" in body
        assert "pid" in body

    def test_root_docs_link(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "/docs" in resp.json()["docs"]
