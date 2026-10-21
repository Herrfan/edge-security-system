"""Phase 9 — 红队测试：防御边界验证。

每个测试 = 一个攻击向量。断言是"防御必须生效"，不是"攻击必须成功"。
如果测试 fail — 说明防御有漏洞 — 这就是 bug。

覆盖范围：

- T-1: 恶意 LLM / RAG 建议 BLOCK_IP 非白名单 → PolicyValidator 拦截
- T-2: 不存在的 event_id → 404 不崩溃
- T-4: SQLite 篡改 → 原型没签名机制（注释里说明；不可在 pytest 里真测）
- T-6: LLM prompt injection 绕过 action_map → ALERT_ONLY 降级
- Phase 6: REAL 模式 guardrail / 管理端口 / 非法 IP / 非法 TTL / 参数 shape
"""
from __future__ import annotations

import ipaddress
import pytest

from app.adapters.llm.base import LLMProvider
from app.domain.common import (
    ActionType,
    ExecutionMode,
    PolicyStatus,
    Severity,
)
from app.domain.event import SecurityEvent
from app.domain.policy import (
    BlockIpParams,
    BlockPortParams,
    PolicyProposal,
    RateLimitParams,
)
from app.services.executor import Executor
from app.services.policy_validator import PolicyValidator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def validator() -> PolicyValidator:
    return PolicyValidator()


@pytest.fixture()
def executor() -> Executor:
    return Executor()


def _mal_llm(prompt_response: dict) -> LLMProvider:
    """构造一个可控返回指定 JSON 的 FakeLLM。"""
    from app.adapters.llm.base import MockLLM
    class _MaliciousLLM(MockLLM):
        def __init__(self, target: dict):
            super().__init__()
            self._target = target

        def generate_json(self, *args, **kwargs):
            return self._target

    return _MaliciousLLM(prompt_response)


def _make_proposal(action_type, *, parameters=None, ip=None, port=None, ttl=None,
                   requires_approval=False, rationale=None) -> PolicyProposal:
    if parameters is None:
        if action_type == ActionType.BLOCK_IP:
            parameters = BlockIpParams(ip=ip or "10.0.0.5")
        elif action_type == ActionType.BLOCK_PORT:
            parameters = BlockPortParams(port=port or 80)
        elif action_type == ActionType.RATE_LIMIT:
            parameters = RateLimitParams(ip=ip or "10.0.0.5", max_pps=1000)
        elif action_type in (ActionType.ALERT_ONLY, ActionType.NO_ACTION):
            # ALERT_ONLY / NO_ACTION 参数 shape 宽松，用 BlockIpParams 做占位
            parameters = BlockIpParams(ip="10.0.0.5")
    return PolicyProposal(
        event_id="evt_redteam_test",
        action_type=action_type,
        parameters=parameters,
        ttl_seconds=ttl if ttl is not None else 3600,
        rationale=rationale or "red-team synthetic test",
        requires_approval=requires_approval,
        risk_level=Severity.HIGH,
    )


def _make_event(*, label="brute_force", score=0.9) -> SecurityEvent:
    return SecurityEvent(
        asset_id="asset-demo",
        predicted_label=label,
        score=score,
        severity=Severity.HIGH,
    )


# ===================================================================
# Category A: 正向边界验证 — 合法动作必须通过
# ===================================================================


class TestPositiveBoundary:
    """防御必须放行合法动作。"""

    def test_block_ip_in_whitelist(self, validator):
        p = _make_proposal(ActionType.BLOCK_IP, ip="10.0.0.5")
        r = validator.validate(p)
        assert r.is_valid, f"合法 BLOCK_IP(10.0.0.5) 应通过，实际 issues={r.issues}"

    def test_block_port_non_mgmt_no_approval(self, validator):
        p = _make_proposal(ActionType.BLOCK_PORT, port=80, requires_approval=False)
        r = validator.validate(p)
        assert r.is_valid

    def test_block_port_mgmt_with_approval(self, validator):
        p = _make_proposal(ActionType.BLOCK_PORT, port=22, requires_approval=True)
        r = validator.validate(p)
        assert r.is_valid, f"管理端口 + approval=True 应通过，实际 issues={r.issues}"

    def test_rate_limit_in_whitelist(self, validator):
        p = _make_proposal(ActionType.RATE_LIMIT, ip="192.168.1.100")
        r = validator.validate(p)
        assert r.is_valid

    def test_alert_only_always_passes(self, validator):
        # ALERT_ONLY 不需要 further checks
        p = _make_proposal(ActionType.ALERT_ONLY)
        r = validator.validate(p)
        assert r.is_valid


