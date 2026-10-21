"""EventService — convert DetectionResult → SecurityEvent + persist."""
from __future__ import annotations

from typing import Iterable, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.common import PolicyStatus, Severity
from app.domain.event import SecurityEvent
from app.repositories.event_repository import EventRepository
from app.services.detection import DetectionResult


# -------- Severity mapping rules ------------------------------------------
# Hand-tuned, simple. Later we may want per-detector or per-CVE overrides.
_NORMAL_LABELS = {"normal", "benign", "ok"}


def label_to_severity(label: str, score: float) -> Severity:
    if label in _NORMAL_LABELS:
        return Severity.INFO
    if score >= 0.9:
        return Severity.CRITICAL
    if score >= 0.75:
        return Severity.HIGH
    if score >= 0.55:
        return Severity.MEDIUM
    return Severity.LOW


class EventService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = EventRepository(session)

    # -------- DetectionResult → SecurityEvent ----------

    def from_detection(
        self,
        det: DetectionResult,
        *,
        asset_id: str = "default-asset",
        flow_summary: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> SecurityEvent:
        sev = label_to_severity(det.predicted_label, det.score)
        return SecurityEvent(
            asset_id=asset_id,
            flow_id=det.flow_id,
            flow_summary=flow_summary,
            predicted_label=det.predicted_label,
            score=det.score,
            severity=sev,
            model_id=det.model_id,
            model_version=det.model_version,
            status=PolicyStatus.DRAFT,
            trace_id=trace_id,
        )

    # -------- Persist ----------

    async def save(self, event: SecurityEvent) -> SecurityEvent:
        return await self._repo.create(event)

    async def save_batch(self, events: Iterable[SecurityEvent]) -> int:
        return await self._repo.bulk_create(list(events))

    # -------- Read-through ----------

    async def get(self, event_id: str):
        return await self._repo.get(event_id)

    async def list(self, **kwargs):
        return await self._repo.list(**kwargs)

    async def count(self, **kwargs):
        return await self._repo.count(**kwargs)
