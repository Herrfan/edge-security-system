"""Phase 7 — metrics endpoints.

Three routes:

* ``GET /metrics``       — Prometheus exposition text. Scrape-ready.
* ``GET /metrics/overview`` — compact JSON snapshot with version trace.
* ``GET /metrics/export?format=csv`` — CSV export for offline analysis.
"""
from __future__ import annotations

import csv
import io
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.core.observability import get_registry
from app.services.feedback import feedback_summary

router = APIRouter(prefix="/api/v1", tags=["metrics", "observability"])


@router.get("/metrics", response_class=PlainTextResponse)
def metrics_prometheus() -> str:
    """Render the in-process registry as Prometheus text.

    A real Prometheus server can scrape this endpoint directly — the format
    matches the OpenMetrics exposition spec used by the official client.
    """
    return get_registry().exposition_text()


@router.get("/metrics/overview")
def metrics_overview() -> dict:
    """Compact JSON snapshot including version + config trace.

    Every metric row can be attributed to a concrete LLM model, embedding
    backend, and code revision via the ``config`` block — requirement from
    任务书 §7 "每条结果能追溯到模型、知识库和配置版本".
    """
    return feedback_summary()


@router.get("/metrics/export")
def metrics_export(format: str = "csv") -> StreamingResponse:
    """Export current metrics as CSV. Useful for offline analysis.

    Args:
        format: Only ``csv`` supported today. Future-proof — 400 on unknowns.
    """
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail=f"format={format!r} not supported — use csv")

    reg = get_registry()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["metric", "kind", "labels", "value", "le"])

    from app.core.observability import Histogram as _Histogram
    for m in reg.all():
        kind = type(m).__name__
        collected = m._collect()
        if not collected:
            writer.writerow([m.name, kind, "", "", ""])
            continue
        is_hist = isinstance(m, _Histogram)
        for row in collected:
            if is_hist:
                suffix, lbls, val, le = row  # type: ignore[misc]
                d = {k: v for k, v in lbls}
                writer.writerow([suffix, kind, _dict_str(d), val, le])
            else:
                lbls, val = row
                d = {k: v for k, v in lbls}
                writer.writerow([m.name, kind, _dict_str(d), val, ""])

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="metrics_export.csv"'},
    )


def _dict_str(d: dict) -> str:
    if not d:
        return ""
    return ",".join(f"{k}={v}" for k, v in sorted(d.items()))
