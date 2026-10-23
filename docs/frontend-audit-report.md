# Phase F0 — 前端现状审计报告

> 审计时间：2026-10-23
> 审计者：Edge Security Agent
> 审计范围：仓库前端基础设施、路由、组件、状态管理、样式、API 接入、认证、测试、构建
> 约束：未经批准不进行大规模重构、不安装依赖、不修改业务代码

---

## A. 已确认的事实（代码证据）

### A.1 技术栈：**零依赖静态 SPA**（不是 Vue/Vite/TypeScript）

| 项目 | 实际情况 |
|---|---|
| 前端框架 | **无**。纯 HTML + CSS + 原生 ES6 JavaScript |
| 构建工具 | **无**。无 package.json、无 node_modules、无 Vite/Webpack、无 TypeScript |
| 状态管理 | **无**。所有状态用 DOM（querySelector）+ fetch 即时拉取，没有跨页面共享状态 |
| 路由 | **无**。4 个"标签页"是 `<nav class="tabs">` 点击切换，没有 URL 路由，浏览器前进/后退失效 |
| 样式方案 | 单文件 `static/style.css`，CSS 变量 + 全局选择器，无 Scoped CSS / CSS Modules |
| 图表 | **无**。纯指标卡（div + 数字），无 ECharts / Chart.js |
| 测试 | **无前端测试**。全仓库 pytest 只覆盖 Python 后端 264 条用例 |
| 挂载方式 | FastAPI main.py 里 `api.mount("/static", StaticFiles(...))` + `GET /ui → FileResponse(index.html)` |
| 后端托管 | 前端代码**直接在仓库根目录 `static/` 下**，不经历构建，生产部署直接随 Python 包一起拷贝 |

### A.2 现有前端页面覆盖度

| 规范 §3.1 主导航 | 现有实现 | 差距 |
|---|---|---|
| 安全态势总览 | **无**（只有 metrics 卡片） | 完全缺失 |
| 流量分析 | 仅有 `POST /flows/seed-policy` 按钮 + 事件列表里的 label | 无文件导入、无检测任务生命周期、无任务详情 |
| 安全事件 | 有"事件流" tab，拉 `/api/v1/events` | 有列表，无详情页，无状态变更 |
| 威胁知识库 | **无** | 完全缺失（只有后端同步接口） |
| 策略工作台 | 有"待审批策略" + "全部策略" 两个 tab，approve/reject/dry-run 按钮 | 有列表，无详情页，无策略参数完整展示，无证据面板 |
| 评估中心 | **无** | 完全缺失 |
| 审计日志 | **无** | 完全缺失（后端还没审计 API） |
| 系统设置 | 根路径 `/` 和 `/health` | 仅 JSON，无设置面板 |

### A.3 API 接口清单（20 条，真实可调用）

| 方法 | 路径 | 返回 | 前端是否接入 |
|---|---|---|---|
| GET | `/health` | `{status, service, version, python}` | ✅ 顶栏轮询 |
| GET | `/api/v1/events` | `List[SecurityEvent]` | ✅ 事件流 |
| GET | `/api/v1/events/{event_id}` | `SecurityEvent` | ❌ 无详情页 |
| POST | `/api/v1/events/seed` | `{imported}` | ❌ |
| POST | `/api/v1/flows/seed-policy` | `{imported_flows}` | ✅ 手动 seed 按钮 |
| POST | `/api/v1/flows/import` | `IngestionSummary` | ❌ 无文件导入 |
| POST | `/api/v1/detection/predict` | 检测结果 | ❌ |
| POST | `/api/v1/detection/train` | 训练结果 | ❌ |
| POST | `/api/v1/knowledge/sync` | `{documents, chunks, provider}` | ❌ |
| POST | `/api/v1/retrieval` | 检索 hits | ❌ |
| GET | `/api/v1/retrieval/status` | 状态 | ❌ |
| GET | `/api/v1/retrieval/{id}` | 详情 | ❌ |
| POST | `/api/v1/policy-proposal/generate` | proposal + evidences | ❌（无完整 RAG 触发流） |
| POST | `/api/v1/policy-proposal/validate` | `{is_valid, reasons}` | ❌ |
| POST | `/api/v1/policy-proposal/approve` | `{policy_id, status, approver, reason}` | ✅ 审批按钮 |
| POST | `/api/v1/policy-proposal/execute` | execution record | ✅ Dry-run 按钮 |
| GET | `/api/v1/policy-proposals` | `List[PolicyProposal]` | ✅ 两个 tab |
| GET | `/metrics` | Prometheus text | ❌ |
| GET | `/api/v1/metrics/overview` | `{info, system, config, metrics: {...}}` | ✅ 指标 tab |
| GET | `/api/v1/metrics/export` | JSON/CSV | ❌ |

