"""API 鉴权骨架 — 零新依赖（用 pyproject.toml 已有的 cryptography 实现 HS256 JWT）。

Phase 10 增量。Phase 9 红队测出来的 "API 无 auth" 风险（T-3/T-5 间接）。

设计：

- 默认 ``auth_enabled=False`` — 不影响 Phase 0-9 全链路
- 启用后：每个受保护端点必须带 ``Authorization: Bearer <token>``
- Token 是 base64url(header).base64url(payload).base64url(signature) 三部分
- Signature 用 HMAC-SHA256（cryptography hazmat）
- Payload 只含 ``sub`` + ``exp``，不引 PyJWT
- 装饰器层实现：``Depends(require_auth)`` + ``@app.on_event("startup")`` 校验 secret

不做什么:
- 不做 RBAC（只有 pass/fail）
- 不做 token 黑名单（进程重启就全清）
- 不做刷新 token

生产部署前需要在此基础上扩展。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    # add padding back
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode("ascii"))


def _sign(msg: bytes, secret: str) -> bytes:
    """HMAC-SHA256 using stdlib only — no new dependency."""
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()


def _verify(msg: bytes, sig: bytes, secret: str) -> bool:
    return hmac.compare_digest(sig, _sign(msg, secret))


# ---- token API ------------------------------------------------------------


def create_token(subject: str, *, extra: Optional[Dict[str, Any]] = None,
                 token_type: str = "access") -> str:
    """生成一个 HS256 token。默认 ttl 从 Settings 取。

    ``token_type="refresh"`` 时 ttl 自动 * 7。
    """
    s = get_settings()
    if not s.auth_jwt_secret:
        raise RuntimeError("auth_jwt_secret is empty — cannot create tokens")
    from hashlib import sha256
    from app.domain.common import _new_id
    header = {"alg": "HS256", "typ": "JWT"}
    now = datetime.now(timezone.utc)
    ttl_minutes = s.auth_token_ttl_minutes * 7 if token_type == "refresh" else s.auth_token_ttl_minutes
    jti = _new_id("jti")
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
        "jti": jti,
        "type": token_type,
    }
    if extra:
        payload.update(extra)

    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64url_encode(_sign(f"{h}.{p}".encode(), s.auth_jwt_secret))
    return f"{h}.{p}.{sig}"


def create_refresh_token(subject: str, *, extra: Optional[Dict[str, Any]] = None) -> str:
    """Long-lived refresh token (ttl = access ttl * 7)."""
    return create_token(subject, extra=extra, token_type="refresh")


def decode_token(token: str) -> Dict[str, Any]:
    """验证签名 + 过期时间 + 黑名单检查，返回 payload。HTTPException on failure."""
    s = get_settings()
    if not s.auth_jwt_secret:
        raise HTTPException(status_code=500, detail="auth_jwt_secret not configured")

    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="invalid token format")

    h_b64, p_b64, sig_b64 = parts

    try:
        sig = _b64url_decode(sig_b64)
        if not _verify(f"{h_b64}.{p_b64}".encode(), sig, s.auth_jwt_secret):
            raise HTTPException(status_code=401, detail="token signature invalid")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"token signature error: {e}")

    try:
        payload = json.loads(_b64url_decode(p_b64))
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"token payload error: {e}")

    exp = payload.get("exp", 0)
    if exp and exp < int(time.time()):
        raise HTTPException(status_code=401, detail="token expired")

    # Phase 12: blacklist check
    jti = payload.get("jti")
    if jti and _is_blacklisted_sync(jti):
        raise HTTPException(status_code=401, detail="token revoked")

    return payload


# ---- Blacklist helpers (Phase 12) ------------------------------------------


def _is_blacklisted_sync(jti: str) -> bool:
    """同步黑名单查询：decode_token 是同步函数，用 sqlite3 直接开一个临时 connection。
    不走 SQLAlchemy async_sessionmaker，避免 sync/async context 混乱。"""
    try:
        from app.core.config import REPO_ROOT
        db_path = REPO_ROOT / "data" / "app.db"
        if not db_path.exists():
            return False
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM token_blacklist WHERE jti = ?", (jti,))
        hit = cur.fetchone() is not None
        conn.close()
        return hit
    except Exception as e:
        logger.warning("blacklist lookup failed: %s", e)
        return False


async def blacklist_token(jti: str, *, subject: str = "", reason: Optional[str] = None,
                          revoked_by: Optional[str] = None) -> None:
    """Add a jti to the blacklist table (async, SQLAlchemy)."""
    from hashlib import sha256
    from datetime import datetime, timezone
    from sqlalchemy import text
    from app.core.database import get_session_factory

    jti_hash = sha256(jti.encode()).hexdigest()
    now_iso = datetime.now(timezone.utc).isoformat()
    factory = get_session_factory()
    async with factory() as s:
        await s.execute(
            text(
                "INSERT OR REPLACE INTO token_blacklist "
                "(jti_hash, jti, subject, exp_at, revoked_at, reason, revoked_by) "
                "VALUES (:jh, :j, :sub, :exp, :rv, :r, :by)"
            ),
            {"jh": jti_hash, "j": jti, "sub": subject, "exp": None,
             "rv": now_iso, "r": reason or "", "by": revoked_by or ""},
        )
        await s.commit()


async def purge_expired_blacklist(*, retention_days: int = 7) -> int:
    """Delete blacklist rows older than ``retention_days``."""
    from sqlalchemy import text
    from app.core.database import get_session_factory
    factory = get_session_factory()
    async with factory() as s:
        r = await s.execute(
            text(
                "DELETE FROM token_blacklist WHERE revoked_at < datetime('now', :offset)"
            ).bindparams(offset=f"-{retention_days} days")
        )
        await s.commit()
        return int(r.rowcount or 0)


# ---- FastAPI dependency ---------------------------------------------------


def require_auth(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """FastAPI dependency。若 auth_enabled=False，直接返回 anonymous —
    让 Phase 0-9 全链路正常工作。启用后强制 Bearer token。"""
    s = get_settings()
    if not s.auth_enabled:
        return {"sub": "anonymous", "auth_enabled": False}  # 鉴权关闭时放行

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or malformed Authorization header",
        )
    token = authorization[len("Bearer "):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="empty token")
    return decode_token(token)


# ---- RBAC role constants ----

ROLE_ADMIN = "admin"          # full CRUD + execute
ROLE_OPERATOR = "operator"    # execute + validate + generate, no config
ROLE_VIEWER = "viewer"        # read-only (health + events + metrics + policies)

# Which roles can pass which FastAPI dependencies below
_ROLE_POLICY = {
    ROLE_ADMIN: {"/policy-proposal/execute", "/policy-proposal/generate",
                 "/policy-proposal/validate", "/policy-proposals"},
    ROLE_OPERATOR: {"/policy-proposal/execute", "/policy-proposal/generate",
                    "/policy-proposal/validate", "/policy-proposals"},
    ROLE_VIEWER: {"/policy-proposals"},
}

_ADMIN_ONLY = {"/metrics/overview", "/metrics/export", "/knowledge/sync", "/flows/seed-policy"}


def require_roles(*allowed: str):
    """FastAPI dependency factory — callers do ``Depends(require_roles("admin", "operator"))``.

    If auth_enabled=False → always pass through (Phase 0-9 behavior preserved).
    Otherwise checks the token payload's ``role`` claim.
    """
    from fastapi import HTTPException, status as _status

    def _check(payload: dict = Depends(require_auth)):
        s = get_settings()
        if not s.auth_enabled:
            return payload  # anonymous allowed
        role = payload.get("role", "viewer")
        if role not in allowed:
            raise HTTPException(
                status_code=_status.HTTP_403_FORBIDDEN,
                detail=f"role '{role}' not in allowed roles {list(allowed)}",
            )
        return payload

    return _check


def auth_startup_check() -> None:
    """Lifespan 里调用：如果 auth_enabled=True 但 auth_jwt_secret 为空 → 立即报错，
    避免部署了一个假装鉴权但实际上全放行的系统。"""
    s = get_settings()
    if s.auth_enabled and not s.auth_jwt_secret:
        raise RuntimeError(
            "auth_enabled=True 但 auth_jwt_secret 为空 — 请在 .env 或 Settings 配置 secret"
        )
