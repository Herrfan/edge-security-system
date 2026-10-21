"""Unified error response contract.

Every HTTP error returned by the application MUST use :func:`error_response`
or raise :class:`AppError`. This guarantees that the client always receives
a predictable JSON envelope regardless of the failure mode.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ErrorEnvelope(BaseModel):
    """Canonical error response body."""

    code: str = Field(..., description="Machine-readable error code.")
    message: str = Field(..., description="Human-readable description.")
    data: Optional[Any] = Field(default=None, description="Optional structured detail.")
    request_id: Optional[str] = Field(default=None, description="Trace / request identifier.")


# ---- Error code registry ---------------------------------------------------
# Keep the list explicit so new codes are reviewed before landing.
class ErrorCode:
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"

    UNAUTHORIZED_TARGET = "UNAUTHORIZED_TARGET"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    EXPIRED = "EXPIRED"

    LLM_PROVIDER_ERROR = "LLM_PROVIDER_ERROR"
    RETRIEVAL_DEGRADED = "RETRIEVAL_DEGRADED"
    FEATURE_SCHEMA_MISMATCH = "FEATURE_SCHEMA_MISMATCH"

    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppError(Exception):
    """Raise from service code to get a uniform error response out the door."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int = 400,
        data: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data


def error_response(
    code: str,
    message: str,
    *,
    http_status: int = 400,
    data: Optional[Any] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Build a uniform error JSON response."""
    payload = ErrorEnvelope(
        code=code,
        message=message,
        data=data,
        request_id=request_id,
    ).model_dump()
    return JSONResponse(status_code=http_status, content=payload)


def app_error_handler(exc: AppError) -> JSONResponse:
    """FastAPI dependency — register as an exception handler."""
    return error_response(
        code=exc.code,
        message=exc.message,
        http_status=exc.http_status,
        data=exc.data,
    )


def validation_error_handler(request, exc) -> JSONResponse:
    """Map FastAPI's default RequestValidationError into our envelope (best-effort).

    RequestValidationError carries `.errors()` and an HTTP 422 status, but it
    is NOT an HTTPException — it has no `.status_code` attribute. FastAPI
    passes us (request, exc); we duck-type the exception.
    """
    status_code = getattr(exc, "status_code", 422)
    if hasattr(exc, "errors"):
        try:
            detail = exc.errors()
        except Exception:
            detail = str(getattr(exc, "detail", exc))
    else:
        detail = getattr(exc, "detail", str(exc))
    message = f"Validation failed: {detail}"
    return error_response(
        code=ErrorCode.VALIDATION_ERROR,
        message=message,
        http_status=int(status_code) if isinstance(status_code, int) else 422,
        data=detail if not isinstance(detail, str) else None,
    )
