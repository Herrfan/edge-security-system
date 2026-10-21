"""End-to-end HTTP tests for events routes using an in-memory DB.

TestClient is sync — the real app (async) runs in a thread pool. We use
TestClient without override and keep fixtures simple: seed events via the
service layer (in-memory SQLite) then hit the HTTP routes.
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ---- Sync TestClient (the FastAPI app is async; TestClient handles bridge) --

@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def csv_path() -> Path:
    # test_event_api.py → parents[1]=test_events/ → parents[2]=tests/ → parents[3]=repo root
    return Path(__file__).resolve().parents[2] / "data" / "samples" / "flows_sample.csv"


# ---- Helper: seed events via events/seed route ----------------------------

@pytest.fixture()
def seeded_events(client, csv_path) -> None:
    """Call events/seed to populate the real DB (create_all happened on startup)."""
    r = client.post(
        "/api/v1/events/seed",
        json={
            "input_file": str(csv_path),
            "detector_id": "rule-demo",
            "max_records": 30,
            "asset_id": "test-asset",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["seeded_events"] == 30


# --------------------------------------------------------------------------

@pytest.mark.usefixtures("seeded_events")
class TestEventsList:
    def test_list_default(self, client):
        r = client.get("/api/v1/events?limit=100")
        assert r.status_code == 200
        events = r.json()
        assert 0 < len(events) <= 100

    def test_list_filter_by_label(self, client):
        r = client.get("/api/v1/events", params={"label": "port_scan"})
        assert r.status_code == 200
        for e in r.json():
            assert e["predicted_label"] == "port_scan"

    def test_list_filter_by_severity(self, client):
        r = client.get("/api/v1/events", params={"severity": "CRITICAL"})
        assert r.status_code == 200
        for e in r.json():
            assert e["severity"] == "CRITICAL"

    def test_list_pagination(self, client):
        p1 = client.get("/api/v1/events", params={"limit": 5, "offset": 0}).json()
        p2 = client.get("/api/v1/events", params={"limit": 5, "offset": 5}).json()
        assert len(p1) == 5
        assert len(p2) == 5
        assert p1[0]["event_id"] != p2[0]["event_id"]


@pytest.mark.usefixtures("seeded_events")
class TestEventsDetail:
    def test_get_existing(self, client):
        first = client.get("/api/v1/events?limit=1").json()[0]
        ev = client.get(f"/api/v1/events/{first['event_id']}")
        assert ev.status_code == 200
        assert ev.json()["event_id"] == first["event_id"]

    def test_get_unknown_404(self, client):
        r = client.get("/api/v1/events/evt_does_not_exist")
        assert r.status_code == 404


class TestEventsSeedEndpoint:
    def test_seed_directly(self, client, csv_path):
        r = client.post(
            "/api/v1/events/seed",
            json={
                "input_file": str(csv_path),
                "detector_id": "rule-demo",
                "max_records": 10,
                "asset_id": "inline-seed",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["seeded_events"] == 10

    def test_seed_missing_file_404(self, client):
        r = client.post(
            "/api/v1/events/seed",
            json={"input_file": "/no/such/file.csv", "detector_id": "rule-demo"},
        )
        assert r.status_code == 404

    def test_seed_unknown_detector_400(self, client, csv_path):
        r = client.post(
            "/api/v1/events/seed",
            json={"input_file": str(csv_path), "detector_id": "does-not-exist"},
        )
        assert r.status_code == 400
