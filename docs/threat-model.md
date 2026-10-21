# 威胁模型（Threat Model）

## 1. 范围

本文件描述 **边缘网络安全系统 AI 编程工具** MVP 原型的安全边界与对抗面。
原型定位：**离线合成流量 + 本地 OLLama 推理 + dry-run 执行**，
不接真实网络设备、不扫描生产网、不自动训练模型。

## 2. 攻击者画像

| 攻击者 | 能力 | 目标 |
|---|---|---|
| 普通互联网用户 | HTTP 请求 | 触发未授权执行、窃取知识库数据 |
| 内网渗透者 | 可访问 API 端口 | 构造恶意 flow / 策略参数 |
| 供应链 | 控制知识库 JSONL 或离线 CSV | 注入假 IOC → RAG 输出 → 策略下发 |
| 本地恶意进程 | 读写 app.db | 篡改 event → 强制 RAG 触发 |

## 3. 资产

| 资产 | 位置 | 重要性 |
|---|---|---|
| app.db（SQLite） | `data/app.db` | 高（events + policies + executions） |
| knowledge.db（sqlite-vec） | `data/knowledge_index/knowledge.db` | 中（可重建） |
| 知识库 JSONL | `data/knowledge/security_knowledge.jsonl` | 中（离线） |
| 样本 CSV | `data/samples/flows_sample.csv` | 低（合成） |
| Ollama 模型文件 | `~/.ollama/models/` | 中（只读） |
| API 端口 8000 | 127.0.0.1 | 高（生产需反向代理） |

## 4. 信任边界

```
┌──────────────────────────────┐
│ 离线合成数据 (CSV / JSONL)   │  ← 来自本地文件，非实时网络
└──────────┬───────────────────┘
           │ knowledge/sync + events/seed
           ▼
┌──────────────────────────────┐
│  Edge Security System (MVP)   │
│ ┌──────────────────────────┐ │
│ │  Retrieval + RAG          │ │
│ └───────────┬──────────────┘ │
│             ▼                │
│ ┌──────────────────────────┐ │
│ │ PolicyValidator (白名单)  │ │
│ └───────────┬──────────────┘ │
│             ▼                │
│ ┌──────────────────────────┐ │
│ │ Executor (DRY_RUN 默认)   │ │
│ └──────────────────────────┘ │
└──────────────────────────────┘
           │
           ▼  (仅 echo，不触达系统)
        /dev/null
```

**关键信任决策**：

- Ollama 只绑 `127.0.0.1:11434`，不暴露到公网。
- `ALLOW_REAL_EXECUTION=False`，任何执行只 dry-run echo。
- CIDR / 端口白名单是唯一可信来源，LLM 建议的 IP 必须落在里面。

## 5. 风险矩阵

| ID | 风险 | 影响 | 可能性 | 缓解 |
|---|---|---|---|---|
| T-1 | 恶意知识库条目 → RAG 生成 BLOCK_IP 非白名单 IP | 高 | 中 | PolicyValidator 强制 CIDR 白名单；不在范围的自动降级 ALERT_ONLY |
| T-2 | 构造恶意 event_id → 触发异常 RAG | 中 | 中 | EventRepository.get() 查不到返回 None → 404；RAGService 对检索空结果 surface DEGRADED |
| T-3 | 内存注入 / 进程级攻击 → 修改 Settings.allow_real_execution | 高 | 极低 | Phase 8 无进程保护（原型限制），生产部署需 ASLR + 隔离 |
| T-4 | SQLite 文件被篡改 → 伪造执行记录 | 中 | 低 | 原型无 DB 签名；audit 时按时间戳 + trace_id 交叉验证 |
| T-5 | Ollama 本地被替换（假模型） | 中 | 低 | Phase 8 无模型签名验证；生产需 hash 校验 |
| T-6 | LLM 提示注入（用户构造恶意 flow_summary） | 低 | 中 | MockLLM 降级路径 deterministic；真实 LLM 输出必须过 PolicyValidator |

## 6. 不做清单（明确 out-of-scope）

- ❌ 不触发真实防火墙 / iptables / nft 命令
- ❌ 不扫描生产网络
- ❌ 不自动训练或发布模型
- ❌ 不接收实时网络流量（只处理离线 CSV）
- ❌ 不声称已通过任何安全认证
- ❌ 不引入外部插件或动态加载代码

## 7. 应急步骤

如果发现异常：

1. 立即 `kill -HUP` 或重启 uvicorn 进程 — 内存指标归零，但 DB 保留
2. 检查 `data/app.db` 中 `executions` 表 status=FAILED 的记录
3. 检查 `data/demo_report.json` 或 `/api/v1/metrics/overview` 里的 `edgy_executions_total{status="FAILED"}`
4. 审计所有 `policy_proposals` 的 `requires_approval` 字段

## 8. 待加强项（后续 Phase）

- SQLite 表签名 / hash 校验
- 模型文件 SHA256 验证
- gRPC mTLS 或 JWT 鉴权（当前 API 无 auth）
- RBAC（谁能 approve 真实执行）
- 在 `10.0.0.0/8` 真实子网做红队测试
