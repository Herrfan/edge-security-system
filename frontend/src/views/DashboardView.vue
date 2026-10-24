<script setup lang="ts">
/**
 * DashboardView — SOC v2 Edition.
 *
 * Layout (参考图片风格):
 *   Row 1: 4 KPI cards — derived from events severity counts (真实数据)
 *   Row 2: 威胁趋势 (多系列折线) | 风险分布 (环形图)
 *   Row 3: 实时告警栏 (CRITICAL+HIGH events)
 *   Row 4: 最近事件表格 | 检测任务状态 | 边缘节点 (未接入占位)
 *
 * Data sources:
 *   - GET /api/v1/metrics/overview   → system stats + edgy_* counters
 *   - GET /api/v1/events?limit=50     → severity counts + charts + alerts + table
 *   - GET /api/v1/policy-proposals?limit=5 → recent proposals (KPI)
 *
 * 严格遵守 SOC 规范: null 不转 0, 未接入的模块显示紧凑占位.
 */
import { computed, onMounted, ref } from 'vue'
import { metricsOverview } from '@/api/metrics'
import { listEvents } from '@/api/events'
import { listProposals } from '@/api/policies'
import RiskDistributionChart from '@/components/charts/RiskDistributionChart.vue'
import EventTrendChart from '@/components/charts/EventTrendChart.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import MetricCard from '@/components/common/MetricCard.vue'
import { formatDateTime } from '@/utils/format'
import type { MetricsOverview, SecurityEvent, PolicyProposal } from '@/types/api'

const loading = ref(true)
const err = ref<string | null>(null)
const overview = ref<MetricsOverview | null>(null)
const events = ref<SecurityEvent[]>([])
const proposals = ref<PolicyProposal[]>([])

onMounted(async () => {
  try {
    loading.value = true; err.value = null
    const [ov, ev, pr] = await Promise.all([
      metricsOverview(), listEvents({ limit: 50 }), listProposals(undefined, 10),
    ])
    overview.value = ov; events.value = ev; proposals.value = pr
  } catch (e: any) {
    err.value = e?.message || '加载 Dashboard 失败'
  } finally {
    loading.value = false
  }
})

// ---- 真实 KPI 推导 ----
const criticalCount = computed(() => events.value.filter((e) => e.severity === 'CRITICAL').length)
const highCount     = computed(() => events.value.filter((e) => e.severity === 'HIGH').length)
const mediumCount   = computed(() => events.value.filter((e) => e.severity === 'MEDIUM').length)

// 实时告警: CRITICAL + HIGH, 最近 5 条
const alerts = computed(() =>
  events.value
    .filter((e) => e.severity === 'CRITICAL' || e.severity === 'HIGH')
    .slice(0, 5),
)

// 待审批策略数 (真实 proposals 数据)
const pendingProposals = computed(() => proposals.value.filter((p) => p.status === 'NEEDS_APPROVAL').length)

// metrics/overview 的 system counters
const sys = () => overview.value?.system
const cfg = () => overview.value?.config as Record<string, any> | undefined

// edgy_* counter status map — 用于检测任务状态面板
const edgyCounters = computed(() => {
  const m = overview.value?.metrics || {}
  const counters = [
    { key: 'edgy_detections_total', label: '检测次数' },
    { key: 'edgy_events_seeded_total', label: 'Seed 事件' },
    { key: 'edgy_rag_runs_total', label: 'RAG 运行' },
    { key: 'edgy_policy_generate_total', label: '策略生成' },
    { key: 'edgy_policy_approve_total', label: '策略审批' },
    { key: 'edgy_policy_execute_total', label: '策略执行' },
  ]
  return counters.map((c) => {
    const block = (m as any)[c.key]
    const series = block?.series?.[0]
    const status = block?.status || 'unavailable'
    const value = series?.value ?? null
    return { ...c, value, status }
  })
})
</script>