### A.4 后端尚未实现 / 无对应前端的接口

| 能力 | 状态 |
|---|---|
| 分页 | `/events?limit=N` 支持，但无 `offset/start_after` 参数 |
| 搜索 / 关键词筛选 | **后端无**（前端也没有搜索框） |
| 任务生命周期（pending→running→done） | **后端无**，Phase 2 检测是一次性调用 |
| 知识库文档管理（列表、导入、删除） | **后端无**，只有 `/knowledge/sync` |
| 审计日志查询 | **后端无**（ExecutionRecord 有 trace_id 但没审计 API） |
| 事件详情 | 后端有 `GET /events/{id}`，前端没接入 |
| 知识库检索（keyword + vector） | 后端有 `/retrieval`，前端没接入 |
| 真实执行（allow_real_execution） | Settings 默认 false，无生产级安全边界测试 |
| 上传文件 `/flows/import` | 后端有，前端无表单 |

### A.5 后端安全机制（前端必须配合但未完全配合）

| 后端能力 | 前端现状 | 风险 |
|---|---|---|
| JWT auth（auth.py） | **未使用**。所有 API 无 token 头 | 开发期可接受，生产必须接入 |
| RBAC require_roles() | **未使用** | 同上 |
| rate_limit middleware | **已挂载但默认关闭**（auth_enabled=false 时单 bucket） | 开发期可接受 |
| mTLS middleware | **已挂载但默认关闭** | 生产 uvicorn CLI flags 配置 |
| Executor allow_real_execution guardrail | **前端只暴露 DRY_RUN 按钮** | ✅ 符合安全边界 |
| 审批状态机 NEEDS_APPROVAL→APPROVED/REJECTED | **前端接入正确** | ✅ |

### A.6 现有代码行数

| 文件 | 行数 | 说明 |
|---|---|---|
| `static/index.html` | ~90 | 顶部栏 + 4 个 tab + 模板 |
| `static/style.css` | ~220 | CSS 变量 + 卡片/表格/指标样式 |
| `static/app.js` | ~280 | fetch 封装 + 4 个 tab 的 refresh + approve/reject/execute 动作 |
| **合计** | **~590 行** | 一个人一天能重写完的体量 |

---

## B. 有证据支持的推断

| 推断 | 证据 | 置信度 |
|---|---|---|
| 当前前端是"Phase 15 补的 demo 面板"，不是正式前端 | Phase 15 commit `7ee7cc5` 明确写"zero-dep static UI"，且只在最后 2 个 tab 真正跑 API | 高 |
| 前端后续演进方向**规范 §5.1 建议 Vue 3 + Vite + TS**，但"现有技术栈优先" | 规范原文 §5.1："不得为采用建议技术而无理由替换现有技术栈" | 中 |
| 现有静态 SPA 如果直接换 Vue 重写，工作量约 3-5 天（含 TypeScript 类型 + 路由 + Pinia） | 静态 SPA 体量小，后端 API 契约已稳定（20 条接口 + 类型定义在 Pydantic models 里） | 中 |
| 前端审计日志页**无法做**，因为后端没审计 API | 审计日志需要 `created_at / actor / action / target_id / result / trace_id / summary` 这些字段，ExecutionRecord 只有 execution_id/policy_id/status | 高 |
| 评估中心页**无法做**，因为后端没实验管理 API | 检测是 RuleDemo / Sklearn 一次性调用，没实验持久化、没版本管理、没混淆矩阵 | 高 |
| 事件详情页**可以做**（后端有 `GET /events/{id}`） | 需前端新增路由 + 详情分区（基本信息/检测信息/证据/关联对象/处置记录） | 高 |
| 知识库/证据检索页**可以做**（后端有 `/retrieval` + `/knowledge/sync`） | 需前端新增检索表单 + hits 列表 + Evidence 详情 | 高 |
| 策略详情页**可以做**（后端有 policy proposal 完整字段） | 需前端新增详情分区（策略参数/证据/校验结果/执行记录） | 高 |

---

## C. 需要用户或后端开发确认的问题

