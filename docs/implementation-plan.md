# Phase 0 实施计划

**基于**：`docs/audit-report.md` 审计结论  
**目标**：在确认审计结论后，分阶段搭建 MVP 原型  
**原则**：最小增量、每阶段可验证、默认 dry-run、不引入无必要依赖

---

## 0. 前置动作（建议在 Phase 1 之前完成）

| 序号 | 动作 | 理由 |
|---|---|---|
| 0.1 | `git init` + 建立 `.gitignore` | 版本控制是所有后续工作的前提 |
| 0.2 | 验证 Ollama 服务可用性：`ollama run qwen2.5:3b "ping"` | 未通过则 Phase 4/5 受阻 |
| 0.3 | 获取/生成小型样例流量数据集（500-2000 条带标签流记录） | Phase 2 检测基线需要真实标签 |
| 0.4 | 确认 CPU 内存 >= 8GB（3B 模型 CPU 推理约需 4-6GB） | 内存不足时需要降级模型策略 |

---

## 1. 推荐开发顺序（Phase 1 → Phase 8）

```
Phase 1  项目骨架与数据契约      ← 立即开始
   ↓
Phase 2  离线流量导入与检测基线    ← 依赖 Phase 1 的数据契约
   ↓
Phase 3  事件管理与存储           ← 依赖 Phase 2 的检测输出
   ↓
Phase 4  安全知识库与混合检索      ← 可与 Phase 2/3 部分并行
   ↓
Phase 5  RAG 证据封装与策略生成    ← 依赖 Phase 4 的检索能力
   ↓
Phase 6  策略校验、审批与 dry-run  ← 依赖 Phase 5 的策略结构
   ↓
Phase 7  反馈与可观测性           ← 贯穿全链路
   ↓
Phase 8  集成演示与文档           ← 收尾
```

### 并行可能性

- **Phase 2（检测）与 Phase 4（检索）** 无直接依赖，可并行开发
- **Phase 7（可观测性）** 可在 Phase 3 后逐步嵌入每个服务

---

## 2. 各 Phase 详细计划

### Phase 1：项目骨架与数据契约

**目标**：建立可启动的空服务 + 全部数据模型 + 测试框架

**预计新增文件**：

```
edge-security-system/
├── .gitignore
├── README.md                         (运行说明，不含性能承诺)
├── .env.example                      (不含真实密钥)
├── pyproject.toml                    (依赖声明)
├── docs/
│   ├── architecture.md               (首版架构图与模块边界)
│   ├── api-spec.md                   (数据契约与 API 清单)
│   └── test-plan.md
├── app/
│   ├── __init__.py
│   ├── main.py                       (FastAPI app + health)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                 (pydantic-settings)
│   │   ├── logging.py                (脱敏 Filter)
│   │   └── errors.py                 (统一错误码)
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── flow.py                   (FlowRecord)
│   │   ├── event.py                  (SecurityEvent)
│   │   ├── evidence.py               (Evidence)
│   │   ├── policy.py                 (PolicyProposal, ActionType enum)
│   │   └── execution.py              (ExecutionRecord)
│   └── api/
│       ├── __init__.py
│       └── health.py                 (GET /health)
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_schemas/
        ├── test_flow_record.py       (正反例)
        ├── test_security_event.py    (正反例)
        ├── test_evidence.py          (正反例)
        ├── test_policy_proposal.py   (正反例, 白名单校验)
        ├── test_execution_record.py  (正反例)
        └── test_config.py
```

**依赖清单（pyproject.toml）**：

```
fastapi>=0.115.0
uvicorn>=0.32.0
pydantic>=2.9.2
pydantic-settings>=2.5.2
SQLAlchemy>=2.0.35
aiosqlite>=0.20.0
python-multipart>=0.0.9
python-dotenv>=1.2.4
cryptography>=50.0.1
orjson>=3.12.0
psutil>=7.2.2
pytest>=8.4.2
pytest-asyncio>=1.4.0
```

