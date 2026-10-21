"""FastAPI application entrypoint.

Wires configuration, logging, error handling, and route registration.
Start with:  uvicorn app.main:app
"""
from __future__ import annotations

import asyncio
import logging
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
from app.middleware.auth import auth_startup_check
from app.services.feedback import feedback_summary, mark_info_gauges
from app.stores.metrics_store import MetricsStore

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(api: FastAPI):
    """Startup + shutdown hooks.

    Phase 10: 额外完成 MetricsStore schema 初始化 / auth 生命周期检查 / shutdown 自动 dump。
    """
    await init_db()

    # ---- Phase 10 auth startup guard ----
    auth_startup_check()

    # ---- Phase 10 metrics persistence ----
    store = MetricsStore.instance()
    await store.init_schema()
    interval = get_settings().metrics_snapshot_interval_minutes
    if interval > 0:
        store.start_timer(interval)
        _logger.info("[MetricsStore] scheduled snapshots every %d min", interval)

    mark_info_gauges()
    _logger.info("Edge security system startup complete")

    try:
        yield
    finally:
        # shutdown hook
        store.stop_timer()
        if get_settings().metrics_persist_enabled:
            try:
                await store.dump(feedback_summary(), kind="shutdown", note="app shutdown")
            except Exception as e:
                _logger.warning("[MetricsStore] shutdown dump failed: %s", e)
        # Phase 12: VictoriaMetrics remote-write
        if get_settings().vm_remote_write_url:
            try:
                from app.adapters.remote_write.victoria import push_latest
                await push_latest()
            except Exception as e:
                _logger.warning("[VM remote-write] shutdown push failed: %s", e)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.app_log_level)

    api = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Edge network security situational awareness prototype — Phase 10. "
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
