<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { listEvents } from '@/api/events'
import type { SecurityEvent } from '@/types/api'
import MetricCard from '@/components/common/MetricCard.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorBanner from '@/components/common/ErrorBanner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { formatDateTime } from '@/utils/format'

const loading = ref(true)
const events = ref<SecurityEvent[]>([])
const err = ref('')
const severity = ref('')
const limit = ref(50)

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

onMounted(load)
watch([severity, limit], load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>安全事件</h2>
        <div class="page-sub">数据源：<code>GET /api/v1/events</code> · 后端暂不支持关键词搜索，仅支持 severity 下拉筛选</div>
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
        <button class="btn" :disabled="loading" @click="load">
          <LoadingSpinner v-if="loading" :size="12" /><span v-else>🔄</span> 刷新
        </button>
      </div>
    </div>

    <!-- Summary cards -->
    <div v-if="events.length" class="metric-grid">
      <MetricCard name="总事件" :value="events.length" />
      <MetricCard name="CRITICAL" :value="events.filter(e => e.severity === 'CRITICAL').length" />
      <MetricCard name="HIGH" :value="events.filter(e => e.severity === 'HIGH').length" />
      <MetricCard name="MEDIUM" :value="events.filter(e => e.severity === 'MEDIUM').length" />
    </div>

    <ErrorBanner v-if="err" :message="err" />

    <EmptyState
      v-else-if="!loading && !err && !events.length"
      title="暂无事件"
      hint="先运行 `python scripts/demo_e2e.py` 或调用 POST /api/v1/events/seed 生成事件"
    />

    <div v-if="events.length" class="table-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th>event_id</th><th>severity</th><th>label</th><th>score</th>
            <th>asset</th><th>status</th><th>created_at</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in events" :key="e.event_id">
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
.page h2 { font-size: 18px; font-weight: 600; margin: 0 0 4px; }
.page-sub { font-size: 12px; color: #8a8fb8; }
.page-sub code { font-family: ui-monospace, Menlo, monospace; }
.toolbar { display: flex; gap: 8px; align-items: center; }
.input, .btn {
  background: #1f2340; border: 1px solid #2a2e4d; color: #e4e7f7;
  padding: 6px 10px; border-radius: 6px; font-size: 13px;
}
.btn { cursor: pointer; display: inline-flex; gap: 6px; align-items: center; }
.btn[disabled] { opacity: 0.6; cursor: not-allowed; }
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; }
.table-wrap { overflow: auto; border: 1px solid #2a2e4d; border-radius: 8px; max-height: calc(100vh - 280px); }
.tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.tbl th, .tbl td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #2a2e4d; }
.tbl th { background: #171a2e; color: #8a8fb8; position: sticky; top: 0; font-weight: 600; }
.tbl tbody tr:hover { background: #171a2e; }
.mono { font-family: ui-monospace, Menlo, monospace; color: #8a8fb8; }
.center { display: flex; gap: 10px; align-items: center; padding: 40px; color: #8a8fb8; }
</style>
