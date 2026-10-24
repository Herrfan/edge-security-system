"""API routes for SecurityEvent list / detail + detection-to-event write."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.domain.common import PolicyStatus, Severity
from app.domain.event import SecurityEvent
from app.services.event_service import EventService

router = APIRouter(prefix="/api/v1", tags=["events"])


@router.get("/events", response_model=List[SecurityEvent])
async def events_list(
    severity: Optional[Severity] = Query(default=None),
    status: Optional[PolicyStatus] = Query(default=None),
    label: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> List[SecurityEvent]:
    svc = EventService(session)
    return await svc.list(severity=severity, status=status, label=label, limit=limit, offset=offset)


@router.get("/events/{event_id}", response_model=SecurityEvent)
async def events_detail(event_id: str, session: AsyncSession = Depends(get_session)) -> SecurityEvent:
    svc = EventService(session)
    ev = await svc.get(event_id)
    if ev is None:
        raise HTTPException(status_code=404, detail=f"event {event_id!r} not found")
    return ev


# ---------------- Bootstrap helper ---------------------------------------
# Dev-only: given a file path + detector name, import flows, run detection,
# persist SecurityEvents. Useful for the end-to-end flow from Phase 2 → 3.

from pydantic import BaseModel, Field


class SeedBody(BaseModel):
    input_file: str
    detector_id: str = "rule-demo"
    max_records: Optional[int] = None
    asset_id: str = "default-asset"
    trace_id: Optional[str] = None


@router.post("/events/seed")
async def events_seed(body: SeedBody, session: AsyncSession = Depends(get_session)) -> dict:
    """Import a local file → run detector → persist events. Dev helper."""
    from pathlib import Path

    from app.services.detection import get_detector
    from app.services.ingestion import iter_records

    p = Path(body.input_file)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"file not found: {body.input_file}")

    det = get_detector(body.detector_id)
    if det is None:
        raise HTTPException(status_code=400, detail=f"unknown detector {body.detector_id!r}")

    flows = list(iter_records(p))
    if body.max_records:
        flows = flows[: body.max_records]

    results = det.predict(flows)
    svc = EventService(session)
    events = [
        svc.from_detection(r, asset_id=body.asset_id, trace_id=body.trace_id) for r in results
    ]
    n = await svc.save_batch(events)

    # --- observability: count seeded events ---
    from app.core.observability import EVENTS_SEEDED_TOTAL
    EVENTS_SEEDED_TOTAL.inc(labels={"detector_id": body.detector_id})

    return {"seeded_events": n, "detector_id": body.detector_id}


class SeedDefaultBody(BaseModel):
    max_records: Optional[int] = None
    asset_id: str = "default-asset"


@router.post("/events/seed-default")
async def events_seed_default(body: SeedDefaultBody, session: AsyncSession = Depends(get_session)) -> dict:
    """Convenience dev helper — seeds events from the repo's sample CSV using rule-demo detector.

    Falls back to defaults:
        input_file  = data/samples/flows_sample.csv
        detector_id = rule-demo
        max_records = all rows (None)
        asset_id    = default-asset (overridable via body.asset_id)
    """
    from pathlib import Path

    from app.services.detection import get_detector
    from app.services.ingestion import iter_records

    repo_root = Path(__file__).resolve().parents[3]
    csv_path = repo_root / "data" / "samples" / "flows_sample.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"default sample CSV not found at {csv_path}")

    det = get_detector("rule-demo")
    if det is None:
        raise HTTPException(status_code=400, detail="rule-demo detector not available")

    flows = list(iter_records(csv_path))
    if body.max_records:
        flows = flows[: body.max_records]

    results = det.predict(flows)
    svc = EventService(session)
    events = [
        svc.from_detection(r, asset_id=body.asset_id, trace_id=None) for r in results
    ]
    n = await svc.save_batch(events)

    from app.core.observability import EVENTS_SEEDED_TOTAL
    EVENTS_SEEDED_TOTAL.inc(labels={"detector_id": "rule-demo"})

    return {
        "seeded_events": n,
        "detector_id": "rule-demo",
        "input_file": str(csv_path),
        "max_records": body.max_records,
    }
