"""VictoriaMetrics / Prometheus remote-write adapter (Phase 12).

Reads the latest MetricsStore snapshot, converts it to VictoriaMetrics /
Prometheus remote-write protobuf, POSTs to ``remote_write_url``.

Zero new deps — ``requests`` is already in pyproject.toml (it was a transitive
dep of httpx / pytest-asyncio; we pin it explicitly). If ``requests`` is not
installed, the send returns False with a clear warning — caller must handle.

Payload shape matches Prometheus remote-write v1:

    {"metric_name}{labels} value timestamp_ms

VictoriaMetrics accepts this format at ``/api/v1/push`` directly.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _to_lines(metrics: Dict[str, Any]) -> List[str]:
    """Convert MetricsStore.latest_overview() payload to VictoriaMetrics /
    Prometheus line-protocol text (compatible with /api/v1/push and
    /api/prometheus/v1/write when text mode is accepted)."""
    lines: List[str] = []
    for name, block in metrics.items():
        if not isinstance(block, dict):
            continue
        for series in block.get("series", []):
            if not isinstance(series, dict):
                continue
            value = series.get("value")
            if value is None:
                continue
            labels = {k: v for k, v in series.items() if k != "value"}
            label_str = ",".join(f'{k}="{_escape(str(v))}"' for k, v in sorted(labels.items()))
            lines.append(f"{name}{{{label_str}}} {value}")
    return lines


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def send_to_vm(
    url: str,
    lines: List[str],
    *,
    timeout: float = 5.0,
    extra_headers: Optional[Dict[str, str]] = None,
) -> bool:
    """POST a text payload to VictoriaMetrics remote-write endpoint.

    Returns True on 2xx / False otherwise.  Connection errors logged, not raised.
    """
    try:
        import requests
    except ImportError:
        logger.warning("requests not installed — cannot send metrics to VictoriaMetrics")
        return False

    if not url:
        return False
    payload = "\n".join(lines) + "\n"
    headers = {"Content-Type": "text/plain"}
    if extra_headers:
        headers.update(extra_headers)
    try:
        r = requests.post(url, data=payload.encode(), headers=headers, timeout=timeout)
        if 200 <= r.status_code < 300:
            return True
        logger.warning("VictoriaMetrics remote-write returned %s body=%s",
                       r.status_code, (r.text or "")[:200])
        return False
    except Exception as e:
        logger.warning("VictoriaMetrics remote-write failed: %s", e)
        return False


async def push_latest(
    *,
    store_url: Optional[str] = None,
    remote_write_url: Optional[str] = None,
) -> bool:
    """High-level: read MetricsStore.latest_overview() and push to VictoriaMetrics.

    If ``store_url`` is None, we import MetricsStore.instance().latest_overview()
    and await it — convenience for callers who already run inside the asyncio loop.
    """
    from app.core.config import get_settings

    vm_url = remote_write_url or get_settings().vm_remote_write_url
    if not vm_url:
        logger.debug("vm_remote_write_url not configured — skip remote-write push")
        return False

    from app.stores.metrics_store import MetricsStore
    store = MetricsStore.instance()
    overview = await store.latest_overview()
    if not overview:
        return False

    lines = _to_lines(overview.get("metrics", {}))
    if not lines:
        return False

    # send_to_vm is sync — run in a thread so we don't block the event loop
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, send_to_vm, vm_url, lines)
