"""Tests for ExecutionRecord."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.common import ExecutionMode, ExecutionStatus
from app.domain.execution import ExecutionRecord


def _minimal_record() -> dict:
    return {
        "policy_id": "pol_abc123",
        "mode": ExecutionMode.DRY_RUN,
        "status": ExecutionStatus.SUCCEEDED,
    }


class TestExecutionRecordPositive:
    def test_minimal(self):
        r = ExecutionRecord(**_minimal_record())
        assert r.execution_id.startswith("exe_")
        assert r.mode == ExecutionMode.DRY_RUN
        assert r.status == ExecutionStatus.SUCCEEDED

    def test_full(self):
        data = _minimal_record()
        data.update({
            "status": ExecutionStatus.FAILED,
            "before_state_ref": "snapshot_before_20261021.json",
            "after_state_ref": "snapshot_after_20261021.json",
            "stdout_summary": "Added rule 42 to simulation table",
            "stderr_summary": None,
            "rollback_status": "SUCCEEDED",
            "trace_id": "trace_abc",
        })
        r = ExecutionRecord(**data)
        assert r.status == ExecutionStatus.FAILED
        assert r.rollback_status == "SUCCEEDED"


class TestExecutionRecordNegative:
    def test_missing_policy_id(self):
        bad = _minimal_record()
        del bad["policy_id"]
        with pytest.raises(ValidationError):
            ExecutionRecord(**bad)

    def test_invalid_mode(self):
        bad = _minimal_record()
        bad["mode"] = "SIMULATE"
        with pytest.raises(ValidationError):
            ExecutionRecord(**bad)

    def test_invalid_status(self):
        bad = _minimal_record()
        bad["status"] = "PARTIALLY_OK"
        with pytest.raises(ValidationError):
            ExecutionRecord(**bad)

    def test_stderr_too_long(self):
        bad = _minimal_record()
        bad["stderr_summary"] = "x" * 5000  # > max_length=2000
        with pytest.raises(ValidationError):
            ExecutionRecord(**bad)
