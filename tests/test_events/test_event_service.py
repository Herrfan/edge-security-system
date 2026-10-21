"""Event repository + service tests."""
from __future__ import annotations

import pytest

from app.domain.common import PolicyStatus, Severity
from app.domain.event import SecurityEvent
from app.repositories.event_repository import EventRepository
from app.services.event_service import EventService, label_to_severity
from app.services.detection import DetectionResult


def _sample_event(label: str = "port_scan", score: float = 0.85) -> SecurityEvent:
    sev = label_to_severity(label, score)
    return SecurityEvent(
        asset_id="web-server-01",
        flow_id="flow_test_001",
        predicted_label=label,
        score=score,
        severity=sev,
        model_id="rule-demo",
        model_version="v1-demo",
        trace_id="trace-abc",
    )


class TestSeverityMapping:
    def test_normal_is_info(self):
        assert label_to_severity("normal", 0.99) == Severity.INFO

    def test_high_score_critical(self):
        assert label_to_severity("port_scan", 0.95) == Severity.CRITICAL

    def test_high_score_high(self):
        assert label_to_severity("port_scan", 0.8) == Severity.HIGH

    def test_mid_score_medium(self):
        assert label_to_severity("brute_force", 0.65) == Severity.MEDIUM


class TestEventRepository:
    async def test_create_and_get(self, event_session):
        repo = EventRepository(event_session)
        ev = _sample_event()
        got = await repo.create(ev)
        await event_session.commit()
        fetched = await repo.get(ev.event_id)
        assert fetched is not None
        assert fetched.predicted_label == "port_scan"
        assert fetched.score == 0.85
        assert fetched.severity == Severity.HIGH  # 0.8 → HIGH (>= 0.75)
        assert fetched.asset_id == "web-server-01"

    async def test_get_nonexistent(self, event_session):
        repo = EventRepository(event_session)
        assert await repo.get("evt_does_not_exist") is None

    async def test_bulk_create(self, event_session):
        repo = EventRepository(event_session)
        events = [_sample_event("normal", 0.1), _sample_event("brute_force", 0.9)]
        n = await repo.bulk_create(events)
        assert n == 2
        await event_session.commit()
        all_rows = await repo.list()
        assert len(all_rows) == 2

    async def test_list_filter_by_severity(self, event_session):
        repo = EventRepository(event_session)
        await repo.bulk_create([
            _sample_event("port_scan", 0.95),  # CRITICAL
            _sample_event("normal", 0.1),     # INFO
            _sample_event("brute_force", 0.8),  # HIGH
        ])
        await event_session.commit()
        critical = await repo.list(severity=Severity.CRITICAL)
        assert len(critical) == 1
        info = await repo.list(severity=Severity.INFO)
        assert len(info) == 1

    async def test_list_filter_by_label(self, event_session):
        repo = EventRepository(event_session)
        await repo.bulk_create([
            _sample_event("port_scan", 0.9),
            _sample_event("port_scan", 0.8),
            _sample_event("brute_force", 0.9),
        ])
        await event_session.commit()
        ps = await repo.list(label="port_scan")
        assert len(ps) == 2

    async def test_list_pagination(self, event_session):
        repo = EventRepository(event_session)
        await repo.bulk_create([_sample_event() for _ in range(10)])
        await event_session.commit()
        first_page = await repo.list(limit=3, offset=0)
        second_page = await repo.list(limit=3, offset=3)
        assert len(first_page) == 3
        assert len(second_page) == 3
        assert first_page[0].event_id != second_page[0].event_id

    async def test_count(self, event_session):
        repo = EventRepository(event_session)
        await repo.bulk_create([
            _sample_event("port_scan", 0.95),  # CRITICAL
            _sample_event("port_scan", 0.8),   # HIGH
            _sample_event("normal", 0.1),      # INFO
        ])
        await event_session.commit()
        assert await repo.count() == 3
        assert await repo.count(severity=Severity.CRITICAL) == 1
        assert await repo.count(severity=Severity.INFO) == 1


class TestEventService:
    async def test_from_detection(self, event_session):
        svc = EventService(event_session)
        det = DetectionResult(
            flow_id="flow_123",
            predicted_label="brute_force",
            score=0.88,
            model_id="rule-demo",
            model_version="v1-demo",
            latency_ms=0.05,
        )
        ev = svc.from_detection(det, asset_id="ssh-gateway", trace_id="trace-xyz")
        assert ev.flow_id == "flow_123"
        assert ev.predicted_label == "brute_force"
        assert ev.score == 0.88
        assert ev.severity == Severity.HIGH  # 0.88 >= 0.75
        assert ev.asset_id == "ssh-gateway"
        assert ev.trace_id == "trace-xyz"
        assert ev.status == PolicyStatus.DRAFT

    async def test_save_batch_via_service(self, event_session):
        svc = EventService(event_session)
        dets = [
            DetectionResult(
                flow_id=f"flow_{i}",
                predicted_label="normal" if i < 3 else "port_scan",
                score=0.1 if i < 3 else 0.9,
                model_id="rule-demo",
                model_version="v1-demo",
                latency_ms=0.01,
            )
            for i in range(5)
        ]
        events = [svc.from_detection(d) for d in dets]
        n = await svc.save_batch(events)
        assert n == 5
        all_rows = await svc.list()
        assert len(all_rows) == 5


class TestEventAPIRoutes:
    """HTTP-level tests that bypass the real DB via test_session fixture scope."""

    async def _seed_via_service(self, event_session, n: int = 5) -> list[str]:
        svc = EventService(event_session)
        events = [_sample_event("port_scan" if i % 2 else "normal", 0.9 if i % 2 else 0.1)
                  for i in range(n)]
        await svc.save_batch(events)
        await event_session.commit()
        return [e.event_id for e in events]

    async def test_list_paginates(self, event_session):
        ids = await self._seed_via_service(event_session, 6)
        svc = EventService(event_session)
        page = await svc.list(limit=2, offset=2)
        assert len(page) == 2

    async def test_get_by_id(self, event_session):
        ids = await self._seed_via_service(event_session, 3)
        svc = EventService(event_session)
        ev = await svc.get(ids[0])
        assert ev is not None
        assert ev.event_id == ids[0]
