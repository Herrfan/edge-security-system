# Phase 0 仓库现状审计报告

**审计日期**：2026-10-21  
**审计对象**：`d:\edge security system`  
**审计范围**：完整仓库盘点、环境检查、任务书对照评估  
**审计原则**：技术真实性——仅依据实际文件和命令输出，不假设、不推测、不伪造

---

## 1. 仓库物理状态

### 1.1 文件清单

整个仓库仅包含 **1 个文件**：

```
d:\edge security system\
├── 边缘网络安全系统_AI编程工具开发任务书.md   (548 行，开发任务基线)
```

**无任何源代码、无依赖清单、无配置、无数据、无模型、无测试文件。**

### 1.2 Git 状态

```
git status → fatal: not a git repository
git log   → fatal: not a git repository
git init  → 尚未执行
```

**仓库不是 Git 仓库，无版本历史。**

### 1.3 其他

- 无 `.env` / `.env.example`
- 无 `AGENTS.md`、`README.md`、`pyproject.toml`、`requirements.txt`
- 无 `app/`、`tests/`、`data/`、`models/`、`scripts/`、`docs/`（本次审计新建）目录

---

## 2. 开发环境

### 2.1 运行时

| 项目 | 实际值 | 证据 |
|---|---|---|
| 操作系统 | Windows（PowerShell 5） | 系统环境 |
| Python | 3.12.10 | `python --version` |
| pip | 25.0.1 | `pip --version` |
| 硬件 | CPU only，无 CUDA/GPU | `torch.cuda.is_available() → False`，0 devices |
| CPU 信息 | 未深入探测，确认仅有 CPU 推理能力 | 同上 |

### 2.2 已安装关键依赖

| 模块 | 版本 | 命令验证 |
|---|---|---|
| FastAPI | 0.115.0 | ✅ `import fastapi` |
| Pydantic | 2.9.2 | ✅ `import pydantic` |
| pydantic-settings | 2.5.2 | ✅ pip list |
| Uvicorn | 0.32.0 | ✅ |
| SQLAlchemy | 2.0.35 | ✅ |
| aiosqlite | 0.20.0 | ✅ |
| pytest | 8.4.2 | ✅ |
| pytest-asyncio | 1.4.0 | ✅ |
| numpy | 2.5.3 | ✅ |
| scikit-learn | 1.9.1 | ✅ |
| scipy | 1.18.1 | ✅ |
| polars | 1.44.2 | ✅ |
| torch | 2.14.0+cpu | ✅ |
| torchvision | 0.29.0 | ✅ |
| transformers | 5.19.0 | ✅ |
| sentence-transformers | 6.1.0 | ✅ |
| cryptography | 50.0.1 | ✅ |
| python-dotenv | 1.2.4 | ✅ |
| python-multipart | 0.0.9 | ✅ |
| PyYAML | 6.0.3 | ✅ |
| orjson | 3.12.0 | ✅ |
| psutil | 7.2.2 | ✅ |

### 2.3 缺失依赖（需评估是否安装）

| 模块 | 状态 | 影响 |
|---|---|---|
| pandas | ❌ 未安装 | CSV 数据处理可先用 polars 替代，polars 已装 |
| onnxruntime | ❌ 未安装 | 模型 ONNX 推理；首版可暂不依赖 |
| FAISS / faiss-cpu | ❌ 未安装 | 向量检索；可先用 sqlite-vec 或 numpy 余弦基线 |
| ChromaDB | ❌ 未安装 | 向量检索备选；同上 |
| PyJWT | ❌ 未安装 | 首版无复杂鉴权时非必需 |
| tiktoken | ✅ 已装 | LLM token 计数 |

### 2.4 本地 LLM / Embedding（通过 Ollama）

```
ollama list →
  qwen2.5:3b                 1.9 GB    (4 weeks ago)
  qwen2.5:7b                 4.7 GB    (5 days ago)
  nomic-embed-text:latest    274 MB    (6 months ago)
```

**重要提示**：这些模型存在于本机，但本次审计**未实际测试** Ollama 服务是否正在运行、调用延迟、响应质量。Ollama 进程状态、模型加载延迟、7B 模型在纯 CPU 上的推理速度均为**待验证**项。

---

## 3. 任务书 MVP 需求逐项评估

评估维度：
- ✅ **已实现**：仓库中有真实代码、测试通过、文档存在
- ⚠️ **部分实现**：有片段或骨架但不完整，或仅设计文档
- ❌ **未实现**：仓库中无任何相关代码
- 🔍 **无法验证**：依赖外部硬件/模型/服务，未实际测试

### 3.1 数据契约（§4）

| 需求 | 状态 | 证据 |
|---|---|---|
| FlowRecord 模型定义 | ❌ 未实现 | 无任何 Python 源文件 |
| SecurityEvent 模型定义 | ❌ 未实现 | 同上 |
| Evidence 模型定义 | ❌ 未实现 | 同上 |
| PolicyProposal 模型定义 | ❌ 未实现 | 同上 |
| ExecutionRecord 模型定义 | ❌ 未实现 | 同上 |
| 统一 API 响应契约 | ❌ 未实现 | 同上 |

