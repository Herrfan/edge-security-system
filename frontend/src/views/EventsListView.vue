<script setup lang="ts">
/**
 * Events List — Phase F2 enhanced.
 * Closed loop from event side:
 *   seed events → filter list → pick event → generate policy → open proposals page.
 */
import { onMounted, ref } from 'vue'
import { listEvents, seedEvents } from '@/api/events'
import { generateProposal } from '@/api/policies'
import type { SecurityEvent } from '@/types/api'
import MetricCard from '@/components/common/MetricCard.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorBanner from '@/components/common/ErrorBanner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import DataSourceBadge from '@/components/common/DataSourceBadge.vue'
import { formatDateTime } from '@/utils/format'

const loading = ref(true)
const events = ref<SecurityEvent[]>([])
const err = ref('')
const severity = ref('')
const limit = ref(50)

const seedLoading = ref(false)
const seedMsg = ref('')
const seedErr = ref('')

const selectedEventId = ref<string | null>(null)
const genLoading = ref(false)
const genResult = ref<{ policy_id: string; action_type: string; evidence_count: number; retrieval_status: string; llm_provider: string; llm_is_mock: boolean; llm_latency_ms: number } | null>(null)
const genErr = ref('')

async function load() {
  loading.value = true
  err.value = ''
  try {
    events.value = await listEvents({ severity: severity.value || undefined, limit: limit.value })
  } catch (e) {
    err.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function doSeed() {
  seedLoading.value = true
  seedMsg.value = ''
  seedErr.value = ''
  try {
    const r = await seedEvents()
    seedMsg.value = `✓ seeded ${r.seeded_events} events via ${r.detector_id}`
    await load()
  } catch (e) {
    seedErr.value = (e as Error).message
  } finally {
    seedLoading.value = false
  }
}

async function doGenerate() {
  if (!selectedEventId.value) return
  genLoading.value = true
  genResult.value = null
  genErr.value = ''
  try {
    const r = await generateProposal(selectedEventId.value)
    genResult.value = {
      policy_id: r.proposal.policy_id,
      action_type: r.proposal.action_type,
      evidence_count: r.evidence_count,
      retrieval_status: r.retrieval_status,
      llm_provider: r.llm_provider,
      llm_is_mock: r.llm_is_mock,
      llm_latency_ms: r.llm_latency_ms,
    }
  } catch (e) {
    genErr.value = (e as Error).message
  } finally {
    genLoading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>安全事件</h2>
        <div class="page-sub">
          <DataSourceBadge kind="live" />
          <span>数据源：<code>GET /api/v1/events</code> · <code>POST /events/seed-default</code> · <code>POST /policy-proposal/generate</code></span>
        </div>
        <div class="page-note">
          F2 闭环：一键 seed 事件 → 选中事件 → 生成策略 → 跳转策略工作台审批 + 干跑。
        </div>
      </div>
      <div class="toolbar">
        <select v-model="severity" class="input">
          <option value="">全部 severity</option>
          <option>CRITICAL</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option><option>INFO</option>
        </select>
        <select v-model="limit" class="input">
          <option :value="20">limit=20</option>
          <option :value="50">limit=50</option>
          <option :value="200">limit=200</option>
        </select>
        <button class="btn btn-seed" :disabled="seedLoading" @click="doSeed">
          <LoadingSpinner v-if="seedLoading" :size="12" /><span v-else>🌱</span> Seed Events
        </button>
        <button class="btn" :disabled="loading" @click="load">
          <LoadingSpinner v-if="loading" :size="12" /><span v-else>🔄</span> 刷新
        </button>
      </div>
    </div>

    <ErrorBanner v-if="err" :message="err" />

    <div v-if="seedMsg" class="seed-ok">{{ seedMsg }}</div>
    <div v-if="seedErr" class="seed-err">⚠ {{ seedErr }}</div>

    <!-- Summary cards -->
    <div v-if="events.length" class="metric-grid">
      <MetricCard name="总事件" :value="events.length" />
      <MetricCard name="CRITICAL" :value="events.filter((e) => e.severity === 'CRITICAL').length" />
      <MetricCard name="HIGH" :value="events.filter((e) => e.severity === 'HIGH').length" />
      <MetricCard name="MEDIUM" :value="events.filter((e) => e.severity === 'MEDIUM').length" />
    </div>

    <!-- Generate row (shown when event selected) -->
    <div v-if="selectedEventId" class="gen-row">
      <div class="gen-title">为事件 <code>{{ selectedEventId }}</code> 生成策略提案</div>
      <button class="btn btn-gen" :disabled="genLoading" @click="doGenerate">
        <LoadingSpinner v-if="genLoading" :size="12" /><span v-else>🛡️</span> Generate via RAG
      </button>
      <button v-if="genResult" class="btn btn-goto" @click="$router.push('/policies')">→ 去策略工作台审批</button>
    </div>

    <div v-if="genResult" class="gen-result">
      <div class="gen-ok">
        ✓ 策略 <code>{{ genResult.policy_id }}</code> · {{ genResult.action_type }} · {{ genResult.evidence_count }} evidences
        · retrieval={{ genResult.retrieval_status }} · llm={{ genResult.llm_provider }} (mock={{ genResult.llm_is_mock }}, {{ genResult.llm_latency_ms.toFixed(0) }} ms)
      </div>
    </div>
    <div v-if="genErr" class="gen-err">⚠ {{ genErr }}</div>

    <EmptyState
      v-else-if="!loading && !err && !events.length"
      title="暂无事件"
      hint="点击「Seed Events」用内置 flows_sample.csv + rule-demo detector 生成事件"
    />

    <div v-if="events.length" class="table-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th style="width: 28px"></th>
            <th>event_id</th><th>severity</th><th>label</th><th>score</th>
            <th>asset</th><th>status</th><th>created_at</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="e in events"
            :key="e.event_id"
            :class="{ pickable: !selectedEventId, selected: selectedEventId === e.event_id }"
            @click="selectedEventId = selectedEventId === e.event_id ? null : e.event_id"
          >
            <td><input type="radio" :value="e.event_id" v-model="selectedEventId" @click.stop /></td>
            <td class="mono">{{ e.event_id }}</td>
            <td><StatusTag :severity="e.severity">{{ e.severity }}</StatusTag></td>
            <td>{{ e.predicted_label || '—' }}</td>
            <td>{{ (e.score ?? 0).toFixed(2) }}</td>
            <td>{{ e.asset_id || '—' }}</td>
            <td>{{ e.status || '—' }}</td>
            <td>{{ formatDateTime(e.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="loading && !err" class="center"><LoadingSpinner :size="24" /> <span>加载事件…</span></div>
  </div>
</template>

<style scoped>
.page { padding: 0; }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.page h2 { font-size: var(--fs-3xl); font-weight: 700; margin: 0 0 4px; color: var(--text-hi); }
.page-sub { font-size: var(--fs-sm); color: var(--text-sub); margin-bottom: 6px; }
.page-sub code { font-family: var(--font-mono); }
.page-note {
  font-size: var(--fs-xs); color: var(--warn);
  background: var(--warn-soft); padding: 6px 12px; border-radius: var(--radius-sm);
  border: 1px solid rgba(245, 158, 11, 0.3); display: inline-block;
}
.toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.input, .btn {
  background: var(--bg-surface); border: 1px solid var(--border); color: var(--text-hi);
  padding: 7px 12px; border-radius: var(--radius-sm); font-size: var(--fs-sm);
  transition: border-color 0.15s, background 0.15s;
}
.input:focus { border-color: var(--accent); }
.btn { cursor: pointer; display: inline-flex; gap: 6px; align-items: center; }
.btn:hover:not([disabled]) { border-color: var(--accent); }
.btn[disabled] { opacity: 0.55; cursor: not-allowed; }
.btn-seed {
  background: var(--ok-soft); color: var(--ok);
  border-color: rgba(16, 185, 129, 0.35);
}
.btn-seed:hover:not([disabled]) { background: rgba(16, 185, 129, 0.22); }

.seed-ok { background: var(--ok-soft); color: var(--ok); padding: 10px 14px; border-radius: var(--radius-md); margin-bottom: 12px; font-size: var(--fs-sm); border: 1px solid rgba(16, 185, 129, 0.3); }
.seed-err, .gen-err { background: var(--err-soft); color: var(--err); padding: 10px 14px; border-radius: var(--radius-md); margin-bottom: 12px; font-size: var(--fs-sm); border: 1px solid rgba(240, 68, 82, 0.3); }

.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; }

.gen-row {
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
  background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 14px 18px;
  margin-bottom: 12px;
}
.gen-title { color: var(--text-mid); font-size: var(--fs-sm); font-weight: 600; }
.gen-title code { font-family: var(--font-mono); background: var(--bg-panel); padding: 2px 8px; border-radius: var(--radius-sm); color: var(--accent); font-size: var(--fs-xs); }
.btn-gen { background: var(--accent); color: #fff; border: none; padding: 8px 16px; font-weight: 600; border-radius: var(--radius-sm); }
.btn-gen:hover:not([disabled]) { background: var(--accent-hover); }
.btn-goto { background: var(--warn); color: var(--bg-root); border: none; padding: 8px 16px; font-weight: 600; border-radius: var(--radius-sm); }

.gen-result { margin-bottom: 12px; }
.gen-ok {
  background: var(--ok-soft); color: var(--ok); padding: 12px 16px; border-radius: var(--radius-md);
  font-size: var(--fs-sm); border: 1px solid rgba(16, 185, 129, 0.3); line-height: 1.6;
}
.gen-ok code { font-family: var(--font-mono); background: rgba(16, 185, 129, 0.18); padding: 2px 6px; border-radius: var(--radius-sm); }

.table-wrap {
  overflow: auto; border: 1px solid var(--border); border-radius: var(--radius-lg);
  max-height: calc(100vh - 380px); background: var(--bg-panel);
}
.tbl { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); }
.tbl th, .tbl td { padding: 10px 12px; text-align: left; border-bottom: 1px solid rgba(30, 58, 95, 0.5); }
.tbl th {
  background: var(--bg-surface); color: var(--text-sub);
  position: sticky; top: 0; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.5px; font-size: var(--fs-xs);
}
.tbl tbody tr { cursor: pointer; transition: background 0.12s; }
.tbl tbody tr:hover.pickable { background: var(--bg-surface); }
.tbl tbody tr.selected { background: rgba(52, 120, 246, 0.12); }
.tbl td { color: var(--text-mid); }
.mono { font-family: var(--font-mono); color: var(--text-sub); }
.center { display: flex; gap: 10px; align-items: center; padding: 40px; color: var(--text-sub); }

@media (max-width: 768px) {
  .metric-grid { grid-template-columns: repeat(2, 1fr); }
  .page h2 { font-size: var(--fs-2xl); }
}
</style>
