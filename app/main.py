"""FastAPI application entrypoint.

Wires configuration, logging, error handling, and route registration.
Start with:  uvicorn app.main:app
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api.routes.detection import router as detection_router
from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.policy import router as policy_router
from app.api.routes.retrieval import router as retrieval_router
from app.core.config import get_settings
from app.core.database import init_db
from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.core.logging import setup_logging
from app.services.feedback import mark_info_gauges


@asynccontextmanager
async def lifespan(api: FastAPI):
    """Startup + shutdown hooks. Uses lifespan to avoid the on_event deprecation."""
    await init_db()
    mark_info_gauges()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.app_log_level)

    api = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Edge network security situational awareness prototype — Phase 3. "
            "Business functionality (ingestion, detection, retrieval, RAG, policy, execution) "
            "lands progressively in later phases. All actions default to dry-run."
        ),
        lifespan=lifespan,
    )

    # Exception handlers — every error goes through our envelope
    api.add_exception_handler(AppError, app_error_handler)
    api.add_exception_handler(RequestValidationError, validation_error_handler)

    # Wire routes
    api.include_router(health_router)
    api.include_router(detection_router)
    api.include_router(events_router)
    api.include_router(retrieval_router)
    api.include_router(policy_router)
    api.include_router(metrics_router)

    @api.get("/", include_in_schema=False)
    def _root() -> dict:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
        }

    return api


app = create_app()
