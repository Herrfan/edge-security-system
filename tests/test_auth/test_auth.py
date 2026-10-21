"""Phase 10 — API auth 骨架测试。"""
from __future__ import annotations

import pytest

from app.middleware.auth import (
    _sign,
    _verify,
    auth_startup_check,
    create_token,
    decode_token,
    require_auth,
)


def test_hs256_roundtrip():
    """最小化的 _sign / _verify 必须对称。"""
    msg = b"hello.world"
    secret = "test-secret-123"
    sig = _sign(msg, secret)
    assert _verify(msg, sig, secret)
    assert not _verify(msg + b"!", sig, secret)
    assert not _verify(msg, sig, "other-secret")


def test_create_and_decode_token_default_ttl():
    secret = "unit-test-secret"
    # 临时设 Settings — 通过 monkeypatch
    import app.middleware.auth as auth_mod
    from unittest.mock import patch

    class _FakeSettings:
        auth_enabled = True
        auth_jwt_secret = secret
        auth_token_ttl_minutes = 1

    with patch.object(auth_mod, "get_settings", return_value=_FakeSettings()):
        tok = create_token("admin")
        payload = decode_token(tok)
        assert payload["sub"] == "admin"
        assert "exp" in payload
        assert payload["exp"] > payload["iat"]


def test_create_token_with_extra_claims():
    secret = "s3cret"
    from unittest.mock import patch
    import app.middleware.auth as auth_mod

    class _FakeSettings:
        auth_enabled = True
        auth_jwt_secret = secret
        auth_token_ttl_minutes = 1

    with patch.object(auth_mod, "get_settings", return_value=_FakeSettings()):
        tok = create_token("alice", extra={"role": "admin"})
        payload = decode_token(tok)
        assert payload["role"] == "admin"


def test_expired_token_rejected():
    """手工构造一个过期 token → 必须 401."""
    import base64, json, time
    secret = "s3cret"
    from unittest.mock import patch
    import app.middleware.auth as auth_mod

    class _FakeSettings:
        auth_enabled = True
        auth_jwt_secret = secret
        auth_token_ttl_minutes = 1

    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": "eve", "iat": now - 3600, "exp": now - 60}  # 早就过期
    def enc(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
    h = enc(json.dumps(header, separators=(",", ":")).encode())
    p = enc(json.dumps(payload, separators=(",", ":")).encode())
    sig = enc(_sign(f"{h}.{p}".encode(), secret))
    tok = f"{h}.{p}.{sig}"

    with patch.object(auth_mod, "get_settings", return_value=_FakeSettings()):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ei:
            decode_token(tok)
        assert ei.value.status_code == 401
        assert "expired" in ei.value.detail.lower()


def test_bad_signature_rejected():
    secret = "real-secret"
    from unittest.mock import patch
    import app.middleware.auth as auth_mod

    class _FakeSettings:
        auth_enabled = True
        auth_jwt_secret = secret
        auth_token_ttl_minutes = 1

    with patch.object(auth_mod, "get_settings", return_value=_FakeSettings()):
        tok = create_token("admin")
        # 把 sig 改一位
        parts = tok.split(".")
        parts[2] = "a" + parts[2][1:]
        bad = ".".join(parts)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ei:
            decode_token(bad)
        assert ei.value.status_code == 401


def test_bad_format_rejected():
    secret = "s3cret"
    from unittest.mock import patch
    import app.middleware.auth as auth_mod

    class _FakeSettings:
        auth_enabled = True
        auth_jwt_secret = secret
        auth_token_ttl_minutes = 1

    with patch.object(auth_mod, "get_settings", return_value=_FakeSettings()):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ei:
            decode_token("only.two")
        assert ei.value.status_code == 401


def test_require_auth_disabled_passthrough():
    """auth_enabled=False — 直接放行，返回 anonymous."""
    from unittest.mock import patch
    import app.middleware.auth as auth_mod

    class _FakeSettings:
        auth_enabled = False
        auth_jwt_secret = ""
        auth_token_ttl_minutes = 60

    with patch.object(auth_mod, "get_settings", return_value=_FakeSettings()):
        result = require_auth(authorization=None)
        assert result["sub"] == "anonymous"
        assert result["auth_enabled"] is False


def test_require_auth_enabled_no_header_401():
    from unittest.mock import patch
    import app.middleware.auth as auth_mod

    class _FakeSettings:
        auth_enabled = True
        auth_jwt_secret = "s3cret"
        auth_token_ttl_minutes = 60

    with patch.object(auth_mod, "get_settings", return_value=_FakeSettings()):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ei:
            require_auth(authorization=None)
        assert ei.value.status_code == 401


def test_auth_startup_check_rejects_missing_secret():
    from unittest.mock import patch
    import app.middleware.auth as auth_mod

    class _FakeSettings:
        auth_enabled = True
        auth_jwt_secret = ""  # ❌ 空

    with patch.object(auth_mod, "get_settings", return_value=_FakeSettings()):
        with pytest.raises(RuntimeError):
            auth_startup_check()


def test_auth_startup_check_passes_when_disabled():
    from unittest.mock import patch
    import app.middleware.auth as auth_mod

    class _FakeSettings:
        auth_enabled = False
        auth_jwt_secret = ""

    with patch.object(auth_mod, "get_settings", return_value=_FakeSettings()):
        # 不抛异常
        auth_startup_check()


def test_auth_startup_check_passes_when_enabled_with_secret():
    from unittest.mock import patch
    import app.middleware.auth as auth_mod

    class _FakeSettings:
        auth_enabled = True
        auth_jwt_secret = "not-empty"

    with patch.object(auth_mod, "get_settings", return_value=_FakeSettings()):
        auth_startup_check()
