"""MetricsStore — persist / restore registry snapshots in SQLite.

Phase 7 的 observability registry 是纯进程内的，进程重启归零。
Phase 10 加一个轻量 SQLite 快照层：

- shutdown 时自动 dump 一次（默认）。
- 可配置定时快照（``metrics_snapshot_interval_minutes``, 默认 0 = 仅 shutdown）。
- 启动时可恢复最近一次快照到注册表（``restore_on_startup``）。
- 存储内容就是 ``Registry.to_overview()`` 的 JSON blob — 不单独建表跟踪
  每个 metric；Registry 已经是 authoritative source，这里只做持久化壳。

零新依赖 — 复用 SQLAlchemy aiosqlite。
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text

from app.core.database import get_session_factory

logger = logging.getLogger(__name__)

_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS metrics_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        captured_at TEXT NOT NULL,
        payload TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'shutdown',
        note TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_metrics_snapshots_captured_at
        ON metrics_snapshots(captured_at)
    """,
]


class MetricsStore:
    """Async-friendly wrapper — creates its own session inside each method."""

    _instance: Optional["MetricsStore"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._factory = get_session_factory()
        self._last_dump_at: float = 0.0
        self._timer: Optional[threading.Timer] = None
        self._timer_interval: int = 0
        self._timer_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "MetricsStore":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ---- schema ----

    async def init_schema(self) -> None:
        from app.core.database import get_engine
        async with get_engine().begin() as conn:
            for stmt in _SCHEMA_STATEMENTS:
                await conn.execute(text(stmt))

    # ---- dump ----

    async def dump(
        self,
        payload: Dict[str, Any],
        *,
        kind: str = "shutdown",
        note: Optional[str] = None,
        snapshot_id: Optional[str] = None,
    ) -> str:
        """Save one snapshot. Returns the snapshot_id used."""
        from app.domain.common import _new_id  # reuse existing id factory

        sid = snapshot_id or _new_id("snap")
        captured_at = datetime.now(timezone.utc).isoformat()
        async with self._factory() as session:
            await session.execute(
                text(
                    "INSERT INTO metrics_snapshots "
                    "(snapshot_id, captured_at, payload, kind, note) "
                    "VALUES (:s, :c, :p, :k, :n)"
                ),
                {"s": sid, "c": captured_at,
                 "p": json.dumps(payload, default=str, ensure_ascii=False),
                 "k": kind, "n": note or ""},
            )
            await session.commit()
        self._last_dump_at = time.perf_counter()
        logger.info("[MetricsStore] snapshot saved: id=%s kind=%s", sid, kind)
        return sid

    # ---- load ----

    async def latest(self, *, limit: int = 1) -> List[Dict[str, Any]]:
        """Return the most recent N snapshots (most recent first)."""
        async with self._factory() as session:
            rows = (await session.execute(
                text(
                    "SELECT snapshot_id, captured_at, payload, kind, note "
                    "FROM metrics_snapshots "
                    "ORDER BY captured_at DESC LIMIT :n"
                ).bindparams(n=limit)
            )).fetchall()
            out = []
            for r in rows:
                out.append({
                    "snapshot_id": r[0],
                    "captured_at": r[1],
                    "payload": json.loads(r[2]) if r[2] else {},
                    "kind": r[3],
                    "note": r[4],
                })
            return out

    async def latest_overview(self) -> Optional[Dict[str, Any]]:
        latest = await self.latest(limit=1)
        if not latest:
            return None
        return latest[0]["payload"]

    # ---- purge old snapshots (retention days) ----

    async def purge(self, *, retention_days: int = 30) -> int:
        """Delete snapshots older than retention_days. Returns deleted count."""
        async with self._factory() as session:
            r = await session.execute(
                text(
                    "DELETE FROM metrics_snapshots "
                    "WHERE captured_at < datetime('now', :offset)"
                ).bindparams(offset=f"-{retention_days} days")
            )
            await session.commit()
            return int(r.rowcount or 0)

    # ---- background timer ----

    def start_timer(self, interval_minutes: int) -> None:
        if interval_minutes <= 0:
            return
        with self._timer_lock:
            self.stop_timer()
            self._timer_interval = interval_minutes

            def _tick() -> None:
                try:
                    from app.core.observability import get_registry
                    from app.services.feedback import feedback_summary
                    # Schedule async work — simplest: run in asyncio loop
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self.dump(feedback_summary(), kind="scheduled"))
                    else:
                        asyncio.run(self.dump(feedback_summary(), kind="scheduled"))
                except Exception as e:
                    logger.warning("[MetricsStore] scheduled dump failed: %s", e)
                finally:
                    with self._timer_lock:
                        if self._timer is not None:
                            self._timer = threading.Timer(
                                interval_minutes * 60.0, _tick
                            )
                            self._timer.daemon = True
                            self._timer.start()

            self._timer = threading.Timer(interval_minutes * 60.0, _tick)
            self._timer.daemon = True
            self._timer.start()

    def stop_timer(self) -> None:
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
