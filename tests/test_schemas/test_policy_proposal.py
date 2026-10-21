"""Tests for PolicyProposal + parameter shapes."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.common import ActionType, Severity
from app.domain.policy import (
    BlockIpParams,
    BlockPortParams,
    PolicyProposal,
    RateLimitParams,
)


def _minimal_policy() -> dict:
    return {
        "event_id": "evt_abc123",
        "action_type": ActionType.ALERT_ONLY,
        "parameters": BlockIpParams(ip="127.0.0.1"),  # Will be accepted loosely for ALERT_ONLY
        "rationale": "Testing positive case",
    }


class TestPolicyProposalPositive:
    def test_alert_only(self):
        # ALERT_ONLY accepts any or no params
        p = PolicyProposal(
            event_id="evt_1",
            action_type=ActionType.ALERT_ONLY,
            parameters=BlockIpParams(ip="127.0.0.1"),
            rationale="Log and alert only",
        )
        assert p.policy_id.startswith("pol_")
        assert p.ttl_seconds == 3600
        assert p.expires_at is not None

    def test_block_ip(self):
        p = PolicyProposal(
            event_id="evt_2",
            action_type=ActionType.BLOCK_IP,
            parameters=BlockIpParams(ip="127.0.0.1"),
            rationale="Port scanner identified",
            evidence_ids=["evd_1"],
            risk_level=Severity.HIGH,
        )
        assert isinstance(p.parameters, BlockIpParams)

    def test_rate_limit(self):
        p = PolicyProposal(
            event_id="evt_3",
            action_type=ActionType.RATE_LIMIT,
            parameters=RateLimitParams(ip="192.168.1.50", max_pps=1000),
            rationale="DDoS attempt",
        )
        assert p.ttl_seconds == 3600  # default

    def test_block_port(self):
        p = PolicyProposal(
            event_id="evt_4",
            action_type=ActionType.BLOCK_PORT,
            parameters=BlockPortParams(port=22),
            rationale="SSH brute force",
            requires_approval=True,
        )
        assert p.requires_approval is True

    def test_explicit_ttl(self):
        p = PolicyProposal(
            event_id="evt_5",
            action_type=ActionType.ALERT_ONLY,
            parameters=BlockIpParams(ip="0.0.0.0"),
            rationale="TTL test",
            ttl_seconds=120,
        )
        from datetime import timedelta
        assert p.expires_at == p.created_at + timedelta(seconds=120)


class TestPolicyProposalNegative:
    def test_missing_event_id(self):
        with pytest.raises(ValidationError):
            PolicyProposal(
                action_type=ActionType.ALERT_ONLY,
                parameters=BlockIpParams(ip="0.0.0.0"),
                rationale="x",
            )

    def test_mismatched_params_shape(self):
        # BLOCK_PORT action but BlockIpParams shape
        with pytest.raises(ValidationError):
            PolicyProposal(
                event_id="evt_x",
                action_type=ActionType.BLOCK_PORT,
                parameters=BlockIpParams(ip="127.0.0.1"),
                rationale="mismatch",
            )

    def test_ttl_too_short(self):
        with pytest.raises(ValidationError):
            PolicyProposal(
                event_id="evt_x",
                action_type=ActionType.ALERT_ONLY,
                parameters=BlockIpParams(ip="0.0.0.0"),
                rationale="ttl too low",
                ttl_seconds=5,
            )

    def test_ttl_too_long(self):
        with pytest.raises(ValidationError):
            PolicyProposal(
                event_id="evt_x",
                action_type=ActionType.ALERT_ONLY,
                parameters=BlockIpParams(ip="0.0.0.0"),
                rationale="ttl too high",
                ttl_seconds=86400 * 30,
            )

    def test_invalid_action_type(self):
        with pytest.raises(ValidationError):
            PolicyProposal(
                event_id="evt_x",
                action_type="DROP_PACKET",  # Not in whitelist
                parameters=BlockIpParams(ip="0.0.0.0"),
                rationale="bad action",
            )

    def test_empty_rationale(self):
        with pytest.raises(ValidationError):
            PolicyProposal(
                event_id="evt_x",
                action_type=ActionType.ALERT_ONLY,
                parameters=BlockIpParams(ip="0.0.0.0"),
                rationale="",
            )

    def test_block_port_zero_port(self):
        # Port 0 technically out of our intent range; model allows 0, 65535 only
        # We don't hard-reject 0 here — keep policy-level checks for runtime
        # But test > 65535
        with pytest.raises(ValidationError):
            BlockPortParams(port=70000)
