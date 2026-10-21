"""Phase 14 — optional mutual TLS middleware.

Design:

- Default **off** (`mtls_enabled=False`). When off, FastAPI runs plain HTTP.
- When on: uvicorn is told to bind SSL (keyfile / certfile), and we do a
  lightweight cert-subject match inside the middleware.
- The middleware checks request.client-cert via ``request.state.client_cert``
  (uvicorn needs ``ssl_keyfile`` + ``ssl_certfile`` AND ``--ssl-verify-clients``,
  but passing verify=False is also an option if we want to gate on subject
  match only — see ``mtls_require_subject``).

Why FastAPI middleware AND uvicorn flags? Because SSL termination has to happen
at the ASGI server (uvicorn); FastAPI middleware can only check the decrypted
cert that uvicorn made available on the request object. You can't do TLS at
the ASGI layer — it's a transport concern.

Zero new deps — stdlib ssl is built into Python.
"""
from __future__ import annotations

import logging
import ssl
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def install_mtls(app: FastAPI) -> None:
    """Add mTLS middleware. Lifespan only — just wires the check.

    Actual SSL wiring happens in run_gunicorn.sh / uvicorn command via
    ssl_keyfile / ssl_certfile CLI args.
    """
    from app.core.config import get_settings

    @app.middleware("http")
    async def _mtls(request: Request, call_next):
        s = get_settings()
        if not s.mtls_enabled:
            return await call_next(request)

        cert = getattr(request.state, "client_cert", None)
        if cert is None:
            # uvicorn was NOT started with client-cert verification → refuse
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "client certificate required but not presented"},
            )

        expected_subject = s.mtls_require_subject.strip()
        if expected_subject and expected_subject not in _cert_subject(cert):
            logger.warning("[mTLS] subject mismatch: expected=%s got=%s",
                           expected_subject, _cert_subject(cert))
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "client certificate subject not trusted"},
            )

        return await call_next(request)


def _cert_subject(cert) -> str:
    """uvicorn exposes cert as dict {subject: [(..., 'CN'), ...]}. Parse it."""
    try:
        subj = cert.get("subject", [])
        parts = []
        for tup in subj:
            if isinstance(tup, tuple) and len(tup) == 2:
                parts.append(f"{tup[1]}={tup[0]}")
        return ",".join(parts)
    except Exception:
        return ""
