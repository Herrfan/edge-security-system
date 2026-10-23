<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { metricsOverview } from '@/api/metrics'
import type { MetricsOverview } from '@/types/api'
import MetricCard from '@/components/common/MetricCard.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorBanner from '@/components/common/ErrorBanner.vue'
import DataSourceBadge from '@/components/common/DataSourceBadge.vue'

const loading = ref(true)
const overview = ref<MetricsOverview | null>(null)
const err = ref('')
const refreshedAt = ref<string>('')

async function load() {
  loading.value = true
  err.value = ''
  try {
    overview.value = await metricsOverview()
    refreshedAt.value = new Date().toLocaleString()
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
        <h2>安全态势总览</h2>
        <div class="page-sub">
          <DataSourceBadge kind="live" />
          <span class="sub-text">数据源：<code>/api/v1/metrics/overview</code></span>
          <span v-if="refreshedAt" class="sub-text">· 更新 {{ refreshedAt }}</span>
        </div>
      </div>
      <button class="btn" :disabled="loading" @click="load">
        <LoadingSpinner v-if="loading" :size="12" />
        <span v-else>🔄</span> 刷新
      </button>
    </div>

    <ErrorBanner v-if="err" :message="err" />

    <!-- Info + System + Config -->
    <div v-if="overview" class="grid">
      <div class="panel">
        <div class="panel-title">后端信息</div>
        <pre class="pre">{{ JSON.stringify(overview.info, null, 2) }}</pre>
      </div>
      <div class="panel">
        <div class="panel-title">系统状态</div>
        <pre class="pre">{{ JSON.stringify(overview.system, null, 2) }}</pre>
      </div>
      <div class="panel">
        <div class="panel-title">运行配置</div>
        <pre class="pre">{{ JSON.stringify(overview.config, null, 2) }}</pre>
      </div>
    </div>

    <!-- Metric cards -->
    <div v-if="overview?.metrics" class="metric-grid">
      <MetricCard
        v-for="(block, key) in overview.metrics"
        :key="key"
        :name="key"
        :value="block.series?.[0]?.value ?? null"
        :sub="`${block.series?.length ?? 0} series`"
        :unavailable="!block.series?.length"
      />
    </div>

    <div v-if="loading && !overview" class="center">
      <LoadingSpinner :size="28" /> <span class="loading-tip">加载指标…</span>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 0; }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page h2 { font-size: 18px; font-weight: 600; margin: 0 0 4px; }
.page-sub { font-size: 12px; color: #8a8fb8; display: flex; gap: 10px; align-items: center; }
.sub-text code { font-family: ui-monospace, Menlo, monospace; }
.btn {
  background: #1f2340; color: #e4e7f7; border: 1px solid #2a2e4d;
  padding: 7px 14px; border-radius: 6px; font-size: 13px; cursor: pointer;
  display: inline-flex; gap: 6px; align-items: center;
}
.btn[disabled] { opacity: 0.6; cursor: not-allowed; }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
.panel { background: #171a2e; border: 1px solid #2a2e4d; border-radius: 8px; padding: 12px; }
.panel-title { font-size: 12px; color: #8a8fb8; font-weight: 600; margin-bottom: 8px; letter-spacing: 0.5px; }
.pre { font-family: ui-monospace, Menlo, monospace; font-size: 11px; color: #c5c8e4; margin: 0; white-space: pre-wrap; word-break: break-all; max-height: 140px; overflow: auto; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.center { display: flex; gap: 10px; align-items: center; justify-content: center; padding: 40px; color: #8a8fb8; }
.loading-tip { font-size: 13px; }
</style>
