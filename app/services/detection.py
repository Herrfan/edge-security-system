"""Detector interface + two baseline implementations.

Phase 2 ships two detectors so we cover both the "rule-based demo" and the
"traditional ML baseline" goals from the task book. Both:

  * conform to the same Detector abstract interface,
  * save model_id + model_version on output,
  * never mutate input data,
  * never send anything to the network.

Neither model is production-grade. The RuleDemoDetector uses hand-tuned
thresholds and MUST be labelled as a DEMO wherever it is surfaced to a
human. The SklearnBaselineDetector trains on the fly from labelled data
passed in — it is not pre-trained.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.domain.flow import FlowRecord
from app.core.observability import DETECTIONS_TOTAL, DETECTION_LATENCY_MS

logger = logging.getLogger(__name__)


# ---- Output shape --------------------------------------------------------

@dataclass
class DetectionResult:
    """One per input FlowRecord."""
    flow_id: str
    predicted_label: str
    score: float         # 0..1
    model_id: str
    model_version: str
    latency_ms: float


# ---- Abstract Detector ---------------------------------------------------

class Detector(ABC):
    """All detectors implement this interface. Swap freely at Phase 3+."""

    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @property
    @abstractmethod
    def model_version(self) -> str: ...

    @abstractmethod
    def predict(self, flows: Sequence[FlowRecord]) -> List[DetectionResult]: ...


# ---------------- RuleDemoDetector ----------------------------------------

class RuleDemoDetector(Detector):
    """Deterministic hand-written rules. DEMO ONLY — no real security claim.

    Rules (tuned for our synthetic dataset):
      * brute_force: dst_port ∈ {22, 3389} AND duration_ms < 200 AND
                     packets_src_to_dst >= 8
      * port_scan  : duration_ms < 60 AND packets_src_to_dst <= 5 AND
                     bytes_src_to_dst < 200 AND dst_port <= 1023
      * otherwise  : normal
    """

    model_id = "rule-demo"
    model_version = "v1-demo"

    def predict(self, flows: Sequence[FlowRecord]) -> List[DetectionResult]:
        out: List[DetectionResult] = []
        for f in flows:
            t0 = time.perf_counter()
            label, score = self._classify(f)
            latency = (time.perf_counter() - t0) * 1000.0
            out.append(DetectionResult(
                flow_id=f.flow_id,
                predicted_label=label,
                score=score,
                model_id=self.model_id,
                model_version=self.model_version,
                latency_ms=latency,
            ))
            DETECTIONS_TOTAL.inc(labels={"detector_id": self.model_id, "label": label})
            DETECTION_LATENCY_MS.observe(latency, labels={"detector_id": self.model_id})
        return out

    @staticmethod
    def _classify(f: FlowRecord) -> tuple[str, float]:
        # --- brute_force ---
        if (
            f.dst_port in (22, 3389)
            and f.duration_ms < 200
            and f.packets_src_to_dst >= 8
        ):
            return "brute_force", 0.92

        # --- port_scan ---
        if (
            f.duration_ms < 60
            and f.packets_src_to_dst <= 5
            and f.bytes_src_to_dst < 200
            and f.dst_port <= 1023
        ):
            return "port_scan", 0.90

        return "normal", 0.85


# ---------------- SklearnBaselineDetector ---------------------------------

class SklearnBaselineDetector(Detector):
    """LogisticRegression baseline trained on labelled data.

    Intentionally small so training + inference finish in under a second on CPU.
    Labels used during training are a required input to :meth:`fit` — there is
    NO bundled pre-trained model.
    """

    model_id = "sklearn-baseline-logreg"
    model_version = "v1"
    feature_names: List[str]

    def __init__(self) -> None:
        self.feature_names = []
        self._clf = None  # lazy sklearn import; don't break RuleDemoDetector import

    @property
    def is_fitted(self) -> bool:
        return self._clf is not None

    # ---------- fit ----------
    def fit(self, X: np.ndarray, y: np.ndarray, *, feature_names: Sequence[str]) -> None:
        """Train from numpy arrays.

        Args:
            X: (n, d) feature matrix
            y: (n,) string labels
            feature_names: column order — MUST match prediction-time order
        """
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler

        if len(X) == 0:
            raise ValueError("cannot fit on empty feature matrix")

        self.feature_names = list(feature_names)
        self._scaler = StandardScaler().fit(X)
        Xs = self._scaler.transform(X)

        # n_classes will be inferred from y — let sklearn handle the mapping
        self._clf = LogisticRegression(
            max_iter=300,
            solver="lbfgs",
            C=1.0,
            random_state=42,
        ).fit(Xs, y)

        logger.info(
            "SklearnBaselineDetector fitted: n_samples=%d n_features=%d classes=%s",
            len(X), X.shape[1], sorted(set(y.tolist())),
        )

    # ---------- predict ----------
    def predict(self, flows: Sequence[FlowRecord]) -> List[DetectionResult]:
        if not self.is_fitted:
            raise RuntimeError(
                "SklearnBaselineDetector is not fitted. Call fit() with labelled data first."
            )
        if not flows:
            return []

        from app.services.feature_pipeline import FeaturePipeline

        pipeline = FeaturePipeline(feature_names=tuple(self.feature_names))
        X = pipeline.extract_matrix(flows)
        Xs = self._scaler.transform(X)

        t0 = time.perf_counter()
        y_pred = self._clf.predict(Xs)
        y_prob = self._clf.predict_proba(Xs).max(axis=1)
        per_flow_latency = (time.perf_counter() - t0) * 1000.0 / len(flows)

        out: List[DetectionResult] = []
        for i, f in enumerate(flows):
            out.append(DetectionResult(
                flow_id=f.flow_id,
                predicted_label=str(y_pred[i]),
                score=float(y_prob[i]),
                model_id=self.model_id,
                model_version=self.model_version,
                latency_ms=per_flow_latency,
            ))
            DETECTIONS_TOTAL.inc(labels={"detector_id": self.model_id, "label": str(y_pred[i])})
            DETECTION_LATENCY_MS.observe(per_flow_latency, labels={"detector_id": self.model_id})
        return out


# ---- Module-level detector registry -------------------------------------
# In-memory only for Phase 2/3. Phase 4+ will replace with a proper service.
_detectors: Dict[str, "Detector"] = {
    "rule-demo": RuleDemoDetector(),
}


def get_detector(detector_id: str) -> Optional[Detector]:
    return _detectors.get(detector_id)


def register_detector(detector_id: str, det: Detector) -> None:
    _detectors[detector_id] = det
