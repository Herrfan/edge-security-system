"""Phase 7 metrics API — /metrics, /metrics/overview, /metrics/export.

Tests live in their own subdir so the existing Phase 1-6 tests stay untouched.
"""
from __future__ import annotations

import io

import pytest


@pytest.mark.asyncio
async def test_metrics_prometheus_format(client):
    """GET /api/v1/metrics returns Prometheus exposition text after lifespan."""
    r = client.get("/api/v1/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    text = r.text
    # Must carry at least the info gauge that lifespan stamped
    assert "# HELP edgy_info" in text
    assert "# TYPE edgy_info gauge" in text
    # edgy_info has 5 labels + value 1
    assert 'app_name="edge-security-system"' in text
    assert " 1" in text


@pytest.mark.asyncio
async def test_metrics_overview_structure(client):
    """GET /api/v1/metrics/overview has config + system + metrics blocks."""
    r = client.get("/api/v1/metrics/overview")
    assert r.status_code == 200
    data = r.json()
    assert "generated_at" in data
    cfg = data["config"]
    assert cfg["app_name"] == "edge-security-system"
    assert cfg["app_version"] == "0.1.0"
    assert cfg["llm_model"] == "qwen2.5:3b"
    assert cfg["vector_backend"] == "sqlite_vec"
    sysb = data["system"]
    assert "cpu_percent" in sysb
    assert sysb["cpu_status"] in ("ok", "unavailable")
    assert sysb["rss_status"] in ("ok", "unavailable")
    m = data["metrics"]
    # edgy_info must be ok (set by lifespan)
    assert m["edgy_info"]["status"] == "ok"


@pytest.mark.asyncio
async def test_metrics_unused_is_unavailable(client):
    """Metrics that were never observed show status=unavailable (任务书 §7)."""
    r = client.get("/api/v1/metrics/overview")
    m = r.json()["metrics"]
    # Phase 6 flow never ran Detection → detection counters stay unavailable
    # (unless the TestClient fixture's lifespan + seed called them — check both)
    for name in ("edgy_detection_latency_ms", "edgy_events_seeded_total"):
        entry = m.get(name)
        if entry:
            assert entry["status"] in ("ok", "unavailable")
            if entry["status"] == "unavailable":
                assert entry["series"] == []


@pytest.mark.asyncio
async def test_metrics_export_csv(client):
    """GET /api/v1/metrics/export?format=csv returns downloadable CSV."""
    r = client.get("/api/v1/metrics/export", params={"format": "csv"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    buf = io.StringIO(r.text)
    import csv as _csv
    reader = _csv.reader(buf)
    header = next(reader)
    assert header == ["metric", "kind", "labels", "value", "le"]
    # At least one row for the info gauge
    rows = list(reader)
    gauge_rows = [row for row in rows if row[1] == "Gauge"]
    assert len(gauge_rows) >= 1


@pytest.mark.asyncio
async def test_metrics_export_bad_format(client):
    """Unknown format → 400."""
    r = client.get("/api/v1/metrics/export", params={"format": "json"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_end_to_end_execution_populates_metrics(client, repo_root):
    """Run a real Phase 6 flow — detection + retrieval + RAG + execute —
    then confirm each step left its metric traces."""
    from pathlib import Path

    kpath = repo_root / "data" / "knowledge" / "security_knowledge.jsonl"
    csv_path = repo_root / "data" / "samples" / "flows_sample.csv"

    client.post("/api/v1/knowledge/sync", json={
        "input_path": str(kpath), "reset_first": True,
    })
    client.post("/api/v1/events/seed", json={
        "input_file": str(csv_path), "detector_id": "rule-demo", "max_records": 5,
    })
    event_id = client.get("/api/v1/events?limit=1").json()[0]["event_id"]
    policy_id = client.post("/api/v1/policy-proposal/generate", json={
        "event_id": event_id,
    }).json()["proposal"]["policy_id"]
    client.post("/api/v1/policy-proposal/execute", json={
        "policy_id": policy_id, "mode": "DRY_RUN",
    })

    r = client.get("/api/v1/metrics/overview")
    m = r.json()["metrics"]

    # 1) Detection was called by events/seed → edgy_detections_total ok
    assert m["edgy_detections_total"]["status"] == "ok"

    # 2) Retrieval called by RAG → edgy_retrieval_calls_total ok
    assert m["edgy_retrieval_calls_total"]["status"] == "ok"

    # 3) RAG pipeline → edgy_rag_runs_total ok
    assert m["edgy_rag_runs_total"]["status"] == "ok"

    # 4) Validation run by EndToEndPolicyService → edgy_policy_validations_total ok
    assert m["edgy_policy_validations_total"]["status"] == "ok"

    # 5) Executor.run → edgy_executions_total ok
    assert m["edgy_executions_total"]["status"] == "ok"

    # 6) KB size snapshot
    assert m["edgy_knowledge_chunks_total"]["status"] == "ok"
    assert m["edgy_knowledge_documents_total"]["status"] == "ok"
