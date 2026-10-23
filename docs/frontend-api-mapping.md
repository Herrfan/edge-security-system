# 前端 API 契约映射表

> 对应规范 §6.3。登记所有前端可能用到的后端接口，明确**已验证 / 待联调 / 未实现**状态。
> 每条记录必须有**证据**（测试文件 / 前端已调用 / curl 验证）。

---

## 通用约定

| 项 | 约定 |
|---|---|
| Base URL | 开发期同源（前端挂载于 FastAPI `/static`），生产可走反向代理 |
| 统一前缀 | `/api/v1/*`；`/health`、`/metrics`、`/docs`、`/ui` 无前缀 |
| 认证 | 默认 auth_enabled=false；开启后需 `Authorization: Bearer <jwt>` |
| 响应格式 | 业务成功 → Pydantic model JSON；失败 → `{detail: "..."}` + HTTP status；health 返回 `{status, service, version, python}` |
| 时间字段 | ISO 8601 字符串（Python datetime.isoformat()） |
| 枚举字段 | 后端 Python Enum `.value` 小写或大写，前端展示层单独映射，**前端不直接把后端枚举值当展示文本** |
| 分页 | 仅 `limit` 参数支持；`offset/start_after` 后端暂不支持 |
| 搜索 | **后端无**关键词搜索参数；事件筛选仅 severity/status |

---

## 1. 系统与健康

### `GET /health` — 服务健康检查

| 项 | 值 |
|---|---|
| 前端使用 | ✅ Phase 15 顶栏状态指示器，20s 轮询 |
| 后端测试 | `tests/test_schemas/test_config.py` 间接覆盖 |
| 状态 | **已验证** |

**响应**
```json
{
  "status": "ok",
  "service": "edge-security-system",
  "version": "0.1.0",
  "python": "3.12.10",
  "pid": 12345
}
```

---

## 2. 安全事件

### `GET /api/v1/events?limit=&severity=&status=&predicted_label=` — 事件列表

| 项 | 值 |
|---|---|
| 前端使用 | ✅ Phase 15 "事件流" tab |
| 后端测试 | `tests/test_events/test_event_api.py::TestEventsAPI::test_list_events` |
| 状态 | **已验证** |

**查询参数**（均可选）
- `limit: int = 50`
- `severity: str` — `CRITICAL / HIGH / MEDIUM / LOW / INFO`
- `status: str` — 后端 status 枚举值
- `predicted_label: str` — 事件类型筛选

**不支持**：offset / 关键词搜索 / 时间范围 / 排序 → 前端必须标注"不支持搜索，仅下拉筛选"

**响应** `List[SecurityEvent]`

### `GET /api/v1/events/{event_id}` — 事件详情

| 项 | 值 |
|---|---|
| 前端使用 | ❌ Phase 15 未接入 |
| 后端测试 | `tests/test_events/test_event_api.py::TestEventsAPI::test_get_event` |
| 状态 | **已验证（后端）/ 待联调（前端）** |

**响应** `SecurityEvent`（完整字段，见数据字典）

### `POST /api/v1/events/seed` — 批量生成事件（开发辅助）

| 项 | 值 |
|---|---|
| 前端使用 | ❌ |
| 后端测试 | `tests/test_events/test_event_api.py` 间接覆盖 |
| 状态 | **已验证** |

---

## 3. 流量与检测

### `POST /api/v1/flows/import` — 文件导入 + 批量检测

| 项 | 值 |
|---|---|
| 前端使用 | ❌ Phase 15 未接入（只有 flows/seed-policy 手动传路径） |
| 后端测试 | `tests/test_detection/test_api.py::TestImportAPI::test_import_csv` |
| 状态 | **已验证（后端）/ 待联调（前端）** |

**请求**：multipart/form-data 文件上传

**响应** `IngestionSummary`
```json
{
  "imported_flows": 3000,
  "events_created": 3000,
  "detector_used": "rule_demo",
  "detector_version": "0.1.0"
}
```

### `POST /api/v1/flows/seed-policy?path=` — 从 CSV 批量导入（开发辅助）

| 项 | 值 |
|---|---|
| 前端使用 | ✅ Phase 15 "导入 flows_sample.csv" 按钮 |
| 状态 | **已验证** |

### `POST /api/v1/detection/predict` — 单次检测

| 项 | 值 |
|---|---|
| 前端使用 | ❌ |
| 状态 | **已验证**（Phase 2 后端实现，但前端场景下一般走 flows/import 批量） |

### `POST /api/v1/detection/train` — 训练检测模型

| 项 | 值 |
|---|---|
| 前端使用 | ❌ |
| 状态 | **已验证（后端）/ 前端不接入**（生产安全边界：训练属于离线操作） |

---

## 4. 知识库与检索

### `POST /api/v1/knowledge/sync` — 知识库同步到 sqlite-vec

| 项 | 值 |
|---|---|
| 前端使用 | ❌ Phase 15 未接入 |
| 后端测试 | `tests/test_retrieval/test_retrieval_api.py::TestKnowledgeSyncAPI` |
| 状态 | **已验证** |

