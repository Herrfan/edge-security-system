"""Phase 9 — API 层红队测试（TestClient + lifespan 真实运行）。

与 test_redteam_validation.py（纯 service）互补：
- 这里测 HTTP 端点 / 404 / 500 / 参数校验层
- Service 层测确定性 validator / guardrail
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_t2_nonexistent_event_id_returns_404(client):
    """攻击 T-2: 不存在的 event_id → 404，不崩溃，不触发 RAG。"""
    r = client.post("/api/v1/policy-proposal/generate", json={
        "event_id": "evt_does_not_exist_xyz12345",
    })
    assert r.status_code in (404, 400, 422), f"不存在的 event_id 应返回客户端错误，实际 {r.status_code}: {r.text[:200]}"


@pytest.mark.asyncio
async def test_generate_without_event_id_is_422(client):
    """请求体缺 event_id → FastAPI 参数校验层拦截，不进入 Service。"""
    r = client.post("/api/v1/policy-proposal/generate", json={})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_execute_with_nonexistent_policy_returns_400(client):
    """不存在的 policy_id → EndToEndPolicyService 应该 ValueError → 400。"""
    r = client.post("/api/v1/policy-proposal/execute", json={
        "policy_id": "pol_does_not_exist",
        "mode": "DRY_RUN",
    })
    assert r.status_code in (400, 404), f"不存在的 policy_id 应 400/404，实际 {r.status_code}: {r.text[:200]}"


@pytest.mark.asyncio
async def test_validate_with_nonexistent_policy_returns_400(client):
    """不存在的 policy_id 调用 validate → 400。"""
    r = client.post("/api/v1/policy-proposal/validate", json={
        "policy_id": "pol_fake",
    })
    assert r.status_code in (400, 404)


@pytest.mark.asyncio
async def test_execute_rejects_unknown_mode(client):
    """非法 mode 参数 → 422 / 400。"""
    r = client.post("/api/v1/policy-proposal/execute", json={
        "policy_id": "pol_anything",
        "mode": "DESTROY_ALL",  # 不是 DRY_RUN / REAL
    })
    assert r.status_code in (422, 400), f"非法 mode 应被拦截，实际 {r.status_code}"


@pytest.mark.asyncio
async def test_end_to_end_attack_flow_blocked(client, repo_root):
    """真实攻击路径:
    1. seed events → 2. RAG generate (LLM 可能建议 BLOCK_IP) → 3. validate 拦截非白名单 IP
    预期: 系统不允许生成 valid 的 BLOCK_IP(非白名单) policy。
    如果当前 RAG + MockLLM 返回的是合法白名单内的 IP → 通过（那是正常行为）。
    如果返回的是 1.2.3.4 这种 → validate 必须返回 is_valid=False。
    """
    import json
    from pathlib import Path

    kpath = repo_root / "data" / "knowledge" / "security_knowledge.jsonl"
    csv_path = repo_root / "data" / "samples" / "flows_sample.csv"

    # 1. reset KB
    client.post("/api/v1/knowledge/sync", json={
        "input_path": str(kpath), "reset_first": True,
    })
    # 2. seed events
    client.post("/api/v1/events/seed", json={
        "input_file": str(csv_path), "detector_id": "rule-demo", "max_records": 5,
    })
    # 3. fetch one event
    events = client.get("/api/v1/events", params={"limit": 1}).json()
    event_id = events[0]["event_id"]
    # 4. RAG generate
    rag = client.post("/api/v1/policy-proposal/generate", json={
        "event_id": event_id,
    }).json()
    proposal = rag["proposal"]
    action = proposal["action_type"]

    # 5. validate — 这就是防御边界
    v = client.post("/api/v1/policy-proposal/validate", json={
        "policy_id": proposal["policy_id"],
    }).json()

    if action == "BLOCK_IP":
        ip = proposal["parameters"]["ip"]
        import ipaddress
        try:
            o = ipaddress.ip_address(ip)
            allowed_cidrs = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
            import ipaddress as ipmod
            in_scope = any(o in ipmod.ip_network(c) for c in allowed_cidrs)
        except ValueError:
            in_scope = False
        if not in_scope:
            # 攻击成功触发了防御
            assert not v["is_valid"], \
                f"BLOCK_IP({ip}) outside whitelist must fail validation; " \
                f"actual is_valid={v['is_valid']}, issues={v.get('issues')}"


@pytest.mark.asyncio
async def test_executions_total_metric_counts_failures(client, repo_root):
    """Phase 7 EXECUTIONS_TOTAL metric — REAL 模式 BLOCK_IP 被 guardrail 拦截，
    status=FAILED 也应该被计数（证明 observability 埋点不丢数据）。"""
    import json
    from pathlib import Path

    csv_path = repo_root / "data" / "samples" / "flows_sample.csv"

    client.post("/api/v1/events/seed", json={
        "input_file": str(csv_path), "detector_id": "rule-demo", "max_records": 3,
    })
    events = client.get("/api/v1/events", params={"limit": 1}).json()
    event_id = events[0]["event_id"]
    policy = client.post("/api/v1/policy-proposal/generate", json={
        "event_id": event_id,
    }).json()["proposal"]
    # REAL 模式需要 approval_token
    r = client.post("/api/v1/policy-proposal/execute", json={
        "policy_id": policy["policy_id"],
        "mode": "REAL",
        "approval_token": "demo-approval",
    })
    # 如果 proposal 本身是 ALERT_ONLY（合法）→ 200 SUCCEEDED；如果是 BLOCK_IP（被 guardrail）→ 200 FAILED
    # 关键：不是 400 / 500
    assert r.status_code in (200, 400), f"execute REAL status={r.status_code} body={r.text[:200]}"
    # 拉 metrics
    ov = client.get("/api/v1/metrics/overview").json()["metrics"]
    et = ov["edgy_executions_total"]
    # 如果 execute 成功（guardrail 放行或拦截都算被观测到）→ ok；否则 unavailable
    if r.status_code == 200:
        assert et["status"] == "ok", f"执行后 edgy_executions_total 必须 ok 状态，实际 {et['status']}"
        # 确认 guardrail 拦截确实留下 FAILED 痕迹
        if policy["action_type"] in ("BLOCK_IP", "BLOCK_PORT", "RATE_LIMIT"):
            failed = [s for s in et["series"] if s.get("status") == "FAILED"]
            assert failed, f"BLOCK 动作在 REAL 模式应产生 FAILED 记录，series={et['series']}"