**验收标准**：

| # | 验收项 | 通过条件 |
|---|---|---|
| A1-1 | 服务可启动 | `uvicorn app.main:app` 无异常 |
| A1-2 | GET /health 返回 200 | `{"status": "ok", "version": "..."}` |
| A1-3 | 所有 Schema 正例测试通过 | 每个模型至少 3 个正例 |
| A1-4 | 所有 Schema 反例测试拒绝 | 每个模型至少 5 个反例（缺失字段、类型错误、枚举外值） |
| A1-5 | `.env.example` 不含真实值 | 纯占位符 |
| A1-6 | `.gitignore` 覆盖 .env、__pycache__、*.db、*.log | — |
| A1-7 | 日志脱敏 Filter 测试 | IP、端口等敏感信息被遮罩 |

**测试命令**：

```bash
# 启动验证
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
curl http://127.0.0.1:8000/health

# Schema 测试
pytest tests/test_schemas/ -v
```

**验收边界**：本 Phase 不实现任何业务服务、数据库读写、检测器、检索、RAG。

---

### Phase 2：离线流量导入与检测基线

**目标**：可导入离线流数据 + 最小可运行检测器

**预计新增/修改文件**：

```
app/
├── api/routes/
│   ├── flows.py                      (POST /api/v1/flows/import)
│   └── detection.py                 (POST /api/v1/detection/predict)
├── services/
│   ├── ingestion.py                  (CSV/JSONL 导入 + polars)
│   ├── feature_pipeline.py           (字段映射 + 校验)
│   └── detection.py                  (Detector 接口 + RuleDemoDetector + SklearnBaseline)
└── adapters/dataset/
    └── csv_adapter.py                (polars 解析适配)

tests/
└── test_detection/
    ├── test_ingestion.py
    ├── test_feature_pipeline.py
    ├── test_rule_detector.py
    └── test_sklearn_baseline.py

data/
└── samples/
    └── (用户提供的样例数据，需 .gitignore 排除)

scripts/
└── evaluate_detection.py              (评估脚本，仅在有真实标签时输出指标)
```

**技术决策**：
- 先实现 `RuleDemoDetector`（明确标注为 demo，可检出已知端口扫描/暴力破解特征）
- 再实现 `SklearnBaselineDetector`（若有标签数据：StandardScaler + LogisticRegression 或小型 MLP）
- 数据用 polars 解析，输出标准化 FlowRecord

**验收标准**：

| # | 验收项 | 通过条件 |
|---|---|---|
| A2-1 | CSV 导入可处理缺失/错误字段 | 明确错误信息，不静默丢弃 |
| A2-2 | RuleDemoDetector 可运行 | 对固定输入返回可复现输出 |
| A2-3 | Sklearn 基线可训练和推理 | 同版本同输入可复现 |
| A2-4 | 特征版本不匹配报错 | feature_schema_version 不一致时返回明确错误 |
| A2-5 | 测试覆盖正常/异常/无效样本 | 至少各 3 例 |
| A2-6 | 无标签时评估脚本不输出 Precision/Recall | 明确标记"无真实标签" |

**风险点**：
- 若无样例数据，RuleDemoDetector 可先做 dry-run 自测，但 Sklearn 基线无法真实验证
- 若数据字段未知，需先对样例数据做字段探测

---

### Phase 3：事件管理与存储

**目标**：检测结果 → 安全事件 → 可查询

**预计新增/修改文件**：

```
app/
├── core/database.py                  (SQLAlchemy engine, session)
├── domain/event.py                   (补充 DB model)
├── repositories/
│   └── event_repository.py           (CRUD)
├── services/event_service.py         (检测结果 → SecurityEvent)
└── api/routes/events.py              (GET /api/v1/events, GET /api/v1/events/{id})

tests/
└── test_events/
    ├── test_event_repository.py
    └── test_event_service.py
```