**请求体**
```json
{
  "input_path": "data/knowledge",
  "reset_first": false,
  "provider": "ollama | mock"
}
```

**响应**
```json
{
  "documents": 12,
  "chunks": 156,
  "provider": "ollama"
}
```

### `POST /api/v1/retrieval` — 混合检索

| 项 | 值 |
|---|---|
| 前端使用 | ❌ Phase 15 未接入 |
| 后端测试 | `tests/test_retrieval/test_retrieval_api.py::TestRetrievalAPI::test_search_hybrid` |
| 状态 | **已验证** |

**请求体**
```json
{
  "query": "brute force ssh",
  "mode": "hybrid | keyword | vector",
  "top_k": 5
}
```

**响应**
```json
{
  "status": "OK | EMPTY | ERROR",
  "mode": "hybrid",
  "hits": [
    {"rowid": 1, "score": 0.82, "rank": 1}
  ]
}
```

### `GET /api/v1/retrieval/status` — 检索服务状态

| 项 | 值 |
|---|---|
| 前端使用 | ❌ |
| 状态 | **已验证** |

### `GET /api/v1/retrieval/{retrieval_id}` — 检索结果详情

| 项 | 值 |
|---|---|
| 前端使用 | ❌ |
| 状态 | **已验证** |

---

## 5. 策略工作台

### `POST /api/v1/policy-proposal/generate` — RAG 生成策略候选

| 项 | 值 |
|---|---|
| 前端使用 | ❌ Phase 15 未接入（demo_e2e 里调用但前端没按钮） |
| 后端测试 | `tests/test_rag/test_rag_e2e.py::TestRAGEndToEnd::test_full_flow` |
| 状态 | **已验证** |

**请求体**
```json
{"event_id": "evt_xxx"}
```

**响应**
```json
{
  "proposal": {
    "policy_id": "pol_xxx",
    "action_type": "BLOCK_IP",
    "parameters": {"ip": "192.168.1.100", "ttl_seconds": 3600},
    "risk_level": "HIGH",
    "rationale": "LLM 生成理由",
    "status": "NEEDS_APPROVAL",
    "requires_approval": true,
    "event_id": "evt_xxx",
    "evidence_ids": ["doc_1:chunk_3", "doc_2:chunk_7"],
    "ttl_seconds": 3600
  },
  "evidences": [
    {"document_id": "...", "chunk_id": "...", "content": "...", "retrieval_method": "hybrid", "retrieval_score": 0.82}
  ],
  "evidence_count": 2,
  "retrieval_status": "OK",
  "llm_provider": "ollama:qwen2.5:3b",
  "llm_is_mock": false,
  "llm_latency_ms": 30501.42
}
```

### `POST /api/v1/policy-proposal/validate` — 确定性校验

| 项 | 值 |
|---|---|
| 前端使用 | ❌ Phase 15 未接入 |
| 后端测试 | `tests/test_policy/test_policy.py::TestPolicyService::test_validate` |
| 状态 | **已验证** |

**请求体**
```json
{
  "policy_id": "pol_xxx",
  "src_ip": "192.168.1.100",   // 可选（executor resolve 用）
  "dst_port": 22               // 可选
}
```

**响应**
```json
{
  "policy_id": "pol_xxx",
  "is_valid": true,
  "reasons": ["CIDR OK", "TTL OK", "Port 22 requires_approval=true"]
}
```

### `POST /api/v1/policy-proposal/approve` — 审批 / 驳回

| 项 | 值 |
|---|---|
| 前端使用 | ✅ Phase 15 "Approve ✓ / Reject ✗" 按钮 |
| 后端测试 | **需要补**（Phase F0 未发现专门的 approve API 测试） |
| 状态 | **已实现（路由）/ 缺专门测试 / 待前端完整联调** |

**请求体**
```json
{
  "policy_id": "pol_xxx",
  "approve": true,
  "reason": "风险可控，允许 24h 临时封禁",   // 可选
  "approver": "alice@security.local",        // 可选
  "approval_token": "shared-secret"          // 可选（MVP 预共享）
}
```

**响应**
```json
{
  "policy_id": "pol_xxx",
  "status": "APPROVED",   // APPROVED 或 REJECTED
  "approver": "alice@security.local",
  "reason": "..."
}
```

**错误码**
| status | 条件 |
|---|---|
| 404 | policy_id 不存在 |
| 409 | 当前状态不是 NEEDS_APPROVAL（不能重复 approve / approve 已 REJECTED） |

### `POST /api/v1/policy-proposal/execute` — 执行（默认 Dry-run）

| 项 | 值 |
|---|---|
| 前端使用 | ✅ Phase 15 "▶ DRY_RUN execute" 按钮 |
| 后端测试 | `tests/test_policy/test_policy.py::TestPolicyValidateExecuteAPI::test_full_flow` + Phase 9 红队测试 |
| 状态 | **已验证** |

