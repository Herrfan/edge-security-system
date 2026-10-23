<script setup lang="ts">
/**
 * Policy Workbench — Phase F2.
 * Full closed loop on policy side:
 *   list proposals → expand details → validate → approve → dry-run execute.
 * Generate can be triggered from EventsListView which passes event_id back via
 * the generate dialog in PolicyCandidateCard.
 */
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { listProposals } from '@/api/policies'
import type { PolicyProposal, PolicyStatus } from '@/types/api'
import MetricCard from '@/components/common/MetricCard.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorBanner from '@/components/common/ErrorBanner.vue'
import DataSourceBadge from '@/components/common/DataSourceBadge.vue'
import PolicyCandidateCard from '@/components/policies/PolicyCandidateCard.vue'

const loading = ref(true)
const list = ref<PolicyProposal[]>([])
const err = ref('')
const filterStatus = ref<string>('')

async function load() {
  loading.value = true
  err.value = ''
  try {
    const s = filterStatus.value as PolicyStatus | ''
    list.value = await listProposals(s || undefined, 200)
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
          <span>数据源：<code>GET /api/v1/policy-proposals</code> · <code>POST /approve</code> · <code>POST /execute</code> (DRY_RUN)</span>
        </div>
        <div class="page-note">
          F2 闭环：策略列表 → 展开详情 → validate → approve → dry-run execute。真实执行 (REAL) 前端永不暴露。
        </div>
      </div>
      <div class="toolbar">
        <select v-model="filterStatus" class="input" @change="load">
          <option value="">全部状态</option>
          <option>NEEDS_APPROVAL</option>
          <option>APPROVED</option>
          <option>REJECTED</option>
          <option>NEEDS_VALIDATION</option>
          <option>EXECUTED</option>
          <option>EXPIRED</option>
        </select>
        <button class="btn" :disabled="loading" @click="load">
          <LoadingSpinner v-if="loading" :size="12" /><span v-else>🔄</span> 刷新
        </button>
      </div>
    </div>

    <ErrorBanner v-if="err" :message="err" />

    <!-- Summary cards -->
    <div v-if="list.length" class="metric-grid">
      <MetricCard name="策略总数" :value="list.length" />
      <MetricCard name="待审批" :value="list.filter((p) => p.status === 'NEEDS_APPROVAL').length" />
      <MetricCard name="已批准" :value="list.filter((p) => p.status === 'APPROVED').length" />
      <MetricCard name="已驳回" :value="list.filter((p) => p.status === 'REJECTED').length" />
    </div>

    <!-- Empty state -->
    <div v-if="!loading && !err && !list.length" class="empty">
      <div class="empty-title">暂无策略提案</div>
      <div class="empty-hint">
        先去 <RouterLink to="/events">安全事件</RouterLink> 选中事件生成策略。
        一键：<code>python scripts/demo_e2e.py --steps 5</code>
      </div>
    </div>

    <!-- Policy cards -->
    <div v-if="list.length" class="cards">
      <PolicyCandidateCard
        v-for="p in list"
        :key="p.policy_id"
        :proposal="p"
        @refresh="load"
      />
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
.toolbar { display: flex; gap: 8px; align-items: center; }
.input, .btn {
  background: #1f2340; border: 1px solid #2a2e4d; color: #e4e7f7;
  padding: 6px 10px; border-radius: 6px; font-size: 13px;
}
.btn { cursor: pointer; display: inline-flex; gap: 6px; align-items: center; }
.btn[disabled] { opacity: 0.6; cursor: not-allowed; }
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; }
.cards { display: flex; flex-direction: column; gap: 0; }
.center { display: flex; gap: 10px; align-items: center; padding: 40px; color: #8a8fb8; }
.empty { padding: 40px; text-align: center; color: #8a8fb8; border: 1px dashed #2a2e4d; border-radius: 10px; background: #141729; }
.empty-title { font-size: 15px; color: #c5c8e4; margin-bottom: 8px; }
.empty-hint { font-size: 12px; }
.empty-hint code { background: #1f2340; padding: 2px 6px; border-radius: 3px; font-family: ui-monospace, Menlo, monospace; }
</style>