# ===================================================================
# Category B: T-1 / Phase 6 — 恶意 BLOCK_IP / RATE_LIMIT 非白名单
# ===================================================================


class TestOutsideWhitelist:
    """威胁 T-1 核心：LLM / 用户建议的 IP 不在允许 CIDR 中 → 必须拦截。"""

    @staticmethod
    def _rule_codes(issues):
        return [i.rule for i in issues]

    # --- BLOCK_IP ---

    def test_block_ip_public_ip_1_2_3_4(self, validator):
        p = _make_proposal(ActionType.BLOCK_IP, ip="1.2.3.4")
        r = validator.validate(p)
        assert not r.is_valid
        assert "BLOCK_IP_OUTSIDE_SCOPE" in self._rule_codes(r.issues)

    def test_block_ip_127_loopback(self, validator):
        p = _make_proposal(ActionType.BLOCK_IP, ip="127.0.0.5")
        r = validator.validate(p)
        assert not r.is_valid

    def test_block_ip_ipv6_public(self, validator):
        p = _make_proposal(ActionType.BLOCK_IP, ip="2001:db8::1")
        r = validator.validate(p)
        assert not r.is_valid

    def test_block_ip_cidr_itself_blocked(self, validator):
        p = _make_proposal(ActionType.BLOCK_IP, ip="10.0.0.0/24")
        r = validator.validate(p)
        assert not r.is_valid
        assert "BLOCK_IP_INVALID" in self._rule_codes(r.issues)

    def test_block_ip_malformed(self, validator):
        p = _make_proposal(ActionType.BLOCK_IP, ip="not.an.ip")
        r = validator.validate(p)
        assert not r.is_valid
        assert "BLOCK_IP_INVALID" in self._rule_codes(r.issues)

    # --- RATE_LIMIT ---

    def test_rate_limit_public_ip(self, validator):
        p = _make_proposal(ActionType.RATE_LIMIT, ip="8.8.8.8")
        r = validator.validate(p)
        assert not r.is_valid
        assert "RATE_LIMIT_OUTSIDE_SCOPE" in self._rule_codes(r.issues)

    def test_rate_limit_malformed_ip(self, validator):
        p = _make_proposal(ActionType.RATE_LIMIT, ip="0.0.0.999")
        r = validator.validate(p)
        assert not r.is_valid


# ===================================================================
# Category C: Phase 6 — 管理端口 / approval 边界
# ===================================================================


class TestManagementPortApproval:
    """管理端口必须 requires_approval=True。"""

    @staticmethod
    def _rule_codes(issues):
        return [i.rule for i in issues]

    @pytest.mark.parametrize("port", [22, 3389, 5985, 5986, 8443])
    def test_each_management_port_requires_approval(self, validator, port):
        p = _make_proposal(ActionType.BLOCK_PORT, port=port, requires_approval=False)
        r = validator.validate(p)
        assert not r.is_valid, f"port={port} without approval should fail"
        assert "PORT_APPROVAL_REQUIRED" in self._rule_codes(r.issues)

    @pytest.mark.parametrize("port", [22, 3389, 5985, 5986, 8443])
    def test_each_management_port_with_approval_passes(self, validator, port):
        p = _make_proposal(ActionType.BLOCK_PORT, port=port, requires_approval=True)
        r = validator.validate(p)
        assert r.is_valid


# ===================================================================
# Category D: TTL 边界
# ===================================================================


