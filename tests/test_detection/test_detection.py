"""RuleDemoDetector + SklearnBaselineDetector tests."""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import classification_report

from app.domain.common import Protocol
from app.domain.flow import FlowRecord
from app.services.detection import (
    Detector,
    RuleDemoDetector,
    SklearnBaselineDetector,
)
from app.services.feature_pipeline import FeaturePipeline


def _synth_flow(**overrides) -> FlowRecord:
    base = dict(
        src_ip="10.0.0.1", dst_ip="10.0.0.2",
        src_port=5000, dst_port=80, protocol=Protocol.TCP,
        duration_ms=100.0, packets_src_to_dst=10, packets_dst_to_src=8,
        bytes_src_to_dst=500, bytes_dst_to_src=300,
        features={
            "pkt_rate": 0.1, "byte_rate": 8.0, "pkt_ratio": 1.25,
            "avg_pkt_size": 40.0, "dst_port_common": 1.0,
            "is_short": 0.0, "byte_pkt_ratio": 40.0,
        },
    )
    base.update(overrides)
    return FlowRecord(**base)


# -------- RuleDemoDetector -----------------------------------------------

class TestRuleDemoDetector:
    def test_rule_demo_marks_demo(self):
        d = RuleDemoDetector()
        assert d.model_id == "rule-demo"
        assert "demo" in d.model_version.lower()

    def test_normal_classified_as_normal(self):
        d = RuleDemoDetector()
        r = d.predict([_synth_flow()])[0]
        assert r.predicted_label == "normal"

    def test_brute_force_detected(self):
        f = _synth_flow(dst_port=22, duration_ms=50, packets_src_to_dst=15)
        d = RuleDemoDetector()
        r = d.predict([f])[0]
        assert r.predicted_label == "brute_force"
        assert 0.0 <= r.score <= 1.0

    def test_port_scan_detected(self):
        f = _synth_flow(
            dst_port=23, duration_ms=20, packets_src_to_dst=3,
            bytes_src_to_dst=80,
        )
        d = RuleDemoDetector()
        r = d.predict([f])[0]
        assert r.predicted_label == "port_scan"

    def test_batch_prediction(self):
        d = RuleDemoDetector()
        flows = [_synth_flow() for _ in range(10)]
        results = d.predict(flows)
        assert len(results) == 10
        assert all(r.flow_id for r in results)
        assert all(r.latency_ms >= 0 for r in results)

    def test_empty_input(self):
        d = RuleDemoDetector()
        assert d.predict([]) == []


# -------- SklearnBaselineDetector ----------------------------------------

@pytest.fixture(scope="module")
def fitted_sklearn() -> SklearnBaselineDetector:
    """Fit on the same synthetic data generation script uses."""
    import sys
    ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(ROOT))
    from scripts.generate_sample_data import generate
    from app.services.ingestion import iter_records

    csv_path = generate(n_per_class=300, seed=99)
    flows = list(iter_records(csv_path))

    truth: list[str] = []
    with csv_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            truth.append(row["label"])
    truth = truth[: len(flows)]

    pipe = FeaturePipeline()
    X = pipe.extract_matrix(flows)
    y = np.array(truth)

    det = SklearnBaselineDetector()
    det.fit(X, y, feature_names=pipe.feature_names)
    return det


class TestSklearnBaselineFitted:
    def test_fit_sets_model_id(self, fitted_sklearn):
        assert fitted_sklearn.model_id.startswith("sklearn-baseline")
        assert fitted_sklearn.is_fitted is True

    def test_predict_on_training_data(self, fitted_sklearn):
        import sys
        ROOT = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(ROOT))
        from scripts.generate_sample_data import generate
        from app.services.ingestion import iter_records

        csv_path = generate(n_per_class=300, seed=99)
        flows = list(iter_records(csv_path))

        results = fitted_sklearn.predict(flows)
        assert len(results) == len(flows)
        # All predicted labels must be one of the 3 known classes
        known = {"normal", "port_scan", "brute_force"}
        assert all(r.predicted_label in known for r in results)
        assert all(0.0 <= r.score <= 1.0 for r in results)

    def test_scores_reasonable(self, fitted_sklearn):
        """LogisticRegression on 300×300×300 should give non-trivial accuracy.

        We only assert the mean F1 across the reported `macro avg` is >= 0.6 —
        this is intentionally permissive because the synthetic data generation
        is deterministic but random. We want a regression guard, not a benchmark.
        """
        import sys
        ROOT = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(ROOT))
        from scripts.generate_sample_data import generate
        from app.services.ingestion import iter_records

        csv_path = generate(n_per_class=300, seed=99)
        flows = list(iter_records(csv_path))
        truth: list[str] = []
        with csv_path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                truth.append(row["label"])
        truth = truth[: len(flows)]

        results = fitted_sklearn.predict(flows)
        preds = [r.predicted_label for r in results]
        report = classification_report(truth, preds, output_dict=True, zero_division=0)
        macro_f1 = report["macro avg"]["f1-score"]
        assert macro_f1 >= 0.6, f"macro F1={macro_f1:.3f} — baseline underperforming"


class TestSklearnBaselineUnfitted:
    def test_predict_before_fit_raises(self):
        det = SklearnBaselineDetector()
        with pytest.raises(RuntimeError, match="not fitted"):
            det.predict([_synth_flow()])

    def test_fit_empty_raises(self):
        det = SklearnBaselineDetector()
        with pytest.raises(ValueError, match="empty"):
            det.fit(np.zeros((0, 7)), np.array([]), feature_names=tuple("abc"))

    def test_empty_prediction(self):
        det = SklearnBaselineDetector()
        det.fit(
            np.random.randn(20, 7),
            np.array(["a", "b"] * 10),
            feature_names=tuple("abcdefg"),
        )
        assert det.predict([]) == []
