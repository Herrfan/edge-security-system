"""Phase 6 tests: PolicyValidator + Executor + EndToEndPolicyService."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.common import (
    ActionType,
    ExecutionMode,
    ExecutionStatus,
    PolicyStatus,
    Severity,
)
from app.domain.policy import (
    BlockIpParams,
    BlockPortParams,
    PolicyProposal,
    RateLimitParams,
)
from app.services.executor import Executor
from app.services.policy_validator import (
    PolicyValidator,
    ValidationIssue,
)


# ---------- test helpers ----------


def _make_proposal(
    action_type: ActionType,
    parameters,
    *,
    ttl_seconds: int = 3600,
    requires_approval: bool = False,
) -> PolicyProposal:
    return PolicyProposal(
        event_id="evt_test_001",
        action_type=action_type,
        parameters=parameters,
        risk_level=Severity.HIGH,
        rationale="test",
        ttl_seconds=ttl_seconds,
        requires_approval=requires_approval,
    )


# ============================================================================
# PolicyValidator unit tests
# ============================================================================


class TestPolicyValidator:
    def test_block_ip_in_allowed_cidr(self):
        v = PolicyValidator()
        p = _make_proposal(ActionType.BLOCK_IP, BlockIpParams(ip="10.0.0.5"))
        vr = v.validate(p)
        assert vr.is_valid
        assert vr.issues == []

    def test_block_ip_outside_scope(self):
        v = PolicyValidator()
        p = _make_proposal(ActionType.BLOCK_IP, BlockIpParams(ip="8.8.8.8"))
        vr = v.validate(p)
        assert not vr.is_valid
        assert any(i.rule == "BLOCK_IP_OUTSIDE_SCOPE" for i in vr.issues)

    def test_block_ip_bad_ip(self):
        v = PolicyValidator()
        p = _make_proposal(ActionType.BLOCK_IP, BlockIpParams(ip="not_an_ip"))
        vr = v.validate(p)
        assert not vr.is_valid
        assert any(i.rule == "BLOCK_IP_INVALID" for i in vr.issues)

    def test_block_port_management_requires_approval(self):
        v = PolicyValidator()
        p = _make_proposal(ActionType.BLOCK_PORT, BlockPortParams(port=22))
        vr = v.validate(p)
        assert not vr.is_valid
        assert any(i.rule == "PORT_APPROVAL_REQUIRED" for i in vr.issues)

    def test_block_port_non_management_ok(self):
        v = PolicyValidator()
        p = _make_proposal(ActionType.BLOCK_PORT, BlockPortParams(port=8080))
        vr = v.validate(p)
        assert vr.is_valid

    def test_rate_limit_ip_outside_scope(self):
        v = PolicyValidator()
        p = _make_proposal(ActionType.RATE_LIMIT,
                           RateLimitParams(ip="8.8.4.4", max_pps=1000))
        vr = v.validate(p)
        assert not vr.is_valid
        assert any(i.rule == "RATE_LIMIT_OUTSIDE_SCOPE" for i in vr.issues)

    def test_alert_always_valid(self):
        v = PolicyValidator()
        p = _make_proposal(ActionType.ALERT_ONLY, BlockPortParams(port=0))
        vr = v.validate(p)
        assert vr.is_valid

    def test_no_action_always_valid(self):
        v = PolicyValidator()
        p = _make_proposal(ActionType.NO_ACTION, BlockPortParams(port=0))
        vr = v.validate(p)
        assert vr.is_valid


# ============================================================================
# Executor unit tests (sync)
# ============================================================================


class TestExecutorDryRun:
    def test_block_ip_produces_plan_not_executed(self):
        exe = Executor(default_mode=ExecutionMode.DRY_RUN)
        p = _make_proposal(ActionType.BLOCK_IP, BlockIpParams(ip="10.0.0.10"))
        rec = exe.execute(p)
        assert rec.mode == ExecutionMode.DRY_RUN
        assert rec.status == ExecutionStatus.SUCCEEDED
        # Guardrail for REAL mode should not affect dry-run
        assert rec.rollback_status == "N/A"

    def test_real_mode_bocks_network_actions(self):
        exe = Executor(default_mode=ExecutionMode.REAL)
        p = _make_proposal(ActionType.BLOCK_IP, BlockIpParams(ip="10.0.0.10"))
        rec = exe.execute(p)
        # Guardrail blocks — should still produce a record with FAILED status
        assert rec.mode == ExecutionMode.REAL
        assert rec.status == ExecutionStatus.FAILED
        assert rec.trace_id and "guardrail" in rec.trace_id

    def test_dry_run_alert_no_stdout(self):
        """DRY_RUN never shells out — stdout must be None."""
        exe = Executor(default_mode=ExecutionMode.DRY_RUN)
        p = _make_proposal(ActionType.ALERT_ONLY, BlockPortParams(port=0))
        rec = exe.execute(p)
        assert rec.stdout_summary is None
        assert rec.stderr_summary is None


# ============================================================================
# API tests — uses real client fixture
# ============================================================================


@pytest.fixture()
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class TestPolicyGenerateAPI:
    def test_generate_dry_run(self, client, repo_root):
        # Setup: knowledge sync → events seed → generate
        kpath = repo_root / "data" / "knowledge" / "security_knowledge.jsonl"
        assert kpath.exists(), f"missing {kpath}"
        r = client.post("/api/v1/knowledge/sync", json={
            "input_path": str(kpath), "reset_first": True,
        })
        assert r.status_code == 200, r.text

        csv_path = repo_root / "data" / "samples" / "flows_sample.csv"
        r = client.post("/api/v1/events/seed", json={
            "input_file": str(csv_path),
            "detector_id": "rule-demo",
            "max_records": 10,
        })
        assert r.status_code == 200, r.text

        event_id = client.get("/api/v1/events?limit=1").json()[0]["event_id"]

        r = client.post("/api/v1/policy-proposal/generate", json={"event_id": event_id})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "proposal" in body
        assert "llm_is_mock" in body
        assert body["evidence_count"] >= 0

    def test_generate_missing_event(self, client):
        r = client.post("/api/v1/policy-proposal/generate", json={"event_id": "evt_does_not_exist"})
        assert r.status_code == 404


class TestPolicyValidateExecuteAPI:
    def test_full_flow(self, client, repo_root):
        """seed → generate → validate → execute (dry-run)."""
        kpath = repo_root / "data" / "knowledge" / "security_knowledge.jsonl"
        csv_path = repo_root / "data" / "samples" / "flows_sample.csv"

        client.post("/api/v1/knowledge/sync", json={
            "input_path": str(kpath), "reset_first": True,
        })
        client.post("/api/v1/events/seed", json={
            "input_file": str(csv_path), "detector_id": "rule-demo", "max_records": 10,
        })
        event_id = client.get("/api/v1/events?limit=1").json()[0]["event_id"]
        policy_id = client.post("/api/v1/policy-proposal/generate", json={
            "event_id": event_id,
        }).json()["proposal"]["policy_id"]

        # Validate
        r_v = client.post("/api/v1/policy-proposal/validate", json={"policy_id": policy_id})
        assert r_v.status_code == 200, r_v.text
        assert "is_valid" in r_v.json()

        # Execute dry-run
        r_e = client.post("/api/v1/policy-proposal/execute", json={
            "policy_id": policy_id, "mode": "DRY_RUN",
        })
        assert r_e.status_code == 200, r_e.text
        body = r_e.json()
        assert body["mode"] == "DRY_RUN"

    def test_execute_invalid_mode_400(self, client, repo_root):
        kpath = repo_root / "data" / "knowledge" / "security_knowledge.jsonl"
        csv_path = repo_root / "data" / "samples" / "flows_sample.csv"
        client.post("/api/v1/knowledge/sync", json={
            "input_path": str(kpath), "reset_first": True,
        })
        client.post("/api/v1/events/seed", json={
            "input_file": str(csv_path), "detector_id": "rule-demo", "max_records": 10,
        })
        event_id = client.get("/api/v1/events?limit=1").json()[0]["event_id"]
        policy_id = client.post("/api/v1/policy-proposal/generate", json={
            "event_id": event_id,
        }).json()["proposal"]["policy_id"]

        r = client.post("/api/v1/policy-proposal/execute", json={
            "policy_id": policy_id, "mode": "NOT_A_MODE",
        })
        assert r.status_code == 400

    def test_list_policies(self, client):
        r = client.get("/api/v1/policy-proposals")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