**验收标准**：
- API 返回符合契约（统一错误格式）
- 事件可按 ID 查询、分页、按 severity/时间筛选
- 日志不含完整网络载荷

---

### Phase 4：安全知识库与混合检索

**目标**：可导入知识文档 + 关键词检索基线 + 可替换的向量检索适配器

**预计新增/修改文件**：

```
app/
├── services/
│   ├── knowledge_ingestion.py         (JSONL/MD 导入 + 切分 + 去重)
│   └── retrieval.py                  (KeywordRetriever + VectorRetriever + RRF)
├── adapters/embedding/
│   ├── base.py                       (EmbeddingProvider 抽象)
│   ├── ollama_embed.py               (nomic-embed-text)
│   └── mock_embed.py                 (不可用时降级)
└── api/routes/
    ├── knowledge.py                  (POST /api/v1/knowledge/sync)
    └── retrieval.py                  (GET /api/v1/retrieval/{id})

tests/
└── test_retrieval/
    ├── test_knowledge_ingestion.py
    ├── test_keyword_retriever.py
    ├── test_rrf_fusion.py
    ├── test_embedding_adapter.py
    └── test_vector_retriever.py      (mock/降级测试)
```

**技术决策**：
- 向量存储：**sqlite-vec**（已装 0.1.9）——SQLite 的向量扩展，避免新增大依赖
- 若 sqlite-vec 不可用：回退到 numpy + 余弦相似度基线
- 关键词检索：纯 Python BM25 实现（无需新依赖）
- Embedding：Ollama nomic-embed-text；不可用时用 mock（明确标记降级）

**验收标准**：
- 每条检索结果可追溯到真实文档和 chunk
- 未配置 vector backend 时返回 `retrieval_status=DEGRADED`
- 索引重建可复现
- RRF 融合逻辑有单元测试

**风险点**：
- Ollama 服务可能不可用 → 需 mock 测试
- 若无知识文档，本 Phase 只能空跑

---

### Phase 5：RAG 证据封装与策略候选生成

**目标**：事件 + 证据 → 结构化候选策略

**预计新增/修改文件**：

```
app/
├── services/
│   └── rag_service.py                (上下文组装 + Prompt + 输出解析)
├── adapters/llm/
│   ├── base.py                       (LLMProvider 抽象)
│   ├── ollama_llm.py                 (qwen2.5:3b/7b)
│   └── mock_llm.py                   (不可用时降级)
├── api/routes/
    └── analyze.py                    (POST /api/v1/events/{id}/analyze)

tests/
└── test_rag/
    ├── test_context_building.py
    ├── test_output_schema_validation.py
    ├── test_evidence_id_binding.py    (伪造 evidence_id 拒绝)
    └── test_llm_timeout.py
```

**技术决策**：
- LLM 只输出 JSON，不执行命令
- 解析失败/超时/证据不足 → 明确返回状态，不伪造

**验收标准**：
- 候选策略的 evidence_ids 均来自本次真实检索
- 无证据 → 不生成可执行策略
- LLM 无 Shell 权限
- 负面测试：伪造 CVE/ATT&CK、伪造 evidence_id、非法 action_type

---

### Phase 6：策略校验、审批与 dry-run 执行

**目标**：独立确定性校验 + 模拟执行器 + 回滚

**预计新增/修改文件**：

```
app/
├── core/
│   └── security.py                   (白名单、授权范围、TTL 配置)
├── services/
│   ├── policy_validator.py           (10 条硬约束)
│   ├── approval_service.py           (人工审批状态机)
│   └── executor.py                   (DryRunExecutor + rollback)
├── api/routes/
    ├── policies.py                   (validate, approve, execute)
    └── executions.py                 (rollback)

tests/
└── test_policy/
    ├── test_validator_whitelist.py
    ├── test_validator_evidence.py
    ├── test_validator_ttl.py
    ├── test_dry_run_executor.py
    ├── test_rollback.py
    ├── test_idempotency.py
    └── test_unauthorized_target.py
```

