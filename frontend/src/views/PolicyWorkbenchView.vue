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
.page h2 { font-size: var(--fs-3xl); font-weight: 700; margin: 0 0 4px; color: var(--text-hi); }
.page-sub { font-size: var(--fs-sm); color: var(--text-sub); margin-bottom: 6px; }
.page-sub code { font-family: var(--font-mono); }
.page-note {
  font-size: var(--fs-xs); color: var(--warn);
  background: var(--warn-soft); padding: 6px 12px; border-radius: var(--radius-sm);
  border: 1px solid rgba(245, 158, 11, 0.3); display: inline-block;
}
.toolbar { display: flex; gap: 8px; align-items: center; }
.input, .btn {
  background: var(--bg-surface); border: 1px solid var(--border); color: var(--text-hi);
  padding: 7px 12px; border-radius: var(--radius-sm); font-size: var(--fs-sm);
}
.input:focus { border-color: var(--accent); }
.btn { cursor: pointer; display: inline-flex; gap: 6px; align-items: center; }
.btn:hover:not([disabled]) { border-color: var(--accent); }
.btn[disabled] { opacity: 0.55; cursor: not-allowed; }

.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; }
.cards { display: flex; flex-direction: column; gap: 0; }

.center { display: flex; gap: 10px; align-items: center; padding: 40px; color: var(--text-sub); }
.empty {
  padding: 48px 24px; text-align: center;
  color: var(--text-sub);
  border: 1px dashed var(--border); border-radius: var(--radius-lg);
  background: var(--bg-surface);
}
.empty-title { font-size: var(--fs-xl); color: var(--text-mid); margin-bottom: var(--space-2); font-weight: 600; }
.empty-hint { font-size: var(--fs-sm); }
.empty-hint code { background: var(--bg-panel); padding: 2px 8px; border-radius: var(--radius-sm); font-family: var(--font-mono); }

@media (max-width: 768px) {
  .metric-grid { grid-template-columns: repeat(2, 1fr); }
  .page h2 { font-size: var(--fs-2xl); }
}
</style>
