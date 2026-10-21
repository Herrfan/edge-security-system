"""Feature pipeline — schema version awareness.

This module is intentionally thin in Phase 2. The real work of feature
engineering lives inside individual detectors. The pipeline's job is:

1. Verify incoming FlowRecord has a known feature_schema_version.
2. Emit an error (not a silent fallback) when versions don't match.
3. Provide a single helper that extracts the numeric feature vector in a
   canonical column order for sklearn consumption.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

import numpy as np

from app.core.errors import AppError, ErrorCode
from app.domain.flow import FlowRecord


# Canonical feature order — sklearn models trained with this column order
# must see future data in the same order.
CANONICAL_FEATURE_ORDER: List[str] = [
    "pkt_rate",
    "byte_rate",
    "pkt_ratio",
    "avg_pkt_size",
    "dst_port_common",
    "is_short",
    "byte_pkt_ratio",
]


@dataclass
class FeaturePipeline:
    """Schema-aware feature extractor."""

    expected_schema_version: str = "v1"
    feature_names: Sequence[str] = tuple(CANONICAL_FEATURE_ORDER)

    def __post_init__(self) -> None:
        self.feature_names = tuple(self.feature_names)

    def verify(self, flow: FlowRecord) -> None:
        """Raise if feature_schema_version differs from what we expect."""
        if flow.feature_schema_version != self.expected_schema_version:
            raise AppError(
                code=ErrorCode.FEATURE_SCHEMA_MISMATCH,
                message=(
                    f"Feature schema version mismatch: flow={flow.feature_schema_version!r}, "
                    f"detector expects {self.expected_schema_version!r}. "
                    f"This often means the data was produced by a newer pipeline than the model."
                ),
                http_status=400,
            )
        if not flow.features:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="FlowRecord has no features — cannot predict.",
                http_status=400,
            )

    def extract_vector(self, flow: FlowRecord) -> np.ndarray:
        """Extract features in canonical order. Missing features → 0.0."""
        self.verify(flow)
        vec = np.zeros(len(self.feature_names), dtype=np.float32)
        for i, name in enumerate(self.feature_names):
            val = flow.features.get(name, 0.0)
            try:
                vec[i] = float(val)
            except (TypeError, ValueError):
                vec[i] = 0.0
        return vec

    def extract_matrix(self, flows: Sequence[FlowRecord]) -> np.ndarray:
        """Extract a matrix (n_flows × n_features). Fails on the first bad flow."""
        if not flows:
            return np.zeros((0, len(self.feature_names)), dtype=np.float32)
        arr = np.zeros((len(flows), len(self.feature_names)), dtype=np.float32)
        for i, f in enumerate(flows):
            arr[i] = self.extract_vector(f)
        return arr
