# Phase F0 — 前端实施计划

> 基于 `frontend-audit-report.md` 的审计事实；等用户确认 C1-C7 决策后再进入实现。

---

## 0. 前置决策（阻塞 Phase F1）

| 决策项 | 选项 | 建议 | 请在右侧打勾 |
|---|---|---|---|
| **C1 技术栈** | A. Vue 3 + Vite + TS (规范 §5.1 建议) <br> B. 继续零依赖 ES Modules（极简但弱类型、弱工具链） | **A** — 规范 §5.1 明确推荐；现有 SPA ~590 行不值得维护两套 | ☐ |
| **C2 部署模式** | A. 后端托管（FastAPI 继续 mount /static，但改成 mount dist/）<br>B. 前端独立部署（nginx / CDN，CORS 代理到后端） | **A** — 延续现状，部署脚本 deploy_linux.sh 只需加 `npm ci && npm run build` 步骤 | ☐ |
| **C3 审计日志 API** | A. 先不做，前端审计页展示"未接入"占位<br>B. 后端加审计 API（约 1-2 天）再做 | **A** — 审计页不是 MVP 闭环必需，标阻塞即可 | ☐ |
| **C4 检测任务 API** | A. 先不做，前端"流量分析"页只展示导入 + 检测结果，无任务生命周期<br>B. 后端加任务 API（约 1 天） | **A** — flows/import 一次性调用够用，任务状态可前端本地跟踪 | ☐ |
| **C5 /events 增强** | A. 后端暂不加分页 offset + 搜索；前端只做下拉筛选<br>B. 后端加分页 + 搜索（约 0.5 天） | **A** — limit=N 够用 | ☐ |
| **C6 真实设备下发** | A. 前端不暴露 REAL 模式按钮，只 DRY_RUN<br>B. 生产管理员可见 REAL（需要额外 approval_token + 二次确认） | **A** — 规范 §4.5 明确"默认不支持真实设备下发" | ☐ |
| **C7 前端认证** | A. Phase F1 就接 JWT（auth_enabled=false 开发期无 token）<br>B. Phase F2+ 再接 | **B** — MVP 阶段 auth_enabled=false，F2 前端骨架先跑通后再加 | ☐ |

**如全部采纳建议**：Phase F1 引入 Vue 3 + Vite + TS + Pinia（可选）+ ECharts + Vitest，后端不新增任何 API，直接调用现有 20 条。

---

## Phase F1 — 应用骨架 + 公共组件（建议 2-3 天）

### 目标
替代现有零依赖静态 SPA，建立正式 Vue 工程，跑通"加载→空→成功→错误"全链路。

### 产出

```
frontend/
  src/
    api/
      client.ts           # 统一 fetch 封装（超时 / 错误 / retry / 拦截）
      events.ts           # events / flows API 函数
      policies.ts         # proposal / approve / execute
      retrieval.ts        # knowledge/sync + /retrieval
      metrics.ts          # metrics/overview
    components/
      common/LoadingSpinner.vue
      common/EmptyState.vue
      common/ErrorBanner.vue
      common/ConfirmDialog.vue         # 高风险操作二次确认
      common/StatusTag.vue              # 风险等级 / 状态标签（文字+颜色）
      common/DataSourceBadge.vue        # 真实后端数据 / 未接入 / 演示数据
      common/MetricCard.vue
      charts/SimpleBarChart.vue         # ECharts 封装，后端返回数组即可
      charts/SimpleLineChart.vue
    layouts/
      DefaultLayout.vue                # 顶栏 + 侧边栏 + 主内容
    router/index.ts                    # Vue Router
    types/
      api.ts                           # 统一响应类型
      event.ts
      policy.ts
      evidence.ts
      execution.ts
    utils/
      format.ts                        # 日期格式化 / 枚举→展示映射
    views/
      PlaceholderView.vue              # "未接入" 通用占位
      NotFoundView.vue
    App.vue
    main.ts
  package.json
  vite.config.ts
  tsconfig.json
```

### 验收
- [ ] `npm run dev` 启动成功，`/ui` 或 `/` 能看到 DefaultLayout
- [ ] 侧边栏 8 个导航项按规范 §3.1 列出，未实现页点进去是 PlaceholderView（"未接入 - 后端 API 不存在或前端未实现"）
- [ ] 已实现页点进去能发起真实 API 请求（即使返回空）
- [ ] TypeScript 严格模式通过
- [ ] `npm run build` 产物输出到 `frontend/dist/`
- [ ] FastAPI `main.py` mount 路径从 `static/` 改为 `frontend/dist/`
- [ ] **后端 264 个 pytest 零回归**（后端托管前端，前端文件变更不影响 Python 测试）

---

## Phase F2 — 策略工作台 + 事件中心 + 检索（建议 3-4 天）

### 目标
跑通规范 §15 指定的"可演示最小闭环"：
`策略候选 → 审批 → Dry-run → 事件列表 → 知识库检索`

### 产出

```
frontend/src/
  api/
    events.ts           # 补 getEvent(id)
    retrieval.ts        # 补 search()
    policies.ts         # generate + validate + approve + execute + list
  views/
    PolicyWorkbenchView.vue         # 候选列表 + 筛选
    PolicyDetailView.vue            # 详情分区（参数 / 证据 / 校验 / 执行记录）
    EventListView.vue               # 列表 + 下拉筛选
    EventDetailView.vue             # 详情分区
    KnowledgeBaseView.vue           # 同步 + 检索 + hits 列表
  components/
    policies/PolicyCandidateCard.vue
    policies/EvidenceChunk.vue
    policies/ApproveDialog.vue
    policies/ExecuteDialog.vue
    policies/ValidatorReasons.vue
    events/EventRow.vue
    events/EventDetailSection.vue
    retrieval/RetrievalHitCard.vue
```

