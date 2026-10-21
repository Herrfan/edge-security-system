"""HTTP API tests for /api/v1/flows/import and /api/v1/detection/*."""
from __future__ import annotations

from pathlib import Path

import pytest

# test_api.py → parents[1]=test_detection/ → parents[2]=tests/ → parents[3]=repo root
@pytest.fixture(scope="module")
def sample_csv_path() -> Path:
    """Re-generate the CSV in this module to avoid cross-module fixture pollution."""
    import sys
    ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(ROOT))
    from scripts.generate_sample_data import generate
    return generate(n_per_class=1000, seed=42)


@pytest.fixture(scope="module")
def sample_exists(sample_csv_path) -> bool:
    return sample_csv_path.exists()


class TestFlowsImportAPI:
    def test_import_sample_csv(self, client, sample_csv_path):
        with sample_csv_path.open("rb") as fh:
            resp = client.post(
                "/api/v1/flows/import",
                files={"file": ("flows_sample.csv", fh, "text/csv")},
                data={"dataset_id": "test-upload"},
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total_rows"] == 3000
        assert body["imported"] == 3000
        assert body["failed"] == 0


class TestDetectionPredictAPI:
    def test_rule_demo_predict(self, client, sample_csv_path):
        resp = client.post(
            "/api/v1/detection/predict",
            json={
                "detector_id": "rule-demo",
                "input_file": str(sample_csv_path),
                "max_records": 5,
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["detector_id"] == "rule-demo"
        assert body["n_flows"] == 5
        assert len(body["predictions"]) == 5
        first = body["predictions"][0]
        assert "predicted_label" in first
        assert "score" in first
        assert 0.0 <= first["score"] <= 1.0

    def test_predict_missing_file_404(self, client):
        resp = client.post(
            "/api/v1/detection/predict",
            json={"detector_id": "rule-demo", "input_file": "/nonexistent.csv"},
        )
        assert resp.status_code == 404

    def test_predict_unknown_detector_400(self, client, sample_csv_path):
        resp = client.post(
            "/api/v1/detection/predict",
            json={"detector_id": "unknown-foo", "input_file": str(sample_csv_path)},
        )
        assert resp.status_code == 400

    def test_predict_empty_input_file_422(self, client):
        resp = client.post(
            "/api/v1/detection/predict",
            json={"detector_id": "rule-demo"},  # missing input_file (required)
        )
        # FastAPI validation for missing required field
        assert resp.status_code == 422, resp.text


class TestDetectionTrainAPI:
    def test_fit_sklearn_and_predict(self, client, sample_csv_path):
        r_train = client.post(
            "/api/v1/detection/train",
            json={"input_file": str(sample_csv_path), "detector_id": "sklearn-baseline"},
        )
        assert r_train.status_code == 200, r_train.text
        body = r_train.json()
        assert body["status"] == "fitted"
        assert "normal" in body["classes"]
        assert "port_scan" in body["classes"]
        assert "brute_force" in body["classes"]

        r_pred = client.post(
            "/api/v1/detection/predict",
            json={
                "detector_id": "sklearn-baseline",
                "input_file": str(sample_csv_path),
                "max_records": 10,
            },
        )
        assert r_pred.status_code == 200, r_pred.text
        assert r_pred.json()["n_flows"] == 10
