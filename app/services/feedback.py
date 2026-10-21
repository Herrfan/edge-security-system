"""Feedback + observability helpers.

Ties the primitive metrics declared in :mod:`app.core.observability` to the
application's real lifecycle events. No business logic — pure plumbing that
services and API routes call in addition to existing work.

Key responsibilities:

1. ``mark_info_gauges()`` — run at startup to stamp the static config/version
   labels into the :data:`edgy_info` Gauge so every scrape carries provenance.
2. ``snapshot_knowledge_gauges()`` — called after ``knowledge/sync`` to record
   chunk / document counts for the overview dashboard.
3. ``try_collect_system_metrics()`` — best-effort CPU / RSS sampling. If psutil
   is not installed, the two gauges simply stay at ``unavailable`` — we never
   fabricate fake numbers (任务书 §7 验收要求).
4. ``feedback_summary()`` — high-level convenience that builds the JSON
   report the ``/metrics/overview`` route returns (includes version +
   config trace so every result is traceable).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.core.observability import (
    INFO_GAUGE,
    KNOWLEDGE_CHUNKS_TOTAL,
    KNOWLEDGE_DOCUMENTS_TOTAL,
    PROCESS_CPU_PERCENT,
    PROCESS_RSS_BYTES,
    get_registry,
)

logger = logging.getLogger(__name__)

# One-shot flag so mark_info_gauges is safe to call from lifespan and from
# tests that don't hit lifespan.
_info_sealed = False


def mark_info_gauges() -> None:
    """Stamp the ``edgy_info`` Gauge with the currently loaded settings.

    Safe to call multiple times — the Gauge is idempotent. Values are taken
    from :class:`app.core.config.Settings` so they match what actually
    started (no drift).
    """
    global _info_sealed
    s = get_settings()
    INFO_GAUGE.set(
        1.0,
        labels={
            "app_name": s.app_name,
            "app_version": s.app_version,
            "llm_model": s.llm_model,
            "embedding_model": s.embedding_model,
            "vector_backend": s.vector_backend,
        },
    )
    _info_sealed = True


def snapshot_knowledge_gauges(chunks: int, documents: int, *, backend: str = "sqlite_vec") -> None:
    """After a knowledge sync, record the resulting counts so the overview
    can show current KB size. Called from ``knowledge/sync`` route.
    """
    KNOWLEDGE_CHUNKS_TOTAL.set(float(chunks), labels={"backend": backend})
    KNOWLEDGE_DOCUMENTS_TOTAL.set(float(documents), labels={"backend": backend})


def try_collect_system_metrics() -> Dict[str, Optional[float]]:
    """Best-effort sample of process CPU + resident memory.

    Returns a dict of ``{metric_name: value_or_None}``. Callers don't need to
    know whether psutil is present; they just pass the dict through and the
    Gauge stays unavailable if the value is ``None``.
    """
    out: Dict[str, Optional[float]] = {"cpu_percent": None, "rss_bytes": None}
    try:
        import psutil  # type: ignore[import-not-found]
    except ImportError:
        logger.debug("psutil not installed — system metrics remain unavailable")
        return out
    try:
        p = psutil.Process()
        out["cpu_percent"] = float(p.cpu_percent(interval=None) or 0.0)
        out["rss_bytes"] = float(p.memory_info().rss)
        PROCESS_CPU_PERCENT.set(out["cpu_percent"])
        PROCESS_RSS_BYTES.set(out["rss_bytes"])
    except Exception as e:
        logger.warning("psutil sample failed: %s", e)
    return out


def feedback_summary() -> Dict[str, Any]:
    """Build the JSON returned by ``GET /metrics/overview``.

    Wraps the registry snapshot with the full version/config trace so
    every metric row can be attributed to a concrete software revision and
    model/vector backend combination (任务书 §7 验收: 每条结果能追溯到模型、
    知识库和配置版本).
    """
    s = get_settings()
    system = try_collect_system_metrics()
    return {
        "generated_at": _now_iso(),
        "config": {
            "app_name": s.app_name,
            "app_version": s.app_version,
            "llm_model": s.llm_model,
            "llm_provider": s.llm_provider,
            "embedding_model": s.embedding_model,
            "vector_backend": s.vector_backend,
            "retrieval_mode": s.retrieval_mode,
            "allow_real_execution": s.allow_real_execution,
            "default_execution_mode": s.default_execution_mode,
        },
        "system": {
            "cpu_percent": system["cpu_percent"],
            "rss_bytes": system["rss_bytes"],
            "cpu_status": "ok" if system["cpu_percent"] is not None else "unavailable",
            "rss_status": "ok" if system["rss_bytes"] is not None else "unavailable",
        },
        "metrics": get_registry().to_overview(),
    }


# ---- helpers -----------------------------------------------------------------

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