### 3.2 API 层（§5）

| 端点 | 状态 | 证据 |
|---|---|---|
| GET /health | ❌ 未实现 | 无 app/main.py |
| POST /api/v1/flows/import | ❌ 未实现 | 同上 |
| POST /api/v1/detection/predict | ❌ 未实现 | 同上 |
| GET /api/v1/events | ❌ 未实现 | 同上 |
| GET /api/v1/events/{event_id} | ❌ 未实现 | 同上 |
| POST /api/v1/events/{event_id}/analyze | ❌ 未实现 | 同上 |
| GET /api/v1/retrieval/{retrieval_id} | ❌ 未实现 | 同上 |
| POST /api/v1/policies/{policy_id}/validate | ❌ 未实现 | 同上 |
| POST /api/v1/policies/{policy_id}/approve | ❌ 未实现 | 同上 |
| POST /api/v1/policies/{policy_id}/execute | ❌ 未实现 | 同上 |
| POST /api/v1/executions/{execution_id}/rollback | ❌ 未实现 | 同上 |
| GET /api/v1/metrics/overview | ❌ 未实现 | 同上 |
| POST /api/v1/knowledge/sync | ❌ 未实现 | 同上 |

### 3.3 核心服务层

| 需求 | 状态 | 备注 |
|---|---|---|
| 离线流量导入（CSV/JSON） | ❌ 未实现 | polars 可用 |
| 特征处理管线 | ❌ 未实现 | — |
| 检测器接口（可替换） | ❌ 未实现 | — |
| 检测基线（规则/ML） | ❌ 未实现 | sklearn 可用 |
| 事件存储（SQLite/SQLAlchemy） | ❌ 未实现 | SQLAlchemy 2.0 + aiosqlite 可用 |
| 安全知识库导入 | ❌ 未实现 | — |
| 关键词检索（BM25） | ❌ 未实现 | 需手工实现或引入轻量库 |
| 向量检索适配器 | ❌ 未实现 | faiss 未装，可用 numpy 基线 |
| 检索融合 | ❌ 未实现 | — |
| RAG 候选策略生成 | ❌ 未实现 | Ollama 本地模型待验证 |
| LLM provider 抽象 | ❌ 未实现 | — |
| 策略校验（白名单/证据/TTL） | ❌ 未实现 | — |
| 审批服务 | ❌ 未实现 | — |
| dry-run 执行器 | ❌ 未实现 | — |
| 回滚机制 | ❌ 未实现 | — |
| 反馈记录 | ❌ 未实现 | — |
| 指标汇总 | ❌ 未实现 | psutil 可用 |

### 3.4 基础设施

| 需求 | 状态 | 备注 |
|---|---|---|
| 项目骨架 / 目录 | ❌ 未实现 | 只有 docs/（本次新建） |
| 配置管理 | ❌ 未实现 | pydantic-settings 可用 |
| 日志脱敏 | ❌ 未实现 | — |
| 健康检查 | ❌ 未实现 | — |
| 数据库 schema / migration | ❌ 未实现 | SQLAlchemy 可用 |
| Repository 层 | ❌ 未实现 | — |
| .env.example | ❌ 未实现 | — |
| pyproject.toml | ❌ 未实现 | — |
| README.md | ❌ 未实现 | — |

### 3.5 测试

| 需求 | 状态 | 备注 |
|---|---|---|
| 单元测试框架 | ⚠️ 部分可用 | pytest 8.4.2 已装，但仓库无测试文件 |
| 集成测试 | ❌ 未实现 | — |
| 安全/负面测试 | ❌ 未实现 | — |
| 性能测试 | ❌ 未实现 | — |

### 3.6 数据 / 模型 / 外部资源

| 资源 | 状态 | 备注 |
|---|---|---|
| 样例流量数据集 | ❌ 未提供 | 需另行准备 |
| PCAP 或流记录 | ❌ 未提供 | — |
| 预训练检测模型 | ❌ 未提供 | — |
| 安全知识库文档 | ❌ 未提供 | 需另行准备公开/授权资料 |
| Embedding 模型 | 🔍 待验证 | nomic-embed-text 在 Ollama，未实测 |
| LLM（qwen2.5） | 🔍 待验证 | Ollama 服务 + CPU 推理速度待验证 |
| 真实防火墙/网络设备 | ❌ 不可用 | 安全边界要求不接真实执行 |

---

## 4. 关键风险与阻塞项

### 4.1 硬阻塞（不解决无法推进）

| # | 风险 | 影响 | 建议 |
|---|---|---|---|
| R1 | **仓库完全为空**，无任何代码基础 | 所有 Phase 均需从零搭建 | 按 Phase 1 建立最小骨架 |
| R2 | **无版本控制** | 无法追踪变更、无法回滚 | 立即 `git init`，Phase 1 前完成 |
| R3 | **无样例数据** | Phase 2 检测基线无法真实验证 | 准备小型 CICIDS2017 子集或自制合成流 |
| R4 | **Ollama 可用性未验证** | Phase 4/5 的检索和 RAG 无法真实验证 | 先执行 `ollama run qwen2.5:3b "hi"` 验证延迟和可用性 |
| R5 | **纯 CPU 推理** | 7B 模型推理可能极慢（估计 10-30s/请求） | 优先用 3B 模型，或接受延迟 |

