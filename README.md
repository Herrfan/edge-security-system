# Edge Security System（边缘网络安全系统 · AI 编程工具）

基于 RAG 与轻量级 AI 的边缘网络安全态势感知与自适应防御系统 —— MVP 原型。

**项目状态：Phase 8（集成演示与文档）已完成**，全部核心链路可跑通。

## 功能总览

| Phase | 模块 | 状态 |
|---|---|---|
| 1 | 骨架 / 配置 / 日志 / 错误处理 / 数据契约 | ✅ |
| 2 | 离线流量导入 + 检测基线（RuleDemo + SklearnBaseline） | ✅ |
| 3 | SQLite 异步存储 + EventRepository | ✅ |
| 4 | 知识库与混合检索（sqlite-vec + BM25 + RRF） | ✅ |
| 5 | RAG 证据封装 + 策略候选生成（qwen2.5:3b） | ✅ |
| 6 | 策略校验 + dry-run 执行器 | ✅ |
| 7 | 反馈与可观测性（Prometheus-compatible metrics） | ✅ |
| 8 | 集成演示 + 本机测试 + 文档 | ✅ |

## 快速开始

```bash
# 1. 安装依赖（首次）
pip install -e ".[dev]"

# 2. 确认 Ollama 已启动，模型已拉取
ollama pull qwen2.5:3b
ollama pull nomic-embed-text

# 3. 启动服务
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 4. 打开 API 文档
#    http://127.0.0.1:8000/docs
```

## 一键端到端演示（推荐）

```bash
python scripts/demo_e2e.py --steps 10
```

脚本将依次执行：

1. 知识库同步（15 文档 → 16 chunks）
2. 离线 CSV 流量导入 + 规则检测
3. RAG 策略候选生成（检索 → 证据封装 → LLM 输出）
4. 确定性策略校验（CIDR / 端口 / TTL 白名单）
5. **DRY_RUN** 执行（安全 echo，不触达任何网络资产）
6. 可观测性快照

结束后自动生成 `data/demo_report.json`。

## 本机性能基准

```bash
python scripts/benchmark.py
# → data/benchmark_report.json
```

### 实测数据（开发机：Intel N100 四核 / 16GB / 本地 CPU 推理）

| 项 | 实测值 |
|---|---|
| 端到端 wall clock | ~32.5 s（含 LLM CPU 推理） |
| 知识库同步 | ~8.7 s |
| events 导入 + 检测 | ~1.0 s |
| **RAG 含 LLM** | ~30.5 s（qwen2.5:3b，CPU） |
| DRY_RUN execute | < 1 ms |
| Ollama 模型：qwen2.5:3b | 1.93 GiB |
| Ollama 模型：nomic-embed-text | 274 MB |
| RSS（benchmark.py 本身） | ~35 MB |

**未测指标（任务书要求显式标记）**

- 边缘设备端到端延迟（当前仅在开发机跑，未上目标设备）
- 并发压测 RPS（未做）
- GPU 推理延迟（本机无 GPU）
- 真实防火墙 / iptables 集成（安全边界禁止）

## 跑测试

```bash
python -m pytest -q
# 预期：176 passed, 0 failed
```

## API 端点

| Method | Path | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| GET | `/api/v1/events?limit=N` | 查询事件 |
| POST | `/api/v1/events/seed` | CSV 导入 + 检测 |
| POST | `/api/v1/knowledge/sync` | 知识库同步 |
| GET | `/api/v1/retrieval` | 关键词 / 向量 / hybrid 检索 |
| POST | `/api/v1/policy-proposal/generate` | RAG 策略生成 |
| POST | `/api/v1/policy-proposal/validate` | 确定性策略校验 |
| POST | `/api/v1/policy-proposal/execute` | DRY_RUN / REAL 执行 |
| GET | `/api/v1/policy-proposals` | 策略列表 |
| GET | `/api/v1/metrics` | **Prometheus 文本格式**（可直接 scrape） |
| GET | `/api/v1/metrics/overview` | JSON 快照（含版本 + config trace） |
| GET | `/api/v1/metrics/export?format=csv` | CSV 导出 |

## 项目结构