**验收标准**：
- 越权/过期/伪造证据/未审批 → 拒绝
- 重复请求不重复应用动作（幂等）
- dry-run 明确标记为模拟
- 回滚覆盖成功与失败路径

---

### Phase 7：反馈与可观测性

**目标**：全链路延迟/指标记录

**预计新增/修改文件**：

```
app/
├── services/feedback.py
├── core/observability.py             (Prometheus-style 埋点)
└── api/routes/metrics.py

tests/
└── test_observability/
```

**验收标准**：
- 指标从真实运行日志计算
- 缺失指标标记为 unavailable
- 每条结果可追溯到模型/知识库/配置版本

---

### Phase 8：集成演示与文档

**目标**：端到端可复现

**预计新增/修改文件**：

```
docs/
├── test-report.md                    (真实测试结果)
├── threat-model.md
└── data-dictionary.md

scripts/
└── demo_e2e.py                       (一键端到端)

README.md                             (更新为完整运行说明)
```

**验收标准**：
- 新环境按 README 可启动
- 演示不依赖手工步骤
- 性能报告仅含真实测量值
- 未测指标标记"待验证"

---

## 3. 跨 Phase 通用约束

### 3.1 新增依赖原则

| 场景 | 策略 |
|---|---|
| 环境已装依赖 | 直接使用，不改版本 |
| 有轻量替代（polars 代 pandas、sqlite-vec 代 FAISS） | 优先替代 |
| 必须新增 | 单 Phase 引入，提前告知 |
| 大型模型/向量库 | 暂停，单独评估 |

### 3.2 不做清单

- ❌ 不接真实防火墙/网络设备
- ❌ 不扫生产网
- ❌ 不自动训练/发布模型
- ❌ 不拆微服务
- ❌ 不引入 Docker（除非后续明确要求）
- ❌ 不声称未实测的性能达标
- ❌ 不把 mock 输出伪装成真实模型

### 3.3 每阶段交付格式

每个 Phase 结束后按任务书 §8 模板输出：

1. 阶段结论（PASS / PARTIAL / BLOCKED）
2. 修改文件清单
3. 真实实现内容
4. 测试命令与结果
5. 安全检查
6. 未解决问题
7. 性能结果（仅实测）
8. 文档同步状态
9. Git 状态
10. 下一阶段建议

---

## 4. 阻塞项前置排查清单

在开始 Phase 1 前，建议先确认以下事项：

- [ ] 是否同意用 `sqlite-vec` 作为向量存储（已装，无额外依赖）
- [ ] 是否同意用 `polars` 替代 `pandas`（数据处理）
- [ ] 是否有或可获取带标签的小型流量数据集（Phase 2 Sklearn 基线需要）
- [ ] 是否有或可准备安全知识文档（Phase 4 需要——如 CVE 条目、ATT&CK 说明、常见威胁描述）
- [ ] Ollama 服务是否在运行，`ollama run qwen2.5:3b "ping"` 延迟可接受
- [ ] 是否执行 `git init` 建立版本控制
- [ ] CPU 可用内存是否 >= 8GB

以上确认后，即可进入 Phase 1。

---

## 5. 风险缓解速查表

| 风险 | 缓解动作 |
|---|---|
| Ollama 服务挂了 | 所有 LLM/Embedding 调用均需 Mock Provider 降级；降级状态明确返回 |
| 内存不足跑不动 7B | Phase 5 强制优先 3B；若仍不足，Mock LLM |
| 向量检索不可用 | Keyword-only 基线；明确 `retrieval_status=DEGRADED` |
| 无标签数据 | 仅交付 RuleDemoDetector，Sklearn 基线标记"待真实数据" |
| 无知识文档 | Phase 4 先做框架，导入少量 CVE 公开条目 |
| Windows 特定路径/权限 | 所有数据路径走配置，不硬编码 |

---

*本计划基于审计报告的真实发现。若前置排查中出现新阻塞项，将在 Phase 1 开始前更新。*