### 核心流程
1. 进入 PolicyWorkbench → 拉 `/api/v1/policy-proposals?status=NEEDS_APPROVAL`
2. 点"Generate Proposal" → POST `/generate`（可选，或假设已 seed）
3. 打开 PolicyDetail → 看 Evidence → 看 ValidatorReasons
4. 点 Approve → ConfirmDialog → POST `/approve`
5. 点 Dry-run → ConfirmDialog（警告 allow_real_execution=false）→ POST `/execute`
6. 回到 EventList → 看事件
7. 进入 KnowledgeBase → sync + search

### 验收
- [ ] 9 步核心流程手工跑通（规范 §2.2）
- [ ] Approve 重复点击 → 409 状态清晰展示（"此策略已 APPROVED，不能再次审批"）
- [ ] 校验失败策略 → ValidatorReasons 红色列出原因，前端不能绕过
- [ ] Dry-run 警告弹窗明确说"不修改任何真实防火墙"
- [ ] 无后端数据 → EmptyState（不是 0 随机填充）
- [ ] 后端 pytest 264/264 绿
- [ ] **至少 3 个单元测试**（api client error handling + 日期格式化 + 枚举映射）

---

## Phase F3 — 态势总览 + 流量分析（建议 2 天）

### 产出

```
frontend/src/
  api/
    traffic.ts          # flows/import + detection/predict
  views/
    DashboardView.vue   # 指标卡 + 风险分布 Bar + 最近事件 Table + 最近策略 Table
    TrafficAnalysisView.vue  # 文件导入 + 检测结果展示
  components/
    charts/RiskDistributionChart.vue
    charts/EventTrendChart.vue    # 时间趋势（mock 后端暂不支持，先用最近 10 事件的 create time 生成）
```

### 注意
- 后端**无事件趋势 API**：前端 EventTrendChart 用 `/events` 返回的时间戳做桶；标注"时间范围=当前返回的事件集"
- 后端**无检测任务 API**：TrafficAnalysisView 只展示 flows/import 的 summary + events 列表，无任务生命周期
- **所有 mock 趋势数据必须标注"由前端从 events 时间戳推导，非后端统计"**

### 验收
- [ ] Dashboard 指标卡全部拉 `/metrics/overview`
- [ ] Dashboard 空数据 → 卡片显示"暂不可用"
- [ ] 流量导入后跳转到 EventListView 自动筛选 severity

---

## Phase F4 — 评估中心 + 系统设置（建议 1-2 天，部分阻塞）

### 产出
```
views/
  EvaluationView.vue     # "未接入"占位（C3 决策 A）
  SettingsView.vue       # 展示 /health + /metrics/overview.config + .env.example 里的配置项（脱敏）
```

### 注意
- EvaluationView → **未接入**占位，说明："后端暂无实验管理 API，无法展示 Precision/Recall/F1"
- SettingsView 必须**不展示敏感配置**（auth_jwt_secret、mtls_keyfile 等）

---

## Phase F5 — 审计日志（阻塞，等 C3）

后端加审计 API 后再做。占位页提前建好。

---

## Phase F6 — 集成测试 + 体验收尾（建议 2 天）

- E2E 测试（playwright / cypress）：9 步核心流程
- 所有页面键盘可达性检查（Tab 遍历 / Enter 提交）
- 响应式测试（Chrome DevTools Device Toolbar）
- 错误页统一（404 / 网络断 / 后端挂）
- 数据来源标签全站补齐（真实后端数据 / 未接入 / 演示数据）

---

## Phase F7 — 联调 + 最终验收

对照规范 §14 最终交付清单逐项勾。

---

## 工作量估算（全部 Phase F0-F7）

| Phase | 工作日 | 依赖 |
|---|---|---|
| F0 现状审计 | **已完成** | — |
| F1 骨架 + 组件 | 2-3 | C1-C7 决策 |
| F2 策略 + 事件 + 检索 | 3-4 | F1 |
| F3 态势 + 流量 | 2 | F2 |
| F4 评估 + 设置 | 1-2 | C3/C4 决策（标记阻塞） |
| F5 审计 | 0.5（占位） / 2（后端就绪后） | C3 |
| F6 集成 + 体验 | 2 | F2-F5 |
| F7 联调 + 验收 | 1 | F6 |
| **合计** | **11-15 工作日** | |

---

## 风险清单（F1 开始前逐项确认）

| # | 风险 | 缓解 | 负责人 |
|---|---|---|---|
| R1 | Vue 脚手架新增 ~200MB node_modules | .gitignore node_modules；CI 用 `npm ci` | 前端 |
| R2 | 后端 schema 变更前端类型漂移 | docs/frontend-api-mapping.md 登记每改一次同步 | 全栈 |
| R3 | flows/import 文件上传在 FastAPI TestClient 里测试 OK，浏览器真实 multipart 可能出问题 | F2 联调第一天先跑通一次真实上传 | 前端 |
| R4 | 后端 `/events` 只有 limit 无 offset，前端分页"上一页"按钮要禁用 | 前端明确标注"仅支持 limit=N 条，无分页" | 前端 |
| R5 | Auth 未接入时 API 默认放行，未来开 auth_enabled=true 前端要同步加 token | 前端 api client 预先留好 auth interceptor，注释里标注 | 前端 |

---

## 下一步

**停下来，等用户确认 C1-C7 决策 + 本实施计划。**

确认后进入 Phase F1：
1. 安装 Node.js（若本机无）
2. `npm create vite@latest frontend -- --template vue-ts`
3. 搭骨架、路由、Layout、公共组件
4. 替换 FastAPI `main.py` mount 路径
5. 构建验证
6. 汇报
