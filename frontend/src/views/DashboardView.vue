<script setup lang="ts">
/**
 * DashboardView — Phase F3 态势总览.
 *
 * 3 parallel fetches via Promise.all:
 *   - GET  /api/v1/metrics/overview   → Metric cards (config/system/metrics)
 *   - GET  /api/v1/events?limit=50     → Recent events + severity distribution + trend
 *   - GET  /api/v1/policy-proposals?limit=5 → Recent policy candidates
 *
 * Charts (RiskDistributionChart, EventTrendChart) are labeled "前端推导" —
 * they are computed client-side from events timestamps, NOT backend stats.
 */
import { onMounted, ref } from 'vue'
import { metricsOverview } from '@/api/metrics'
import { listEvents } from '@/api/events'
import { listProposals } from '@/api/policies'
import RiskDistributionChart from '@/components/charts/RiskDistributionChart.vue'
import EventTrendChart from '@/components/charts/EventTrendChart.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import type { MetricsOverview, SecurityEvent, PolicyProposal } from '@/types/api'

function fmtInt(v: any): string {
  const n = typeof v === 'number' ? v : Number(v || 0)
  return Math.floor(n).toLocaleString()
}

const loading = ref(true)
const err = ref<string | null>(null)
const overview = ref<MetricsOverview | null>(null)
const events = ref<SecurityEvent[]>([])
const proposals = ref<PolicyProposal[]>([])

onMounted(async () => {
  try {
    loading.value = true
    err.value = null
    const [ov, ev, pr] = await Promise.all([
      metricsOverview(),
      listEvents({ limit: 50 }),
      listProposals(undefined, 5),
    ])
    overview.value = ov
    events.value = ev
    proposals.value = pr
  } catch (e: any) {
    err.value = e?.message || '加载 Dashboard 失败'
  } finally {
    loading.value = false
  }
})

// ---- config / system helpers (metrics/overview always has these) ----
const cfg = () => overview.value!.config as Record<string, any>
const sys = () => overview.value!.system!
const infoSeries = () => overview.value!.metrics['edgy_info']?.series?.[0] ?? null
</script>

