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


def create_token(subject: str, *, extra: Optional[Dict[str, Any]] = None) -> str:
    """生成一个 HS256 token。默认 ttl 从 Settings 取。"""
    s = get_settings()
    if not s.auth_jwt_secret:
        raise RuntimeError("auth_jwt_secret is empty — cannot create tokens")
    header = {"alg": "HS256", "typ": "JWT"}
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.auth_token_ttl_minutes)).timestamp()),
    }
    if extra:
        payload.update(extra)

    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64url_encode(_sign(f"{h}.{p}".encode(), s.auth_jwt_secret))
    return f"{h}.{p}.{sig}"


def decode_token(token: str) -> Dict[str, Any]:
    """验证签名 + 过期时间，返回 payload。HTTPException on failure."""
    s = get_settings()
    if not s.auth_jwt_secret:
        raise HTTPException(status_code=500, detail="auth_jwt_secret not configured")

    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="invalid token format")

    h_b64, p_b64, sig_b64 = parts
    msg = f"{h_b64}.{p_b64}".encode()

    try:
        sig = _b64url_decode(sig_b64)
        if not _verify(msg, sig, s.auth_jwt_secret):
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

    return payload


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


# ---- 生命周期检查 ----------------------------------------------------------


def auth_startup_check() -> None:
    """Lifespan 里调用：如果 auth_enabled=True 但 auth_jwt_secret 为空 → 立即报错，
    避免部署了一个假装鉴权但实际上全放行的系统。"""
    s = get_settings()
    if s.auth_enabled and not s.auth_jwt_secret:
        raise RuntimeError(
            "auth_enabled=True 但 auth_jwt_secret 为空 — 请在 .env 或 Settings 配置 secret"
        )
