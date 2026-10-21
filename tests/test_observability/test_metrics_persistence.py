"""Phase 10 — MetricsStore 持久化测试。"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core.database import get_session_factory
from app.stores.metrics_store import MetricsStore


@pytest.mark.asyncio
async def test_init_schema_creates_table():
    store = MetricsStore.instance()
    await store.init_schema()
    factory = get_session_factory()
    async with factory() as s:
        r = (await s.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='metrics_snapshots'"
        ))).fetchone()
    assert r is not None, "metrics_snapshots 表必须被 init_schema 创建"


@pytest.mark.asyncio
async def test_dump_then_load():
    store = MetricsStore.instance()
    await store.init_schema()

    payload = {"metrics": {"edgy_info": {"status": "ok", "series": [{"app_name": "edge-security-system"}]}}}
    sid = await store.dump(payload, kind="shutdown", note="test dump")
    assert sid.startswith("snap_")

    latest = await store.latest(limit=1)
    assert len(latest) == 1
    assert latest[0]["snapshot_id"] == sid
    assert latest[0]["kind"] == "shutdown"
    assert latest[0]["payload"]["metrics"]["edgy_info"]["series"][0]["app_name"] == "edge-security-system"


@pytest.mark.asyncio
async def test_latest_overview_none_when_empty():
    store = MetricsStore.instance()
    await store.init_schema()
    factory = get_session_factory()
    async with factory() as s:
        await s.execute(text("DELETE FROM metrics_snapshots"))
        await s.commit()
    assert await store.latest_overview() is None


@pytest.mark.asyncio
async def test_purge_retention():
    store = MetricsStore.instance()
    await store.init_schema()
    factory = get_session_factory()
    async with factory() as s:
        await s.execute(text(
            "INSERT INTO metrics_snapshots (snapshot_id, captured_at, payload, kind, note) "
            "VALUES ('old_snap', datetime('now', '-60 days'), '{}', 'scheduled', '')"
        ))
        await s.execute(text(
            "INSERT INTO metrics_snapshots (snapshot_id, captured_at, payload, kind, note) "
            "VALUES ('new_snap', datetime('now'), '{}', 'scheduled', '')"
        ))
        await s.commit()

    deleted = await store.purge(retention_days=30)
    assert deleted == 1, f"应删除 1 条 60 天前的旧快照，实际 {deleted}"

    latest = await store.latest(limit=10)
    ids = [x["snapshot_id"] for x in latest]
    assert "old_snap" not in ids
    assert "new_snap" in ids


@pytest.mark.asyncio
async def test_lifespan_dump_roundtrip():
    """模拟 lifespan shutdown 的 dump + reload 链路 — 不依赖 session-scoped fixture timing。"""
    store = MetricsStore.instance()
    await store.init_schema()

    # 手动调用一次 shutdown dump 的等价物
    from app.services.feedback import feedback_summary
    sid = await store.dump(feedback_summary(), kind="shutdown", note="manual-lifespan-sim")
    assert sid.startswith("snap_")

    latest = await store.latest(limit=10)
    shutdowns = [x for x in latest if x["kind"] == "shutdown"]
    assert shutdowns, "必须能 load 到至少一条 shutdown snapshot"
    # payload 里应该有 metrics/config/system
    payload = shutdowns[0]["payload"]
    assert "config" in payload
    assert "metrics" in payload


@pytest.mark.asyncio
async def test_multiple_dumps_ordered():
    store = MetricsStore.instance()
    await store.init_schema()
    ids = []
    for i in range(3):
        sid = await store.dump({"payload": i}, kind="scheduled", note=f"n={i}")
        ids.append(sid)
    latest = await store.latest(limit=3)
    assert [x["snapshot_id"] for x in latest] == list(reversed(ids))
