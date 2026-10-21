"""API routes for offline flow import and detection."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from app.services.detection import (
    Detector,
    SklearnBaselineDetector,
    get_detector,
    register_detector,
)
from app.services.feature_pipeline import FeaturePipeline
from app.services.ingestion import IngestionSummary, import_file, iter_records

router = APIRouter(prefix="/api/v1", tags=["flows", "detection"])


# --------------------------- Request body schemas -------------------------


class PredictBody(BaseModel):
    detector_id: str = Field(default="rule-demo")
    input_file: str = Field(..., description="Absolute path on server")
    max_records: Optional[int] = None


class TrainBody(BaseModel):
    input_file: str = Field(..., description="Absolute path on server")
    detector_id: str = "sklearn-baseline"
    label_column: str = "label"


# --------------------------- /flows/import --------------------------------

@router.post("/flows/import", response_model=IngestionSummary)
async def flows_import(
    file: UploadFile = File(..., description="CSV / JSONL / JSON flow records"),
    dataset_id: Optional[str] = Form(default=None),
) -> IngestionSummary:
    """Accept an uploaded data file and return an import summary."""
    if file.filename is None:
        raise HTTPException(status_code=400, detail="filename required")

    tmp_dir = Path(__file__).resolve().parents[3] / "data" / "uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    target = tmp_dir / file.filename
    content = await file.read()
    target.write_bytes(content)

    return import_file(target, dataset_id=dataset_id or file.filename)


# --------------------------- /detection/predict ---------------------------

@router.post("/detection/predict")
def detection_predict(body: PredictBody) -> Dict[str, Any]:
    """Run a named detector over a local file."""
    p = Path(body.input_file)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"file not found: {body.input_file}")

    det = get_detector(body.detector_id)
    if det is None:
        raise HTTPException(
            status_code=400,
            detail=f"unknown detector_id={body.detector_id!r}; available: {list(get_detector_registry_keys())}",
        )

    flows = list(iter_records(p))
    if body.max_records:
        flows = flows[: body.max_records]

    results = det.predict(flows)
    return {
        "detector_id": body.detector_id,
        "model_id": det.model_id,
        "model_version": det.model_version,
        "n_flows": len(flows),
        "predictions": [
            {
                "flow_id": r.flow_id,
                "predicted_label": r.predicted_label,
                "score": r.score,
                "latency_ms": round(r.latency_ms, 4),
            }
            for r in results
        ],
    }


# --------------------------- /detection/train -----------------------------

@router.post("/detection/train")
def detection_train(body: TrainBody) -> Dict[str, Any]:
    """Fit the sklearn baseline on a labelled file and register it."""
    import csv
    import numpy as np

    p = Path(body.input_file)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"file not found: {body.input_file}")

    flows = list(iter_records(p))
    truth: List[str] = []
    with p.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            truth.append(row.get(body.label_column, ""))
    truth = truth[: len(flows)]
    if not truth or all(t == "" for t in truth):
        raise HTTPException(
            status_code=400,
            detail=f"no labels found in column {body.label_column!r}",
        )

    pipeline = FeaturePipeline()
    X = pipeline.extract_matrix(flows)
    y = np.array(truth)

    sk = SklearnBaselineDetector()
    sk.fit(X, y, feature_names=pipeline.feature_names)
    register_detector(body.detector_id, sk)

    return {
        "status": "fitted",
        "detector_id": body.detector_id,
        "n_samples": len(flows),
        "classes": sorted(set(truth)),
    }


# ---- Helper ----

def get_detector_registry_keys() -> list[str]:
    """Used by error messages + event seed route."""
    from app.services.detection import _detectors
    return list(_detectors.keys())
