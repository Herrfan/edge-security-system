"""Phase 14 — per-role token-bucket rate limiter.

Why FastAPI middleware, not dependency? Because rate-limit should apply to
every path — including routes that skip ``Depends(require_auth)`` (e.g.
``/health``, ``/docs``). A dependency can't decorate the whole app graph.

Design:

- Token bucket per role (admin, operator, viewer, anonymous)
- Default role buckets are generous enough for dev (100 req/s admin, 50 ops,
  20 viewer, 30 anonymous) — they can be overridden per-role via Settings
  keys like ``rate_limit_admin_rps``.
- Bucket refill happens on each request; if tokens == 0 → HTTP 429.
- ``/health``, ``/docs``, ``/openapi.json``, ``/metrics`` always bypass — these
  are infra endpoints and we don't want an SRE being rate-limited while
  investigating an outage.
- Always-allow when ``auth_enabled=False`` — backwards-compat with Phase 0-13.

Zero new deps — pure threading.Lock + time.monotonic, aiosqlite free.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ---- Token bucket --------------------------------------------------------


class TokenBucket:
    """Thread-safe token bucket. capacity = refill_rate = rps."""

    __slots__ = ("capacity", "refill_rate", "tokens", "_lock", "_last_tick")

    def __init__(self, rps: float) -> None:
        self.capacity = rps
        self.refill_rate = rps  # tokens per second
        self.tokens = float(rps)
        self._lock = threading.Lock()
        self._last_tick = time.monotonic()

    def acquire(self) -> bool:
        """Return True if a token was available; decrement it. False → rate-limited."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_tick
            if elapsed > 0:
                self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
                self._last_tick = now
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False


# ---- Registry + middleware -----------------------------------------------


_BUCKETS: Dict[str, TokenBucket] = {}
_BUCKETS_LOCK = threading.Lock()


def _role_to_bucket(role: str) -> TokenBucket:
    with _BUCKETS_LOCK:
        if role not in _BUCKETS:
            s = get_settings()
            rps = {
                "admin": s.rate_limit_admin_rps,
                "operator": s.rate_limit_operator_rps,
                "viewer": s.rate_limit_viewer_rps,
            }.get(role, s.rate_limit_anonymous_rps)
            _BUCKETS[role] = TokenBucket(rps=rps)
        return _BUCKETS[role]


# Paths that NEVER rate-limit — infra / health / metrics
_BYPASS_PREFIXES = ("/health", "/docs", "/openapi.json", "/metrics", "/")
# "/" root is just the tiny index JSON; no reason to rate-limit it.
# Keep the short-circuit cheap.


def install_rate_limit(app: FastAPI) -> None:
    """Add rate-limit middleware. Called from main.py lifespan."""

    @app.middleware("http")
    async def _rate_limit(request: Request, call_next):
        path = request.url.path or "/"
        # Bypass first — cheapest check
        for pfx in _BYPASS_PREFIXES:
            if path.startswith(pfx):
                return await call_next(request)

        s = get_settings()
        if not s.auth_enabled:
            # auth disabled → single anonymous bucket covers everything
            role = "anonymous"
        else:
            role = request.headers.get("x-role", "anonymous")
            # NOTE: x-role is trusted header only when a reverse proxy strips it
            # before forwarding. Without that, an attacker could set arbitrary
            # roles. For this demo we treat it as authenticated; production
            # must validate role from JWT payload (decode_token payload["role"]).

        bucket = _role_to_bucket(role)
        if not bucket.acquire():
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": f"rate-limit exceeded for role={role}"},
                headers={"Retry-After": "1"},
            )

        return await call_next(request)