**请求体**
```json
{
  "policy_id": "pol_xxx",
  "mode": "DRY_RUN",   // 或 REAL，但 REAL 被 allow_real_execution 硬边界拦截
  "approval_token": "..."   // 可选
}
```

**响应**
```json
{
  "execution_id": "exe_xxx",
  "policy_id": "pol_xxx",
  "mode": "DRY_RUN",
  "status": "SUCCEEDED",
  "started_at": "...",
  "finished_at": "...",
  "stdout_summary": "...",
  "stderr_summary": null,
  "rollback_status": "N/A",
  "trace_id": "guardrail=phase6_action",   // 可能的 trace 值
  "duration_ms": 23.45,
  "validator_reasons": ["CIDR OK", ...]
}
```

### `GET /api/v1/policy-proposals?status=&limit=` — 策略列表

| 项 | 值 |
|---|---|
| 前端使用 | ✅ Phase 15 "待审批策略" + "全部策略" 两个 tab |
| 后端测试 | `tests/test_policy/test_policy.py` 覆盖 list |
| 状态 | **已验证** |

**查询参数**（均可选）
- `status: PolicyStatus enum value` — `NEEDS_APPROVAL / APPROVED / REJECTED / EXECUTED / NEEDS_VALIDATION / EXPIRED / DRAFT`
- `limit: int = 50`

**响应** `List[PolicyProposal]`

---

## 6. 可观测性

### `GET /metrics` — Prometheus 文本格式

| 项 | 值 |
|---|---|
| 前端使用 | ❌ Phase 15 未接入（overview 已覆盖卡片） |
| 状态 | **已验证** |

### `GET /api/v1/metrics/overview` — 结构化指标总览

| 项 | 值 |
|---|---|
| 前端使用 | ✅ Phase 15 "指标" tab |
| 后端测试 | `tests/test_observability/test_metrics_api.py::TestOverviewAPI` |
| 状态 | **已验证** |

**响应**
```json
{
  "info": {"service": "...", "version": "..."},
  "system": {
    "cpu_percent": 12.3,
    "rss_bytes": 123456789,
    "status": "OK"   // 或 "UNAVAILABLE"（psutil 未装）
  },
  "config": {
    "llm_model": "qwen2.5:3b",
    "embedding_model": "nomic-embed-text",
    "allow_real_execution": false,
    ...
  },
  "metrics": {
    "edgy_detections_total": {"series": [{"value": 3000, "detector": "rule_demo"}]},
    "edgy_rag_runs_total": {"series": [{"value": 10, "llm_is_mock": false}]},
    ...
  }
}
```

### `GET /api/v1/metrics/export?format=csv` — CSV / JSON 导出

| 项 | 值 |
|---|---|
| 前端使用 | ❌ |
| 状态 | **已验证** |

---

## 7. 尚未实现但规范要求的 API（前端必须展示"未接入"占位）

| 规范章节 | 能力 | 说明 |
|---|---|---|
| §4.7 审计日志 | 审计日志查询 API | 后端无；Phase F5 前只能占位 |
| §4.2 流量分析 | 检测任务生命周期 API（pending/running/done） | 后端 detection 是一次性调用 |
| §4.3 安全事件 | 事件状态变更 API（acknowledge / resolve） | 后端有 status 字段但没 PATCH 端点 |
| §4.6 评估中心 | 实验管理 API | 后端无 |
| §7 交互 | 关键词搜索 / 时间范围筛选 / 排序 | 后端无 |

---

## 8. API 契约变更历史（Phase F0 后每次接口改动必须登记）

| 日期 | 变更 | 影响 | 负责人 |
|---|---|---|---|
| 2026-10-22 | 新增 `POST /api/v1/policy-proposal/approve` | Phase 15 | Agent |

---

## 9. 前端联调 Checklist（Phase F1 后逐条执行）

- [ ] `/health` 顶栏轮询 OK
- [ ] `/api/v1/events` 列表 + 筛选 OK
- [ ] `/api/v1/events/{id}` 详情 OK（F2）
- [ ] `/api/v1/flows/import` 文件上传 OK（F3）
- [ ] `/api/v1/knowledge/sync` 触发 OK（F2）
- [ ] `/api/v1/retrieval` 检索 OK（F2）
- [ ] `/api/v1/policy-proposal/generate` 完整 RAG 触发 OK（F2）
- [ ] `/api/v1/policy-proposal/validate` 校验 OK（F2）
- [ ] `/api/v1/policy-proposal/approve` 审批 OK（F2）
- [ ] `/api/v1/policy-proposal/execute` Dry-run OK（F2）
- [ ] `/api/v1/policy-proposals` 列表 + 状态筛选 OK（F2）
- [ ] `/api/v1/metrics/overview` 指标卡 OK（F1）
- [ ] 审计日志 API — **未实现，占位**（F4/F5 阻塞）
- [ ] 检测任务 API — **未实现，占位**（F3 阻塞）
