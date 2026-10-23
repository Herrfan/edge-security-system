"""FastAPI application entrypoint.

All API is under ``/api/v1/*``. Static UI lives at ``/ui`` (served from
``static/index.html`` via Starlette StaticFiles — zero frontend deps, no build
step). FastAPI docs remain at ``/docs``.

Start with:  uvicorn app.main:app
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

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
            "Edge network security situational awareness prototype — Phase 14. "
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

    # --- Phase 14: middlewares (BEFORE the root route so they see everything) ---
    from app.middleware.rate_limit import install_rate_limit
    from app.middleware.mtls import install_mtls
    install_rate_limit(api)
    install_mtls(api)

    @api.get("/", include_in_schema=False)
    def _root() -> dict:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "ui": "/ui",
        }

    # --- Phase 15 → F1: Vue SPA mount ---
    # Priority 1: frontend/dist (built by `npm run build` in frontend/)
    # Priority 2: static/ fallback (legacy Phase 15 zero-dep SPA, still works)
    repo_root = Path(__file__).resolve().parents[1]
    frontend_dist = repo_root / "frontend" / "dist"
    legacy_static = repo_root / "static"

    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        api.mount("/static", StaticFiles(directory=str(frontend_dist)), name="frontend-dist")

        @api.get("/ui", include_in_schema=False)
        async def _ui() -> FileResponse:
            return FileResponse(str(frontend_dist / "index.html"))

        # SPA fallback: any non-/api/v1/*, non-/docs, non-/openapi.json, non-/health, non-/metrics
        # path should serve index.html so Vue Router (hash history) can resolve it client-side.
        @api.get("/{full_path:path}", include_in_schema=False)
        async def _spa_fallback(full_path: str) -> FileResponse:
            # Let explicit API/docs/health/metrics routes take precedence — Starlette handles 404 first
            # before this fallback fires, but we still guard on extension to avoid masking static assets.
            if full_path and "." in full_path.split("/")[-1]:
                # Has file extension (e.g. .js, .css, .svg) — don't try to serve index.html
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Not Found")
            return FileResponse(str(frontend_dist / "index.html"))

    elif legacy_static.exists() and (legacy_static / "index.html").exists():
        api.mount("/static", StaticFiles(directory=str(legacy_static)), name="static-legacy")

        @api.get("/ui", include_in_schema=False)
        async def _ui() -> FileResponse:
            return FileResponse(str(legacy_static / "index.html"))

    else:
        _logger.warning(
            "No frontend found — neither frontend/dist/ nor static/ exists. "
            "Run `cd frontend && npm run build` or keep static/index.html."
        )

    return api


app = create_app()