<template>
  <div class="dash">
    <!-- Page header -->
    <div class="page-head">
      <div class="head-left">
        <h2 class="page-title">安全态势总览</h2>
        <p class="page-desc">
          实时监控网络安全态势 · 识别威胁 · 智能分析 · 快速响应
        </p>
      </div>
      <div class="head-right">
        <span class="time-chip">近 1 小时</span>
        <span class="time-chip active">近 24 小时</span>
        <span class="time-chip">近 7 天</span>
        <span class="time-chip">自定义</span>
      </div>
    </div>

    <!-- Loading / Error overlay -->
    <div v-if="loading" class="overlay">
      <div class="overlay-inner">加载态势数据中…</div>
    </div>
    <div v-else-if="err" class="overlay err">
      <div class="overlay-inner">❌ 加载失败: {{ err }}</div>
    </div>

    <template v-else-if="overview">
      <!-- ===== Row 1: KPI cards ===== -->
      <section class="kpi-row">
        <MetricCard
          name="高危事件" :value="criticalCount + highCount" tone="danger"
          sub="CRITICAL + HIGH"
          :delta="{ dir: criticalCount > 0 ? 'up' : 'flat' }"
        />
        <MetricCard
          name="中危事件" :value="mediumCount" tone="warn"
          sub="MEDIUM severity"
        />
        <MetricCard
          name="检测任务" tone="info"
          :value="edgyCounters.find(c => c.key === 'edgy_detections_total')?.value ?? 0"
          :unavailable="edgyCounters.find(c => c.key === 'edgy_detections_total')?.status === 'unavailable'"
          sub="rule-demo + sklearn 基线"
        />
        <MetricCard
          name="防御策略" :value="pendingProposals" tone="ok"
          sub="待审批 NEEDS_APPROVAL"
          :delta="{ dir: pendingProposals > 0 ? 'up' : 'flat' }"
        />
      </section>

      <!-- ===== Row 2: Charts + Real-time Alerts ===== -->
      <section class="row2">
        <div class="col-charts">
          <EventTrendChart :events="events" />
        </div>
        <div class="col-right">
          <RiskDistributionChart :events="events" />
          <!-- Real-time alerts sidebar -->
          <div class="alerts-card">
            <div class="alerts-head">
              <span class="alerts-title">⚡ 实时告警</span>
              <span class="alerts-count">{{ alerts.length }}</span>
            </div>
            <div v-if="alerts.length === 0" class="alerts-empty">暂无高危告警</div>
            <div v-else class="alerts-list">
              <div
                v-for="a in alerts" :key="a.event_id"
                class="alert-item"
                :class="`sev-${a.severity.toLowerCase()}`"
              >
                <div class="alert-main">
                  <StatusTag :severity="a.severity">{{ a.severity }}</StatusTag>
                  <span class="alert-label">{{ a.predicted_label || '未知类型' }}</span>
                </div>
                <div class="alert-meta">
                  <span class="alert-time">{{ formatDateTime(a.created_at) }}</span>
                  <span class="alert-dot">·</span>
                  <span class="alert-score">置信度 {{ (a.score ?? 0).toFixed(2) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ===== Row 3: Recent events + Task status + Edge nodes ===== -->
      <section class="row3">
        <!-- Recent events table -->
        <div class="section-card wide">
          <div class="section-head">
            <span class="section-title">最近事件</span>
            <span class="section-link">全部 →</span>
          </div>
          <div v-if="events.length === 0" class="mini-empty">暂无事件</div>
          <table v-else class="data-table">
            <thead>
              <tr>
                <th>时间</th><th>事件类型</th><th>严重等级</th>
                <th>状态</th><th>描述</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="e in events.slice(0, 8)" :key="e.event_id">
                <td class="mono-sm">{{ formatDateTime(e.created_at) }}</td>
                <td>{{ e.predicted_label || '—' }}</td>
                <td><StatusTag :severity="e.severity">{{ e.severity }}</StatusTag></td>
                <td>{{ e.status || '—' }}</td>
                <td class="desc">{{ e.flow_summary || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Detection task status -->
        <div class="section-card">
          <div class="section-head">
            <span class="section-title">检测任务状态</span>
            <span class="section-link">查看全部 →</span>
          </div>
          <div class="counters-grid">
            <div
              v-for="c in edgyCounters" :key="c.key"
              class="counter-item"
              :class="{ unavailable: c.status === 'unavailable' }"
            >
              <div class="counter-label">{{ c.label }}</div>
              <div class="counter-val">
                {{ c.status === 'unavailable' ? '—' : c.value ?? 0 }}
              </div>
              <div class="counter-status" :class="`st-${c.status}`">{{ c.status }}</div>
            </div>
          </div>
        </div>

        <!-- Edge node status (unavailable — no backend API) -->
        <div class="section-card">
          <div class="section-head">
            <span class="section-title">边缘节点状态</span>
            <span class="section-link">查看详情 →</span>
          </div>
          <div class="edge-placeholder">
            <span class="edge-icon">🖥️</span>
            <span class="edge-text">当前不可用</span>
            <span class="edge-sub">暂无边缘节点监测数据</span>
          </div>
        </div>
      </section>
    </template>

    <!-- Footer: system info strip -->
    <footer v-if="overview" class="sys-strip">
      <span>💻 CPU {{ sys()?.cpu_percent ?? '—' }}%</span>
      <span>🧠 RSS {{ sys()?.rss_bytes != null ? (sys()!.rss_bytes! / 1024 / 1024).toFixed(0) : '—' }} MB</span>
      <span>🤖 LLM {{ cfg()?.llm_model ?? '—' }}</span>
      <span>🛡️ Real exec {{ cfg()?.allow_real_execution ? '⚠ ON' : 'FALSE (安全)' }}</span>
    </footer>
  </div>
</template>

<style scoped>
/* ===== Overlay ===== */
.overlay {
  position: fixed; inset: 0; z-index: 100;
  display: flex; align-items: center; justify-content: center;
  background: rgba(7, 13, 26, 0.85); backdrop-filter: blur(4px);
}
.overlay.err { color: var(--err); }
.overlay-inner {
  background: var(--bg-panel); border: 1px solid var(--border);
  padding: var(--space-6) var(--space-8); border-radius: var(--radius-lg);
  font-size: var(--fs-base);
}

/* ===== Page header ===== */
.page-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: var(--space-5); flex-wrap: wrap; gap: var(--space-3);
}
.head-left { line-height: 1.3; }
.page-title { font-size: var(--fs-3xl); font-weight: 700; margin: 0 0 var(--space-1); color: var(--text-hi); }
.page-desc { font-size: var(--fs-sm); color: var(--text-sub); margin: 0; }

.head-right { display: flex; gap: var(--space-2); }
.time-chip {
  font-size: var(--fs-xs); padding: 4px 12px; border-radius: 14px;
  background: var(--bg-surface); color: var(--text-sub);
  border: 1px solid var(--border); cursor: pointer;
  transition: all 0.15s;
}
.time-chip:hover { color: var(--text-hi); }
.time-chip.active { background: var(--accent); color: #fff; border-color: var(--accent); }

/* ===== Row 1: KPI ===== */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

/* ===== Row 2: Charts + Alerts ===== */
.row2 {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.col-charts { display: flex; flex-direction: column; gap: var(--space-3); }
.col-right { display: flex; flex-direction: column; gap: var(--space-3); }

/* Alerts card */
.alerts-card {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-4);
  display: flex; flex-direction: column; gap: var(--space-2);
}
.alerts-head { display: flex; align-items: center; gap: var(--space-2); }
.alerts-title { font-size: var(--fs-xl); font-weight: 600; color: var(--text-hi); }
.alerts-count {
  margin-left: auto;
  background: var(--err-soft); color: var(--err);
  font-size: var(--fs-xs); font-weight: 700;
  padding: 2px 10px; border-radius: 10px;
  border: 1px solid rgba(240, 68, 82, 0.4);
}
.alerts-empty {
  padding: var(--space-6); text-align: center;
  color: var(--text-dim); font-size: var(--fs-sm);
}
.alerts-list { display: flex; flex-direction: column; gap: var(--space-1); }
.alert-item {
  border-left: 2px solid var(--border);
  padding: var(--space-2) var(--space-3);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  background: var(--bg-surface);
  transition: background 0.15s;
}
.alert-item:hover { background: var(--bg-hover); }
.alert-item.sev-critical { border-left-color: var(--err); background: var(--err-soft); }
.alert-item.sev-high     { border-left-color: var(--warn); background: var(--warn-soft); }
.alert-item.sev-medium   { border-left-color: var(--info-blue); background: var(--info-soft); }

.alert-main { display: flex; align-items: center; gap: var(--space-2); margin-bottom: 2px; }
.alert-label { font-size: var(--fs-sm); color: var(--text-hi); font-weight: 500; }
.alert-meta { display: flex; align-items: center; gap: var(--space-2); font-size: 11px; color: var(--text-dim); }
.alert-dot { color: var(--text-dim); }

/* ===== Row 3: Tables + Counters ===== */
.row3 {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.section-card {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-4);
  display: flex; flex-direction: column;
}
.section-card.wide { min-width: 0; }

.section-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-3); }
.section-title { font-size: var(--fs-xl); font-weight: 600; color: var(--text-hi); }
.section-link { font-size: var(--fs-xs); color: var(--accent); cursor: pointer; }
.section-link:hover { color: var(--accent-hover); }

.mini-empty { padding: var(--space-8) 0; text-align: center; color: var(--text-dim); font-size: var(--fs-sm); }

/* Data table */
.data-table { width: 100%; font-size: var(--fs-sm); }
.data-table th {
  text-align: left; padding: 8px 10px;
  color: var(--text-sub); font-weight: 600; font-size: var(--fs-xs);
  text-transform: uppercase; letter-spacing: 0.5px;
  border-bottom: 1px solid var(--border);
}
.data-table td {
  padding: 8px 10px;
  border-bottom: 1px solid rgba(30, 58, 95, 0.5);
  color: var(--text-mid);
}
.data-table tr:hover td { background: rgba(52, 120, 246, 0.06); }
.data-table tr:last-child td { border-bottom: none; }
.mono-sm { font-family: var(--font-mono); color: var(--text-sub); font-size: 12px; }
.desc { color: var(--text-dim); max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Detection task counters */
.counters-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-2); }
.counter-item {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  display: flex; flex-direction: column; gap: 2px;
}
.counter-item.unavailable { opacity: 0.6; }
.counter-label { font-size: 10px; color: var(--text-sub); text-transform: uppercase; letter-spacing: 0.5px; }
.counter-val { font-size: 18px; font-weight: 700; color: var(--text-hi); font-family: var(--font-mono); }
.counter-item.unavailable .counter-val { color: var(--text-dim); font-size: 14px; font-style: italic; }
.counter-status { font-size: 10px; font-family: var(--font-mono); color: var(--text-dim); }
.counter-status.st-ok { color: var(--ok); }
.counter-status.st-unavailable { color: var(--text-dim); }

/* Edge node placeholder */
.edge-placeholder {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: var(--space-6); text-align: center;
  border: 1px dashed var(--border); border-radius: var(--radius-md);
  background: var(--bg-surface);
  gap: var(--space-2);
}
.edge-icon { font-size: 28px; opacity: 0.5; }
.edge-text { font-size: var(--fs-sm); color: var(--text-sub); font-weight: 600; }
.edge-sub { font-size: var(--fs-xs); color: var(--text-dim); line-height: 1.4; }

/* Footer strip */
.sys-strip {
  display: flex; gap: var(--space-5); flex-wrap: wrap;
  font-size: var(--fs-xs); color: var(--text-sub);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border);
  font-family: var(--font-mono);
}

/* ===== Responsive ===== */
@media (max-width: 1440px) {
  .row2 { grid-template-columns: 1fr; }
  .col-right { flex-direction: row; flex-wrap: wrap; }
  .col-right > * { flex: 1 1 280px; }
  .row3 { grid-template-columns: 1fr 1fr; }
  .row3 .section-card:last-child { grid-column: span 2; }
}
@media (max-width: 1024px) {
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
  .row3 { grid-template-columns: 1fr; }
  .row3 .section-card:last-child { grid-column: auto; }
}
@media (max-width: 640px) {
  .kpi-row { grid-template-columns: 1fr; }
  .data-table { font-size: 11px; }
  .desc { max-width: 120px; }
}
</style>
