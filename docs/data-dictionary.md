# 数据字典

MVP 原型包含的所有 Pydantic 领域模型 + SQLite 表字段说明。

## 1. FlowRecord（流量记录）

来自离线 CSV，一行 = 一条双向 TCP 流。

| 字段 | 类型 | 说明 |
|---|---|---|
| flow_id | str | 自动生成，前缀 `flow_` |
| src_ip | str | 源 IP（合成数据来自 `192.168.250.x` 攻击段） |
| dst_ip | str | 目的 IP（`10.0.0.x` 或 `172.16.x.x`） |
| src_port | int | 源端口 |
| dst_port | int | 目的端口（22 / 3389 / 443 / 80 等） |
| protocol | str | "TCP" / "UDP" |
| duration_ms | float | 流持续毫秒数 |
| packets_src_to_dst | int | A→B 包数 |
| packets_dst_to_src | int | B→A 包数 |
| bytes_src_to_dst | int | A→B 字节 |
| bytes_dst_to_src | int | B→A 字节 |

## 2. SecurityEvent（安全事件）

检测器输出 + SQLite 持久化。

| 字段 | 类型 | 说明 |
|---|---|---|
| event_id | str | 前缀 `evt_` |
| asset_id | str | 资产标识（phase 2 demo 默认 `"asset-demo"`） |
| flow_id | str \| None | 关联 FlowRecord |
| predicted_label | str | `"brute_force"` / `"port_scan"` / `"normal"` |
| score | float | 0..1 置信度 |
| severity | Severity | INFO / MEDIUM / HIGH / CRITICAL |
| model_id | str | `"rule-demo"` 或 `"sklearn-baseline-logreg"` |
| model_version | str | 如 `"v1-demo"` |
| evidence_summary | str \| None | 简短描述 |
| status | str | 生命周期：NEW / INVESTIGATING / CLOSED |
| trace_id | str \| None | 关联执行 / 策略的链路 ID |

## 3. PolicyProposal（策略候选）

RAG 输出 + 持久化。

| 字段 | 类型 | 说明 |
|---|---|---|
| policy_id | str | 前缀 `pol_` |
| event_id | str | 触发该策略的 SecurityEvent |
| action_type | ActionType | ALERT_ONLY / BLOCK_IP / BLOCK_PORT / RATE_LIMIT |
| parameters | BaseModel | BlockIpParams / BlockPortParams / RateLimitParams / NoActionParams（Shape Union） |
| risk_level | Severity | |
| rationale | str | LLM / 人类可读的理由 |
| evidence_ids | list[str] | 关联 Evidence 的 document_id + chunk_id |
| ttl_seconds | int | ∈ [60, 604800]，默认 3600 |
| status | PolicyStatus | NEEDS_VALIDATION / NEEDS_APPROVAL / EXECUTED / REJECTED |
| requires_approval | bool | 管理端口或高风险动作强制 True |

## 4. ExecutionRecord（执行记录）

执行器输出。

| 字段 | 类型 | 说明 |
|---|---|---|
| execution_id | str | 前缀 `exe_` |
| policy_id | str | 关联 PolicyProposal |
| mode | ExecutionMode | DRY_RUN / REAL |
| started_at | datetime | UTC |
| finished_at | datetime \| None | UTC |
| status | ExecutionStatus | UNKNOWN / SUCCEEDED / FAILED / ROLLED_BACK |
| stdout_summary | str \| None | 最多 2000 字符，MASKED |
| stderr_summary | str \| None | 最多 2000 字符，MASKED |
| rollback_status | str \| None | "SUCCEEDED" / "FAILED" / "N/A" |
| trace_id | str \| None | 目标 + guardrail 状态 |

## 5. Evidence（证据封装）

RAG 从知识库取回的 chunk 封装。

| 字段 | 类型 | 说明 |
|---|---|---|
| document_id | str | 知识库文档 ID（CVE / ATT&CK / IOC） |
| chunk_id | str | chunk 序号 |
| source | str | `"CVE"` / `"ATTACK"` / `"IOC"` |
| title | str | 文档标题 |
| content | str | chunk 文本（最多 2000 字符） |
| retrieval_method | str | `"keyword"` / `"vector"` / `"hybrid"` |
| retrieval_score | float | 0..1 |

## 6. Knowledge chunk（sqlite-vec 内部 schema）

VecIndex 在 sqlite-vec 中维持两张表：

```sql
CREATE TABLE knowledge_chunks (
  rowid INTEGER PRIMARY KEY,
  chunk_id TEXT,          -- 唯一
  document_id TEXT,
  source TEXT,            -- CVE / ATTACK / IOC
  source_ref TEXT,        -- 外部引用，如 "CVE-2024-12345"
  title TEXT,
  content TEXT,
  feature_schema_version TEXT
);

CREATE VIRTUAL TABLE vec0 USING vec0(
  embedding float32[768]
);
```

每一行 `vec0.rowid` 对应 `knowledge_chunks.rowid`。

## 7. Metrics（可观测性）

Phase 7 注册了 19 个指标，详见 `/api/v1/metrics/overview`。

| 分组 | 指标 | 类型 |
|---|---|---|
| Info | edgy_info | Gauge |
| Detection | edgy_detections_total, edgy_detection_latency_ms, edgy_events_seeded_total | Counter / Histogram |
| Retrieval | edgy_retrieval_calls_total, edgy_retrieval_latency_ms, edgy_retrieval_hits_per_query | Counter / Histogram |
| RAG | edgy_rag_runs_total, edgy_rag_total_latency_ms, edgy_rag_llm_latency_ms, edgy_rag_evidence_count | Counter / Histogram |
| Validation | edgy_policy_validations_total | Counter |
| Executor | edgy_executions_total, edgy_execution_latency_ms, edgy_executions_inflight | Counter / Histogram / Gauge |
| KB | edgy_knowledge_chunks_total, edgy_knowledge_documents_total | Gauge |
| System | edgy_process_cpu_percent, edgy_process_rss_bytes | Gauge |

## 8. 枚举值字典

### ActionType

| 值 | 说明 |
|---|---|
| ALERT_ONLY | 只告警，不改变网络状态 |
| BLOCK_IP | 封锁源 IP（需 CIDR 白名单） |
| BLOCK_PORT | 封锁端口（管理端口强制审批） |
| RATE_LIMIT | 限流（需 CIDR 白名单） |
| NO_ACTION | 不做任何动作 |

### PolicyStatus

| 值 | 说明 |
|---|---|
| NEEDS_VALIDATION | RAG 刚生成，待过 PolicyValidator |
| NEEDS_APPROVAL | Validator 通过 + DRY_RUN 执行过，待人工批准 |
| EXECUTED | REAL 执行成功 |
| REJECTED | Validator 拦截 + 或 REAL 执行失败 |

### Severity

INFO / LOW / MEDIUM / HIGH / CRITICAL

### ExecutionMode

DRY_RUN（默认）/ REAL

### ExecutionStatus

UNKNOWN / SUCCEEDED / FAILED / ROLLED_BACK

---

所有字段均在 Pydantic domain model 中声明为 `extra="forbid"`，不接受未声明字段。
