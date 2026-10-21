"""GET /health — liveness + dependency probe."""
from __future__ import annotations

import os
import platform
from typing import Any, Dict

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> Dict[str, Any]:
    """Return a structured health snapshot.

    This endpoint MUST stay cheap — no DB calls, no LLM probes.
    Dependency liveness probes belong in a later endpoint.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pid": os.getpid(),
    }