class TestTTLBounds:
    def test_ttl_zero_rejected(self, validator):
        with pytest.raises(Exception):
            _make_proposal(ActionType.BLOCK_IP, ttl=0, ip="10.0.0.5")

    def test_ttl_59_rejected(self, validator):
        with pytest.raises(Exception):
            _make_proposal(ActionType.BLOCK_IP, ttl=59, ip="10.0.0.5")

    def test_ttl_60_passes(self, validator):
        p = _make_proposal(ActionType.BLOCK_IP, ttl=60, ip="10.0.0.5")
        r = validator.validate(p)
        assert r.is_valid

    def test_ttl_7days_passes(self, validator):
        p = _make_proposal(ActionType.BLOCK_IP, ttl=604800, ip="10.0.0.5")
        r = validator.validate(p)
        assert r.is_valid

    def test_ttl_7days_plus_one_rejected(self, validator):
        with pytest.raises(Exception):
            _make_proposal(ActionType.BLOCK_IP, ttl=604801, ip="10.0.0.5")


# ===================================================================
# Category E: 参数 Shape Union 边界（domain 层 extra="forbid"）
# ===================================================================


class TestParameterShape:
    """action_type 与 parameters shape 必须匹配 — domain 层 model_validator 拦截。"""

    def test_block_port_with_block_ip_params_rejected(self):
        # BLOCK_PORT 需要 BlockPortParams (port), 不能用 BlockIpParams
        with pytest.raises(Exception):
            PolicyProposal(
                event_id="evt_x",
                action_type=ActionType.BLOCK_PORT,
                parameters=BlockIpParams(ip="10.0.0.5"),  # 错误 shape
                rationale="test",
            )

    def test_block_ip_with_bare_dict_rejected(self):
        # extra="forbid" — dict 不能直接绕过 Pydantic 校验
        with pytest.raises(Exception):
            PolicyProposal(
                event_id="evt_x",
                action_type=ActionType.BLOCK_IP,
                parameters={"ip": "10.0.0.5", "malicious": True},
                rationale="test",
            )


# ===================================================================
# Category F: T-1 — FakeLLM 构造 RAG 攻击路径
# ===================================================================


class TestRAGActionMapDegradation:
    """LLM 返回非法 action → action_map 自动降级 ALERT_ONLY。"""

    def test_unknown_action_degrades_to_alert_only(self):
        from app.services.rag_service import RAGService

        fake = _mal_llm({"RECOMMENDED_ACTION": "DESTROY_SYSTEM", "THREAT_LEVEL": "CRITICAL"})
        rag = RAGService(llm=fake, retrieval=None)

        event = _make_event(label="brute_force", score=0.9)
        llm_parsed = fake.generate_json("any", system="", temperature=0.1)
        proposal = rag._build_proposal(
            event=event,
            llm_parsed=llm_parsed,
            llm_error=None,
            retrieval_status="OK",
            evidence_doc_ids=[],
            evidences=[],
        )
        assert proposal.action_type == ActionType.ALERT_ONLY, \
            f"未知 action 'DESTROY_SYSTEM' 应降级 ALERT_ONLY，实际 {proposal.action_type}"

    def test_unknown_action_reverse_mapping(self):
        from app.services.rag_service import RAGService
        fake = _mal_llm({"RECOMMENDED_ACTION": "PWNED_HOST", "THREAT_LEVEL": "CRITICAL"})
        rag = RAGService(llm=fake, retrieval=None)
        event = _make_event(label="ddos", score=0.8)
        llm_parsed = fake.generate_json("x", system="", temperature=0.1)
        proposal = rag._build_proposal(
            event=event, llm_parsed=llm_parsed, llm_error=None,
            retrieval_status="OK", evidence_doc_ids=[], evidences=[],
        )
        assert proposal.action_type == ActionType.ALERT_ONLY

    def test_block_ip_non_whitelist_reaches_validator(self):
        """LLM 合法返回 BLOCK_IP + 非白名单 IP → RAGService 不拦截（拦截在 PolicyValidator）。"""
        from app.services.rag_service import RAGService
        fake = _mal_llm({
            "RECOMMENDED_ACTION": "BLOCK_IP",
            "THREAT_LEVEL": "CRITICAL",
            "JUSTIFICATION": "Attack from 1.2.3.4",
        })
        rag = RAGService(llm=fake, retrieval=None)
        event = _make_event(label="brute_force", score=0.99)
        llm_parsed = fake.generate_json("x", system="", temperature=0.1)
        proposal = rag._build_proposal(
            event=event, llm_parsed=llm_parsed, llm_error=None,
            retrieval_status="OK", evidence_doc_ids=["doc_mal"], evidences=[],
        )
        validator = PolicyValidator()
        result = validator.validate(proposal)
        if proposal.action_type == ActionType.BLOCK_IP:
            ip = proposal.parameters.ip
            try:
                o = ipaddress.ip_address(ip)
                allowed = any(o in n for n in validator.allowed_cidrs)
                if not allowed:
                    assert not result.is_valid, f"BLOCK_IP({ip}) outside whitelist must fail"
            except ValueError:
                assert not result.is_valid


