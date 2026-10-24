# F0 只读审计总结

> 日期：2026-10-24
> 审计范围：SOC 规范 §1-8 + 参考图片 + 现有前端全部源码 + API 契约映射

---

## 1. 仓库事实（已验证）

| 项 | 事实 |
|---|---|
| 框架 | Vue 3.5 + TypeScript 5 + Vite 8 |
| 图表 | echarts core modular (tree-shaken) |
| 路由 | createWebHashHistory，DefaultLayout 外壳，8 子路由 |
| CSS | 全局 style.css + 各组件 scoped styles，无 CSS-in-JS / 无 Tailwind |
| API client | `api/client.ts` + 5 模块（events/retrieval/policies/metrics/traffic），基于 fetch |
| 状态管理 | 无 Pinia/Vuex，组件内 ref + computed |
| 图标 | 纯 emoji，无 iconfont/Lucide |
| 依赖 | 无 UI 组件库（Element Plus / Ant Design Vue 均不存在）|
| 构建 | `cd frontend && npm run build` → dist/ |
| 类型检查 | `vue-tsc -b` |
| Lint | **未配置** |
| 前端测试 | **未配置**（vitest 不存在）|
| 后端测试 | pytest 268 passed, 1 skipped |
| uvicorn | 已运行，`http://127.0.0.1:8000/ui` 可访问 |
| AGENTS.md | **不存在**（Glob 已验证）|

## 2. 当前设计令牌 vs SOC 规范

| 语义 | 当前值 | SOC 规范建议 | 差距 |
|---|---|---|---|
| 页面背景 | `#0f1120` | `#070D1A` | 现有偏紫，SOC 要求更深海军蓝 |
| 导航背景 | `#141729` | `#0B1630` | 现有偏紫，SOC 深蓝 |
| 卡片背景 | `#171a2e` | `#0D1930` | 现有偏紫，SOC 深蓝 |
| 次级表面 | `#1f2340` | `#10213D` | — |
| 边框 | `#2a2e4d` | `#203655` | — |
| 主文本 | `#e4e7f7` | `#E8F0FF` | 接近 |
| 次级文本 | `#8a8fb8` | `#9CB0D0` | 接近 |
| 主操作蓝 | `#4f8cff` | `#3478F6` | SOC 更蓝，当前偏青 |
| 辅助青色 | 未定义 | `#22C7D6` | **缺失** — 无 cyan accent |
| 严重/高危 | `#ff5a5f` | `#F04452` | 接近 |
| 中风险 | `#ffb454` | `#F59E0B` | 接近 |
| 低风险 | `#4f8cff` (复用主蓝) | `#3B82F6` | 语义混淆 |
| 成功 | `#29c38b` | `#10B981` | 接近 |
| 禁用/未接入 | `#5a5f8a` | `#64748B` | 接近 |

**核心问题**：现有色板偏紫（#0f1120 / #141729 / #171a2e / #1f2340 都带明显紫色调），SOC 规范是纯深蓝。参考图片的侧边栏和卡片有清晰的深蓝感，当前没有。

## 3. 布局基线 vs SOC 规范

| 规范要求 | 当前状态 | 差距 |
|---|---|---|
| 唯一全局顶部栏 | ✅ TopBar.vue | — |
| 唯一侧边导航 | ✅ Sidebar.vue | — |
| 页面内部不重复渲染外壳 | ✅ 所有 view 都不渲染 header/sidebar | — |
| 顶部栏显示真实健康状态 | ✅ 20s 轮询 /health | — |
| 侧边导航当前选中态 | ✅ route.path 匹配 | 需增强视觉（加左侧蓝条）|
| 侧边导航待处理数量 | ❌ | **缺失** — 参考图片有红色 badge（Events ⚠3）|
| 底部安全边界提示 | ✅ Sidebar 底部有 | — |
| 顶部栏产品名 | ✅ "Edge Security · 安全态势感知 · 自适应防御" | — |
| 1920×1080 布局 | ⚠️ 未逐页验证 | Dashboard 6 列 metric 可能过挤 |
| 1440×900 | ⚠️ 未逐页验证 | 同上 |
| 768px 响应式 | ⚠️ 部分已有 media query | Sidebar 未实现折叠 |

## 4. 组件基线 vs SOC 规范