<template>
  <div class="dash">
    <!-- Top config strip: edgy_info series + config block -->
    <section v-if="overview" class="cfg-strip">
      <div class="cfg-cell">
        <div class="cfg-lbl">App</div>
        <div class="cfg-val">{{ infoSeries()?.app_name ?? cfg()?.app_name }} <span class="cfg-sub">v{{ infoSeries()?.app_version ?? cfg()?.app_version }}</span></div>
      </div>
      <div class="cfg-cell">
        <div class="cfg-lbl">LLM</div>
        <div class="cfg-val">{{ infoSeries()?.llm_model ?? cfg()?.llm_model }} <span class="cfg-sub">@ {{ cfg()?.llm_provider }}</span></div>
      </div>
      <div class="cfg-cell">
        <div class="cfg-lbl">Embedding</div>
        <div class="cfg-val">{{ infoSeries()?.embedding_model ?? cfg()?.embedding_model }} <span class="cfg-sub">@ {{ infoSeries()?.vector_backend ?? cfg()?.vector_backend }}</span></div>
      </div>
      <div class="cfg-cell">
        <div class="cfg-lbl">允许真实执行</div>
        <div class="cfg-val">
          <span :class="cfg()?.allow_real_execution ? 'badge-danger' : 'badge-ok'">
            {{ cfg()?.allow_real_execution ? 'ON (风险!)' : 'FALSE (安全)' }}
          </span>
        </div>
      </div>
    </section>

    <!-- Metric cards row — config + system + 4 edgy_* counters (mostly unavailable until triggered) -->
    <section v-if="overview" class="metric-row">
      <div class="metric-card">
        <div class="m-label">系统 CPU</div>
        <div class="m-value">{{ sys()?.cpu_percent ?? '—' }}<span class="m-unit">%</span></div>
        <div class="m-sub">{{ sys()?.cpu_status }}</div>
      </div>
      <div class="metric-card">
        <div class="m-label">内存 RSS</div>
        <div class="m-value">{{ sys()?.rss_bytes != null ? (sys()!.rss_bytes! / 1024 / 1024).toFixed(1) : '—' }}<span class="m-unit">MB</span></div>
        <div class="m-sub">{{ sys()?.rss_status }}</div>
      </div>
      <div class="metric-card">
        <div class="m-label">检测次数</div>
        <div class="m-value">{{ fmtInt(overview.metrics['edgy_detections_total']?.series?.[0]?.value ?? 0) }}</div>
        <div class="m-sub">{{ overview.metrics['edgy_detections_total']?.status ?? 'unavailable' }}</div>
      </div>
      <div class="metric-card">
        <div class="m-label">Seed 事件数</div>
        <div class="m-value">{{ fmtInt(overview.metrics['edgy_events_seeded_total']?.series?.[0]?.value ?? 0) }}</div>
        <div class="m-sub">{{ overview.metrics['edgy_events_seeded_total']?.status ?? 'unavailable' }}</div>
      </div>
      <div class="metric-card">
        <div class="m-label">RAG 运行数</div>
        <div class="m-value">{{ fmtInt(overview.metrics['edgy_rag_runs_total']?.series?.[0]?.value ?? 0) }}</div>
        <div class="m-sub">{{ overview.metrics['edgy_rag_runs_total']?.status ?? 'unavailable' }}</div>
      </div>
      <div class="metric-card">
        <div class="m-label">检索调用</div>
        <div class="m-value">{{ fmtInt(overview.metrics['edgy_retrieval_calls_total']?.series?.[0]?.value ?? 0) }}</div>
        <div class="m-sub">{{ overview.metrics['edgy_retrieval_calls_total']?.status ?? 'unavailable' }}</div>
      </div>
    </section>

    <!-- Charts row -->
    <section class="charts-row">
      <RiskDistributionChart :events="events" />
      <EventTrendChart :events="events" />
    </section>

    <!-- Recent tables -->
    <section class="tables-row">
      <div class="table-card">
        <div class="tc-head">
          <span class="tc-title">最近事件</span>
          <span class="tc-sub">events?limit=50</span>
        </div>
        <table v-if="events.length" class="data-table">
          <thead>
            <tr><th>ID</th><th>Severity</th><th>Type</th><th>Description</th></tr>
          </thead>
          <tbody>
            <tr v-for="e in events.slice(0, 8)" :key="e.event_id">
              <td class="mono">{{ e.event_id.slice(-10) }}</td>
              <td><StatusTag :severity="e.severity">{{ e.severity }}</StatusTag></td>
              <td>{{ e.predicted_label }}</td>
              <td class="desc">{{ e.flow_summary ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-mini">暂无事件</div>
      </div>

      <div class="table-card">
        <div class="tc-head">
          <span class="tc-title">最近策略候选</span>
          <span class="tc-sub">policy-proposals?limit=5</span>
        </div>
        <table v-if="proposals.length" class="data-table">
          <thead>
            <tr><th>ID</th><th>Status</th><th>Action</th><th>Risk</th></tr>
          </thead>
          <tbody>
            <tr v-for="p in proposals" :key="p.policy_id">
              <td class="mono">{{ p.policy_id.slice(-10) }}</td>
              <td><StatusTag :status="p.status">{{ p.status }}</StatusTag></td>
              <td>{{ p.action_type }}</td>
              <td><StatusTag :severity="p.risk_level">{{ p.risk_level }}</StatusTag></td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-mini">暂无策略候选</div>
      </div>
    </section>

    <!-- Loading / Error -->
    <div v-if="loading" class="overlay">加载 Dashboard 中…</div>
    <div v-else-if="err" class="overlay err">❌ {{ err }}</div>
  </div>
</template>

<style scoped>
.dash { display: flex; flex-direction: column; gap: 16px; padding: 0; }
.cfg-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.cfg-cell { background: #11132a; border: 1px solid #2a2e4d; border-radius: 10px; padding: 10px 14px; }
.cfg-lbl { font-size: 10px; text-transform: uppercase; color: #8a8fb8; letter-spacing: 1.2px; margin-bottom: 2px; }
.cfg-val { font-size: 13px; color: #e4e7f7; font-weight: 600; }
.cfg-sub { color: #8a8fb8; font-weight: 400; font-size: 11px; margin-left: 4px; }

.badge-ok { background: rgba(41, 195, 139, 0.15); color: #29c38b; padding: 1px 8px; border-radius: 10px; font-size: 11px; border: 1px solid rgba(41, 195, 139, 0.4); }
.badge-danger { background: rgba(255, 90, 95, 0.15); color: #ff5a5f; padding: 1px 8px; border-radius: 10px; font-size: 11px; border: 1px solid rgba(255, 90, 95, 0.4); }

.metric-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; }
.metric-card { background: #11132a; border: 1px solid #2a2e4d; border-radius: 10px; padding: 12px 14px; display: flex; flex-direction: column; gap: 4px; }
.m-label { font-size: 10px; text-transform: uppercase; color: #8a8fb8; letter-spacing: 1.2px; }
.m-value { font-size: 22px; font-weight: 700; color: #e4e7f7; letter-spacing: 0.5px; }
.m-unit { font-size: 11px; color: #8a8fb8; font-weight: 400; margin-left: 3px; }
.m-sub { font-size: 11px; color: #8a8fb8; }

.charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

.tables-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.table-card { background: #11132a; border: 1px solid #2a2e4d; border-radius: 10px; padding: 12px 14px; }
.tc-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }
.tc-title { font-size: 13px; font-weight: 600; color: #e4e7f7; }
.tc-sub { font-size: 10px; color: #8a8fb8; }

.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th { text-align: left; padding: 6px 8px; border-bottom: 1px solid #2a2e4d; color: #8a8fb8; font-weight: 500; text-transform: uppercase; font-size: 10px; letter-spacing: 0.8px; }
.data-table td { padding: 6px 8px; border-bottom: 1px solid #1a1d36; color: #c3c7dc; }
.data-table tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: rgba(79, 140, 255, 0.06); }
.mono { font-family: ui-monospace, Consolas, monospace; color: #8a8fb8; }
.desc { color: #a9aed0; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.empty-mini { padding: 30px 0; text-align: center; color: #8a8fb8; font-size: 13px; }
.overlay { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(8, 9, 21, 0.8); z-index: 100; color: #e4e7f7; }
.overlay.err { color: #ff5a5f; }
</style>