# ===================================================================
# Category G: Executor guardrail（REAL 模式）
# ===================================================================


class TestExecutorGuardrail:
    """REAL 模式必须拦截所有破坏性动作。"""

    def test_real_blocks_block_ip(self, executor, monkeypatch):
        # allow_real_execution=False（默认）→ REAL 永远拦截，这是 product-level 硬边界
        p = _make_proposal(ActionType.BLOCK_IP, ip="10.0.0.5")
        rec = executor.execute(p, mode=ExecutionMode.REAL)
        assert rec.status == "FAILED"
        assert "allow_real_execution" in (rec.trace_id or "")

    def test_real_blocks_block_port(self, executor):
        p = _make_proposal(ActionType.BLOCK_PORT, port=22, requires_approval=True)
        rec = executor.execute(p, mode=ExecutionMode.REAL)
        assert rec.status == "FAILED"

    def test_real_blocks_rate_limit(self, executor):
        p = _make_proposal(ActionType.RATE_LIMIT, ip="10.0.0.5")
        rec = executor.execute(p, mode=ExecutionMode.REAL)
        assert rec.status == "FAILED"

    def test_real_alert_only_still_blocked_by_product_boundary(self, executor, monkeypatch):
        """即便 ALERT_ONLY / NO_ACTION 是 shell-safe，allow_real_execution=False 仍然拦。"""
        p = _make_proposal(ActionType.ALERT_ONLY)
        rec = executor.execute(p, mode=ExecutionMode.REAL)
        # Phase 11 先 allow_real_execution 门，再 action_type 门 → 这里 FAILED 是正确的
        assert rec.status == "FAILED"

    def test_real_no_action_still_blocked_by_product_boundary(self, executor):
        p = _make_proposal(ActionType.NO_ACTION)
        rec = executor.execute(p, mode=ExecutionMode.REAL)
        assert rec.status == "FAILED"

    def test_dry_run_never_calls_subprocess(self, executor, monkeypatch):
        """DRY_RUN 模式 subprocess.run 不应被调用。"""
        import subprocess
        p = _make_proposal(ActionType.BLOCK_IP, ip="10.0.0.5")

        called = {"n": 0}
        def _boom(*a, **kw):
            called["n"] += 1
            raise AssertionError("DRY_RUN should NOT call subprocess.run")

        monkeypatch.setattr(subprocess, "run", _boom)
        rec = executor.execute(p, mode=ExecutionMode.DRY_RUN)
        assert called["n"] == 0, "DRY_RUN must not invoke subprocess.run"
        assert rec.status == "SUCCEEDED"


# ===================================================================
# Category H: Executor._build_command 输出审计 — 命令本身不能有真实危险命令
# ===================================================================


class TestExecutedCommandSanity:
    """即便 guardrail 放行，echo 的命令本身也必须安全。Phase 11 改用 adapter."""

    def test_alert_only_plan_contains_echo(self):
        from app.adapters.backends import EchoBackend
        p = _make_proposal(ActionType.ALERT_ONLY)
        plan = EchoBackend().build(p, src_ip="10.0.0.5", dst_port=80)
        assert "echo" in plan.lower() or "alert" in plan.lower()

    def test_build_command_never_contains_shell_metachars(self):
        from app.adapters.backends import EchoBackend
        p = _make_proposal(ActionType.BLOCK_IP, ip="10.0.0.5")
        plan = EchoBackend().build(p)
        dangerous = [";", "|", "&", "`", "$(", "${"]
        for d in dangerous:
            assert d not in plan, f"plan={plan!r} contains dangerous shell char {d!r}"