| SOC 规范建议 | 当前组件 | 差距 |
|---|---|---|
| PageHeader | ❌ 无统一组件 | 每个 view 自己写 `.page-head`，样式重复 |
| KpiCard | ✅ `MetricCard.vue` | 色板 + 字号需对齐 SOC；当前是 monospace 数字 |
| StatusBadge | ✅ `StatusTag.vue` | 色板对齐 SOC 即可 |
| DataState | ⚠️ 零散 | 各 view 自己写 loading/error/empty 状态无统一组件 |
| SectionCard | ❌ 无 | Dashboard 直接写 `.metric-card` `.table-card` 等，需统一 |
| FilterBar | ❌ 无 | Events/Policy 的筛选在 toolbar 里，样式不统一 |

## 5. API 数据真实性基线

这是 SOC 规范最强调的。检查 DashboardView：

| 项 | 当前行为 | 是否符合规范 |
|---|---|---|
| metrics/overview → edgy_* counters | 直接显示 `series[0].value ?? 0` | ⚠️ **null → 0 的隐式转换**（规范：只有真实 0 才显示 0）|
| RiskDistributionChart | 前端从 events severity 计算 | ✅ 标注了"前端推导" |
| EventTrendChart | 前端从 events timestamps 计算 | ✅ 标注了"前端推导" |
| charts 空状态 | `events.length === 0` 时显示空白 | ⚠️ **无明确 empty 状态提示** |
| charts 错误状态 | 父级 overlay 覆盖 | ⚠️ 不够细粒度 |
| TopBar 健康检查 | poll /health | ✅ 有真实来源 |
| DataSourceBadge | 标注 kind='live' | ✅ |
| "connected" 文案 | 硬编码显示 | ⚠️ 规范：无健康检查时应隐藏 |

## 6. 参考图片视觉要点（需实现）

| 参考图元素 | 实现方式 |
|---|---|
| 深蓝侧边栏（#0B1630 级）| Sidebar 背景改深，选中项加左侧蓝色竖条 |
| 顶部栏左侧盾牌图标 + 产品名 + 版本 | TopBar 重写 |
| 顶部栏右侧：系统正常状态灯 + 时间 + 用户头像 | TopBar 加时间显示 |
| 4 个大 KPI 卡片（高危/中危/检测任务/防御策略）| Dashboard top row — 用 events severity counts + metrics/overview 真实数据 |
| 威胁趋势折线图（多条堆叠）| echarts line，来自 events 时间桶 |
| 风险等级分布饼图/环形图 | 已有 RiskDistributionChart，需换色板 |
| 右侧实时告警栏（红色高亮）| Dashboard 右侧 column — events 取 severity=CRITICAL/HIGH |
| 最近事件表格 | 已有 |
| 检测任务状态环形进度 | metrics/overview 中的 edgy_detection 状态 |
| 边缘节点状态 | 暂无 API → 显示"未接入"占位 |
| 底部情报来源图标栏 | 纯装饰，按规范可隐藏 |

## 7. 风险与约束

| 约束 | 说明 |
|---|---|
| 不改 API 契约 | api/ 目录一律不动 |
| 不动路由 | router/index.ts 不动 |
| 不碰安全边界 | allow_real_execution=false 硬约束保留 |
| 不新增依赖 | 无 npm install（echarts/Vue/Vite 已有）|
| 不引入 UI 组件库 | 继续手写 scoped style |
| 图标继续用 emoji | 不引入 iconfont/Lucide |
| DataSourceBadge 保留 | 7 个 live 页面都有，不能删 |
| 后端接口缺失的模块 | 边缘节点状态 → 显示"未接入"占位，不伪造数据 |

## 8. 分阶段计划（SOC 规范 §9-17）

| Phase | 内容 | 风险 |
|---|---|---|
| F0 ✅ | 审计总结（本文件）| 只读 |
| **F1** | style.css 重写（SOC 色板令牌）+ TopBar/Sidebar/DefaultLayout 重写 | 视觉外壳，零业务风险 |
| **F2** | DashboardView 重构 — SOC 大屏布局 | 核心 KPI + 图表 + 告警栏 |
| F3 | EventsListView + TrafficAnalysisView | 视觉对齐 |
| F4 | PolicyWorkbenchView + KnowledgeBaseView | 视觉对齐 |
| F5 | SettingsView + EvaluationView/AuditView 占位页 | 收尾 |
| F6 | 构建 + vue-tsc + 浏览器验收 | 回归测试 |

---

**F0 完成。直接进入 F1。**
