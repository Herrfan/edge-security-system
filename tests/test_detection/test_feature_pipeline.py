"""Feature pipeline tests."""
from __future__ import annotations

import pytest

from app.core.errors import AppError, ErrorCode
from app.domain.common import Protocol
from app.domain.flow import FlowRecord
from app.services.feature_pipeline import FeaturePipeline


def _flow(version: str = "v1", features: dict | None = None) -> FlowRecord:
    return FlowRecord(
        src_ip="10.0.0.1", dst_ip="10.0.0.2",
        src_port=5000, dst_port=80, protocol=Protocol.TCP,
        duration_ms=100, packets_src_to_dst=10, packets_dst_to_src=8,
        bytes_src_to_dst=500, bytes_dst_to_src=300,
        feature_schema_version=version,
        features=features or {
            "pkt_rate": 0.1, "byte_rate": 8.0, "pkt_ratio": 1.25,
            "avg_pkt_size": 40.0, "dst_port_common": 1.0,
            "is_short": 0.0, "byte_pkt_ratio": 40.0,
        },
    )


class TestFeaturePipeline:
    def test_extract_vector(self):
        pipe = FeaturePipeline()
        vec = pipe.extract_vector(_flow())
        assert vec.shape == (7,)
        assert vec.dtype.kind in ("f", "c")  # float

    def test_schema_mismatch_rejected(self):
        pipe = FeaturePipeline()
        with pytest.raises(AppError) as exc:
            pipe.extract_vector(_flow(version="v2"))
        assert exc.value.code == ErrorCode.FEATURE_SCHEMA_MISMATCH

    def test_empty_features_rejected(self):
        pipe = FeaturePipeline()
        empty_flow = _flow()
        empty_flow.features.clear()  # Pydantic model allows this post-init
        with pytest.raises(AppError) as exc:
            pipe.extract_vector(empty_flow)
        assert exc.value.code == ErrorCode.VALIDATION_ERROR

    def test_missing_feature_filled_zero(self):
        pipe = FeaturePipeline()
        f = _flow(features={"pkt_rate": 0.5})  # only one feature
        vec = pipe.extract_vector(f)
        # pkt_rate slot → 0.5, others → 0
        assert vec[0] == 0.5
        assert vec[1] == 0.0

    def test_extract_matrix(self):
        pipe = FeaturePipeline()
        flows = [_flow(), _flow(), _flow()]
        mat = pipe.extract_matrix(flows)
        assert mat.shape == (3, 7)

    def test_extract_matrix_empty(self):
        pipe = FeaturePipeline()
        mat = pipe.extract_matrix([])
        assert mat.shape == (0, 7)
