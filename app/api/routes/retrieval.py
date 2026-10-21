"""API routes for knowledge sync and retrieval."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["knowledge", "retrieval"])


class SyncBody(BaseModel):
    input_path: str = Field(..., description="Absolute path to JSONL / Markdown file or directory")
    reset_first: bool = True


# ---------------- /knowledge/sync ----------------------------------------


@router.post("/knowledge/sync")
def knowledge_sync(body: SyncBody) -> dict:
    """Index / rebuild the knowledge base from a local path."""
    from app.services.knowledge_ingestion import sync_knowledge
    from app.services.feedback import snapshot_knowledge_gauges

    p = Path(body.input_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"input path not found: {body.input_path}")

    result = sync_knowledge(p, reset_first=body.reset_first)
    snapshot_knowledge_gauges(result["chunks"], result["documents"], backend=result["provider"].split(":")[0])
    return result


# ---------------- /retrieval/{id} ---------------------------------------


class RetrievalBody(BaseModel):
    query: str
    mode: Optional[str] = Field(default=None, description="keyword | vector | hybrid; None uses config default")
    top_k: int = Field(default=10, ge=1, le=100)


@router.post("/retrieval")
def retrieval_search(body: RetrievalBody) -> dict:
    """Run retrieval and return the top hits."""
    from app.services.retrieval import RetrievalService

    svc = RetrievalService()
    return svc.search(body.query, mode=body.mode, top_k=body.top_k)


@router.get("/retrieval/status")
def retrieval_status() -> dict:
    """Liveness + index size."""
    from app.services.retrieval import RetrievalService
    svc = RetrievalService()
    return {
        "count": svc.count(),
    }


# ---------------- /retrieval/{retrieval_id} ------------------------------

@router.get("/retrieval/{retrieval_id}")
def retrieval_get(retrieval_id: str) -> dict:
    """Reserved endpoint — returns a stored retrieval result by id.

    Phase 4 does not persist retrieval results; this returns 404 until Phase 5.
    Present in the OpenAPI so clients can surface future capability.
    """
    raise HTTPException(
        status_code=404,
        detail=f"retrieval_id={retrieval_id!r} not found — Phase 4 does not persist retrieval results",
    )