| # | 问题 | 影响范围 |
|---|---|---|
| C1 | **是否允许引入 Node.js + Vue 3 + Vite + TypeScript？** 这是规范 §5.1 建议栈，但会新增一个完整前端工程（package.json、node_modules、构建产物），生产部署链路也变 | 技术选型、部署链路、依赖管理 |
| C2 | **是否保持"后端托管前端静态资源"的部署模式？**（当前 main.py mount /static）还是前端单独部署 nginx + 后端 API？ | 部署架构、CORS 配置 |
| C3 | **后端是否计划新增审计日志 API？**（规范 §4.7 审计日志页需要） | 前端评估中心 + 审计日志页的可行性 |
| C4 | **后端是否计划新增检测任务持久化 API？**（规范 §4.2 任务生命周期 pending→running→done） | 流量分析页是否能做完整闭环 |
| C5 | **后端 `/events` 是否会加分页 offset + 搜索 + 时间范围筛选？** 规范 §7 要求分页/筛选 | 事件中心页的数据能力 |
| C6 | **真实设备下发（Phase 11 backend adapter）是否要暴露给前端？** 规范 §4.5 明确说"默认不支持真实设备下发"，但后端 backend.run_atomic() 已就绪 | 安全边界决策 |
| C7 | **前端认证方式：继续 auth_enabled=false 开发，还是 Phase F1 就接入 JWT？** | MVP 范围界定 |

---

## D. 推荐的分阶段开发顺序

> 严格按规范 §11 Phase F0-F7；每阶段必须停下来等用户审批。

| Phase | 目标 | 产出 | 依赖 |
|---|---|---|---|
| **F0** | 现状审计 + 映射文档 + 实施计划 | 当前三份文档 | — |
| **F1** | **应用骨架 + 公共组件** | Vue 工程脚手架 / 路由 / API client / 类型定义 / 加载-空-错误状态 / 全局布局 / 顶部栏+侧边栏 | C1/C2 决定（栈选型） |
| **F2** | **策略工作台 + 事件中心 + 检索** | 这三个页面覆盖完整闭环：策略候选 → 审批 → Dry-run + 事件列表/详情 + 知识库检索 | — |
| **F3** | **安全态势总览 + 流量分析** | 态势总览指标卡 + 趋势图 + 流量文件导入 + 检测触发 | 后端 `/events/seed` + `/flows/import` 可用 |
| **F4** | **系统设置 + 评估中心**（标记阻塞） | 设置面板 + 评估中心（如果 C3/C4 未解决则展示"未接入"占位） | C3/C4 解决情况 |
| **F5** | **审计日志页**（标记阻塞如果 C3 未解决） | 审计列表 + 详情 | C3 解决 |
| **F6** | **集成测试 + 体验收尾** | E2E 测试 + 响应式 + 键盘可达性 + 错误页 | 全部功能 |
| **F7** | **联调 + 最终验收** | 跑通 9 步核心流程（规范 §2.2）+ 对比验收清单 | — |

### 为什么先做 F2？

F2 三个页面**恰好是规范 §15 指定的"可演示最小闭环"**：
`策略候选 → 审批 → Dry-run → 事件列表 → 知识库检索`

后端这 7 个 API **全部已实现且可直接调用**，零后端阻塞，联调成本最低。如果 F1 骨架到位后直接 F2，能最快产出一个能看的完整产品。

---

## E. 风险、依赖和阻塞项

| # | 类型 | 描述 | 应对 |
|---|---|---|---|
| R1 | **依赖膨胀** | Vue 3 + Vite + ECharts 新增至少 50+ npm 包 | 在 C1 决策里权衡；如果要保持极简可以继续零依赖方案但用 ES Modules + import map |
| R2 | **TypeScript vs Pydantic 类型漂移** | 后端改 schema 前端类型必须同步 | 建立 docs/frontend-api-mapping.md 契约登记表 |
| R3 | **后端接口缺口** | 审计日志 API / 检测任务 API / events 分页搜索 均不存在 | 前端用"未接入"占位，明确标注 |
| R4 | **CORS** | 前后端分开部署时前端 dev server 要配代理 | vite.config.ts proxy |
| R5 | **现有静态 SPA 保留还是替换？** | 静态 SPA ~590 行，Vue 重写约 3000 行 | 建议直接替换，静态 SPA 不值得维护两套 |
| R6 | **node_modules 体积** | Vue 完整脚手架约 200-300MB | .gitignore node_modules，npm ci 安装 |
| R7 | **前端测试零覆盖** | 规范 §10 要求单元/组件/E2E | F1 就要引入 Vitest + Vue Test Utils，避免最后补 |
| R8 | **安全：前端不能替代后端校验** | 规范 §9 条款 3/6/7 | 前端所有危险操作（approve/execute）必须走后端，前端只做体验性检查 |

---

## 审计结论：BLOCKED（等待 C1-C7 决策）

**本 Phase F0 停在此处。** 不自动进入 Phase F1，等待用户确认：

1. **技术栈决策**（C1）：是 Vue 3 + Vite + TypeScript，还是保持零依赖方案增强？
2. **部署模式决策**（C2）：后端托管还是前端独立部署？
3. **后端缺口决策**（C3/C4）：审计 API + 检测任务 API 是否近期会加，还是前端先做占位？
4. **C5-C7 次要确认**

确认后进入 Phase F1。