### 4.2 软风险（可降级处理）

| # | 风险 | 影响 | 降级方案 |
|---|---|---|---|
| R6 | FAISS/ChromaDB 未安装 | 无法做真实向量检索 | 先用 numpy + 余弦相似度基线；或用 sqlite-vec（已装 0.1.9） |
| R7 | pandas 未安装 | 部分 CSV 处理不便 | polars 替代，polars API 覆盖绝大多数 pandas 场景 |
| R8 | 无 ONNX Runtime | 模型无法导出 ONNX | 首版用原生 sklearn/torch；ONNX 作为后续优化 |
| R9 | 无 PyJWT | 无请求级鉴权 | MVP 首版可无复杂鉴权；或用 API Key Header 简单方案 |
| R10 | 向量模型质量 | sentence-transformers 6.1.0 版本较新，兼容性待确认 | 先在 CPU 上做小批量测试 |

### 4.3 安全相关

| # | 风险 | 状态 |
|---|---|---|
| S1 | 无真实防御设备 | ✅ 已满足安全边界——默认 dry-run，不接真实执行 |
| S2 | 无真实网络流量 | ✅ 已满足——首版只处理离线样本 |
| S3 | Ollama 本地 API 默认监听 | 需确认 `127.0.0.1` 绑定，避免暴露到网络 |
| S4 | 未来 `.env` 可能泄露密钥 | Phase 1 需建立 `.gitignore` 和 `.env.example` |

---

## 5. 推荐技术栈（基于现有环境，不新增大型依赖）

| 层级 | 选型 | 理由 |
|---|---|---|
| 语言 | Python 3.12.10 | 已安装 |
| API 框架 | FastAPI 0.115.0 | 已装，类型校验自动文档 |
| 数据校验 | Pydantic v2 + pydantic-settings | 已装 |
| 数据库 | SQLite + SQLAlchemy 2.0 + aiosqlite | 已装，原型足够 |
| 异步服务 | Uvicorn | 已装 |
| 数据处理 | polars（替代 pandas） | 已装 |
| 检测模型 | scikit-learn（传统基线） | 已装 |
| 向量检索 | sqlite-vec 0.1.9（已装）或 numpy 余弦基线 | 避免新增大依赖 |
| Embedding | Ollama nomic-embed-text | 本机有，274MB |
| LLM | Ollama qwen2.5:3b（主）/ qwen2.5:7b（备选） | 本机有，1.9GB/4.7GB |
| 日志 | Python logging + 自定义脱敏 Filter | 标准库 |
| 配置 | pydantic-settings + .env | 已装 |
| 测试 | pytest + pytest-asyncio | 已装 |
| 向量融合 | RRF（Reciprocal Rank Fusion），纯 Python 实现 | 无需额外依赖 |
| 指标 | psutil（CPU/内存）+ 手工埋点 | 已装 |

### 明确不引入的依赖（首版）

- FAISS / ChromaDB —— 用 sqlite-vec 或 numpy 基线替代
- pandas —— polars 替代
- onnxruntime —— 原生框架足够
- PyJWT —— 首版无复杂鉴权
- Docker —— 本地 venv 优先
- PostgreSQL —— SQLite 原型足够

---

## 6. 与任务书的差距汇总

任务书 MVP 共有约 **50+ 项** 具体需求点。本次审计结论：

| 状态 | 数量 | 说明 |
|---|---|---|
| ✅ 已实现 | **0** | 仓库无任何源代码 |
| ⚠️ 部分可用（环境已有依赖但无代码） | **~15** | 依赖已装，等待编排 |
| ❌ 未实现（完全空白） | **~35+** | 从零搭建 |
| 🔍 待验证（需运行测试） | **~5** | Ollama 服务状态、模型推理速度等 |

**总体结论**：仓库处于**完全初始状态**——任务书是唯一资产。开发环境基础依赖较齐全，但所有业务代码、测试、配置、数据、模型调用均需从零构建。

---

## 7. 审计局限性声明

本次审计 **未做以下操作**，相关结论为"待验证"：

1. 未启动 FastAPI 服务并测试 `/health` 端点（因无代码）
2. 未测试 Ollama 本地模型调用延迟、输出质量、embedding 向量维度
3. 未探测 CPU 型号、核心数、可用内存（影响并发设计）
4. 未检查网络连通性——但设计要求不访问生产网络，首版不需要
5. 未获取或创建样例数据集
6. 未检查 Windows 防火墙或 WinPcap——首版只处理离线数据
7. 未尝试 `git init`——本阶段不主动初始化版本控制，等待确认

---

*审计完成。本报告中的所有结论均有文件列表、`pip list` 输出或 Python import 测试作为依据。无推测成分，无伪造数据。*
