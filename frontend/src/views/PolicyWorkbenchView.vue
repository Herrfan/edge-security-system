<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listProposals } from '@/api/policies'
import type { PolicyProposal } from '@/types/api'
import MetricCard from '@/components/common/MetricCard.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorBanner from '@/components/common/ErrorBanner.vue'
import DataSourceBadge from '@/components/common/DataSourceBadge.vue'
import { formatDateTime } from '@/utils/format'

const loading = ref(true)
const list = ref<PolicyProposal[]>([])
const err = ref('')

async function load() {
  loading.value = true
  err.value = ''
  try {
    list.value = await listProposals(undefined, 100)
  } catch (e) {
    err.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>策略工作台</h2>
        <div class="page-sub">
          <DataSourceBadge kind="live" />
          <span>数据源：<code>GET /api/v1/policy-proposals</code> · <code>POST /approve</code> · <code>POST /execute</code></span>
        </div>
        <div class="page-note">
          Phase F1 骨架：仅展示策略列表 + 基础统计。Phase F2 将接入审批、干跑、知识库检索、完整工作台。
        </div>
      </div>
      <button class="btn" :disabled="loading" @click="load">
        <LoadingSpinner v-if="loading" :size="12" /><span v-else>🔄</span> 刷新
      </button>
    </div>

    <ErrorBanner v-if="err" :message="err" />

    <div v-if="list.length" class="metric-grid">
      <MetricCard name="策略总数" :value="list.length" />
      <MetricCard name="待审批" :value="list.filter((p) => p.status === 'NEEDS_APPROVAL').length" />
      <MetricCard name="已批准" :value="list.filter((p) => p.status === 'APPROVED').length" />
      <MetricCard name="已驳回" :value="list.filter((p) => p.status === 'REJECTED').length" />
    </div>

    <div v-if="list.length" class="table-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th>policy_id</th><th>event_id</th><th>action_type</th>
            <th>status</th><th>risk_level</th><th>created_at</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in list" :key="p.policy_id">
            <td class="mono">{{ p.policy_id }}</td>
            <td class="mono">{{ p.event_id || '—' }}</td>
            <td>{{ p.action_type }}</td>
            <td><StatusTag v-if="p.status" :status="p.status">{{ p.status }}</StatusTag><span v-else>—</span></td>
            <td>{{ p.risk_level || '—' }}</td>
            <td>{{ formatDateTime(p.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else-if="!loading && !err" class="empty">
      <div class="empty-title">暂无策略提案</div>
      <div class="empty-hint">先在"安全事件"页面选中事件调用 <code>POST /api/v1/policy-proposal/generate</code> 生成策略</div>
    </div>

    <div v-if="loading && !err" class="center"><LoadingSpinner :size="24" /> <span>加载策略列表…</span></div>
  </div>
</template>

<style scoped>
.page { padding: 0; }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.page h2 { font-size: 18px; font-weight: 600; margin: 0 0 4px; }
.page-sub { font-size: 12px; color: #8a8fb8; margin-bottom: 6px; }
.page-sub code { font-family: ui-monospace, Menlo, monospace; }
.page-note { font-size: 12px; color: #ffb454; background: rgba(255, 180, 84, 0.08); padding: 6px 10px; border-radius: 6px; display: inline-block; }
.btn {
  background: #1f2340; color: #e4e7f7; border: 1px solid #2a2e4d;
  padding: 6px 10px; border-radius: 6px; font-size: 13px; cursor: pointer;
  display: inline-flex; gap: 6px; align-items: center;
}
.btn[disabled] { opacity: 0.6; cursor: not-allowed; }
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; }
.table-wrap { overflow: auto; border: 1px solid #2a2e4d; border-radius: 8px; max-height: calc(100vh - 280px); }
.tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.tbl th, .tbl td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #2a2e4d; }
.tbl th { background: #171a2e; color: #8a8fb8; position: sticky; top: 0; font-weight: 600; }
.tbl tbody tr:hover { background: #171a2e; }
.mono { font-family: ui-monospace, Menlo, monospace; color: #8a8fb8; }
.center { display: flex; gap: 10px; align-items: center; padding: 40px; color: #8a8fb8; }
.empty { padding: 40px; text-align: center; color: #8a8fb8; border: 1px dashed #2a2e4d; border-radius: 10px; background: #141729; }
.empty-title { font-size: 15px; color: #c5c8e4; margin-bottom: 8px; }
.empty-hint { font-size: 12px; }
.empty-hint code { background: #1f2340; padding: 2px 6px; border-radius: 3px; font-family: ui-monospace, Menlo, monospace; }
</style>