```
app/
├── main.py                       FastAPI 入口（lifespan + mark_info_gauges）
├── core/
│   ├── config.py                 Pydantic Settings + lru_cache
│   ├── database.py               SQLAlchemy 2.0 async engine + 4 张 ORM
│   ├── logging.py                RedactionFilter + 结构化日志
│   ├── errors.py                 ErrorEnvelope + 统一 400/500 handler
│   └── observability.py          Counter / Gauge / Histogram（零依赖，Prometheus-compatible）
├── domain/                       数据契约（Pydantic v2，extra="forbid"）
│   ├── common.py                 ActionType / PolicyStatus / ExecutionMode / _new_id / utcnow
│   ├── flow.py                   FlowRecord
│   ├── event.py                  SecurityEvent
│   ├── evidence.py               Evidence（RAG 证据封装）
│   ├── policy.py                 PolicyProposal + 参数 Shape Union
│   └── execution.py              ExecutionRecord
├── adapters/
│   ├── embedding/base.py         EmbeddingProvider（Ollama / Mock）
│   └── llm/base.py               LLMProvider（Ollama / Mock + _parse_json_tolerant）
├── repositories/                 Event / Flow / Policy / Execution
├── services/
│   ├── detection.py              RuleDemoDetector + SklearnBaselineDetector
│   ├── feature_pipeline.py       Flow → 数值特征
│   ├── ingestion.py              CSV → FlowRecord
│   ├── knowledge_ingestion.py    JSONL → chunk → embed → sqlite-vec
│   ├── retrieval.py              VecIndex + BM25Index + RRF
│   ├── rag_service.py            Event → Retrieval → LLM → PolicyProposal
│   ├── prompt_manager.py         Prompt 模板 + build_prompt
│   ├── policy_validator.py       确定性校验（CIDR / 端口 / TTL）
│   ├── executor.py               DRY_RUN 默认，REAL 有 guardrail
│   ├── policy_service.py         EndToEndPolicyService 编排
│   └── feedback.py               mark_info_gauges / snapshot_knowledge_gauges / feedback_summary
└── api/routes/
    ├── health.py
    ├── detection.py
    ├── events.py
    ├── retrieval.py
    ├── policy.py
    └── metrics.py

scripts/
├── generate_sample_data.py       合成 3 类攻击流量
├── generate_knowledge.py          生成知识 JSONL
├── demo_e2e.py                   ★ Phase 8 一键演示
└── benchmark.py                   ★ Phase 8 本机性能基准

data/                             (gitignore：sqlite / 向量索引 / demo 报告)
├── samples/flows_sample.csv
├── knowledge/security_knowledge.jsonl
├── demo_report.json              ← demo_e2e.py 输出
└── benchmark_report.json         ← benchmark.py 输出
```

## 技术栈

| 组件 | 版本 / 实现 | 说明 |
|---|---|---|
| Python | 3.12 | — |
| FastAPI | latest | 异步 + lifespan |
| Pydantic | v2 | 领域模型 + 参数 Shape Union |
| SQLAlchemy | 2.0 | async + aiosqlite |
| polars | latest | CSV 处理（可选） |
| scikit-learn | latest | 检测基线 LogisticRegression |
| numpy | latest | 向量化 + BM25 |
| sqlite-vec | 0.1.9 | vec0 虚拟表，768-dim KNN |
| Ollama | local | qwen2.5:3b LLM + nomic-embed-text embedding |
| **Observability** | **自实现** | Counter/Gauge/Histogram，零新依赖 |

## 安全边界（红线）

1. **默认 DRY_RUN**：所有策略执行只 echo，不触达任何系统
2. **REAL 有 guardrail**：Block_IP / BLOCK_PORT / RATE_LIMIT 在 REAL 模式被拦截，只允许 ALERT_ONLY / NO_ACTION shell-safe 命令
3. **CIDR 白名单**：BLOCK_IP / RATE_LIMIT 参数 IP 必须在 `10.0.0.0/8 / 172.16.0.0/12 / 192.168.0.0/16` 内
4. **管理端口强制审批**：dst_port ∈ {22, 3389, 5985, 5986, 8443} 必须 `requires_approval=True`
5. **不扫描生产网**：所有流量来自合成 CSV
6. **不自动训练模型**：SklearnBaselineDetector 是 on-the-fly 训练，无持久化 checkpoint
7. **不伪装 mock 输出**：LLM / embedding 是 mock 时 RAGResult.surface DEGRADED

## 已知限制

| 项 | 限制 | 计划 |
|---|---|---|
| 执行后端 | 只有 echo dry-run，无真实防火墙集成 | Phase 9+ |
| 指标持久化 | 进程内 registry，重启归零 | Phase 9+ 加 SQLite / Prometheus remote-write |
| 检测模型 | RuleDemo 是 hand-tuned 规则，SklearnBaseline 无预训练 | 后续接入真实 IDS 输出 |
| 并发 | 单进程 FastAPI 开发服务 | 生产部署需 uvicorn workers + Gunicorn |
| 异步模型 | SQLAlchemy async engine + aiosqlite；但 VecIndex / BM25 / Executor 是 sync | 可接受 — 推理 / 执行本身是重 CPU / 阻塞 |

## 文档

- [开发任务书](边缘网络安全系统_AI编程工具开发任务书.md)
- [Phase 0 审计报告](docs/audit-report.md)
- [Phase 1-8 实施计划](docs/implementation-plan.md)
- [威胁模型](docs/threat-model.md) ★ Phase 8
- [数据字典](docs/data-dictionary.md) ★ Phase 8
- [测试报告（真实）](data/benchmark_report.json)

## Git 状态

当前工作区有 Phase 7-8 新增 / 修改文件，未提交。详见最后一次 `git status`。
