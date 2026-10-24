<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { health, metricsOverview } from '@/api/metrics'
import type { HealthInfo, MetricsOverview } from '@/types/api'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorBanner from '@/components/common/ErrorBanner.vue'
import DataSourceBadge from '@/components/common/DataSourceBadge.vue'

const loading = ref(true)
const h = ref<HealthInfo | null>(null)
const overview = ref<MetricsOverview | null>(null)
const err = ref('')

async function load() {
  loading.value = true
  err.value = ''
  try {
    const [hv, ov] = await Promise.all([health(), metricsOverview()])
    h.value = hv
    overview.value = ov
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
        <h2>系统设置</h2>
        <div class="page-sub">
          <DataSourceBadge kind="live" />
          <span>数据源：<code>GET /health</code> + <code>GET /api/v1/metrics/overview</code></span>
        </div>
        <div class="page-note">
          F1 骨架：仅展示运行时健康状态与配置快照。敏感配置（鉴权密钥、模型 API Key、VictoriaMetrics remote-write）由后端 <code>.env</code> 管理，前端永不暴露。
        </div>
      </div>
      <button class="btn" :disabled="loading" @click="load">
        <LoadingSpinner v-if="loading" :size="12" /><span v-else>🔄</span> 刷新
      </button>
    </div>

    <ErrorBanner v-if="err" :message="err" />

    <div v-if="h || overview" class="grid">
      <div class="panel">
        <div class="panel-title">健康状态</div>
        <div v-if="h" class="kv">
          <div><span>status</span><code :class="{ ok: h.status === 'ok' }">{{ h.status }}</code></div>
          <div><span>service</span><code>{{ h.service }}</code></div>
          <div><span>version</span><code>{{ h.version }}</code></div>
          <div><span>python</span><code>{{ h.python }}</code></div>
          <div><span>pid</span><code>{{ h.pid }}</code></div>
        </div>
      </div>

      <div v-if="overview?.config" class="panel">
        <div class="panel-title">后端配置快照</div>
        <pre class="pre">{{ JSON.stringify(overview.config, null, 2) }}</pre>
      </div>

      <div v-if="overview?.system" class="panel">
        <div class="panel-title">系统状态</div>
        <pre class="pre">{{ JSON.stringify(overview.system, null, 2) }}</pre>
      </div>
    </div>

    <div class="safety-panel">
      <div class="safety-title">🛡 产品级安全边界（前端永不绕过）</div>
      <ul class="safety-list">
        <li><code>allow_real_execution = false</code> 默认 DRY_RUN，前端无"真实执行"按钮</li>
        <li>审批严格遵循后端状态机：仅 NEEDS_APPROVAL → APPROVED/REJECTED，非法状态返回 409</li>
        <li>Dry-run 明确提示"不修改任何真实防火墙"</li>
        <li>前端校验仅为 UX，后端独立完成全部敏感操作校验</li>
        <li>LLM 生成的策略与 Shell 命令永不经前端直接执行</li>
        <li>前端永不在 localStorage 存储密码、JWT、凭证</li>
      </ul>
    </div>

    <div v-if="loading && !h && !overview" class="center">
      <LoadingSpinner :size="28" /> <span class="loading-tip">加载设置…</span>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 0; }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.page h2 { font-size: 18px; font-weight: 600; margin: 0 0 4px; }
.page-sub { font-size: 12px; color: var(--text-sub); margin-bottom: 6px; }
.page-sub code { font-family: var(--font-mono); }
.page-note { font-size: 12px; color: var(--warn); background: rgba(245, 158, 11, 0.08); padding: 6px 10px; border-radius: 6px; display: inline-block; }
.page-note code { font-family: var(--font-mono); }
.btn {
  background: var(--bg-surface); color: var(--text-hi); border: 1px solid var(--border);
  padding: 6px 10px; border-radius: 6px; font-size: 13px; cursor: pointer;
  display: inline-flex; gap: 6px; align-items: center;
}
.btn[disabled] { opacity: 0.6; cursor: not-allowed; }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
.panel { background: var(--bg-panel); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; }
.panel-title { font-size: 12px; color: var(--text-sub); font-weight: 600; margin-bottom: 10px; letter-spacing: 0.5px; text-transform: uppercase; }
.kv { display: flex; flex-direction: column; gap: 6px; }
.kv > div { display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
.kv span { color: var(--text-sub); }
.kv code { font-family: var(--font-mono); color: var(--text-mid); font-size: 12px; background: var(--bg-surface); padding: 2px 6px; border-radius: 3px; }
.kv code.ok { color: var(--ok); }
.pre { font-family: var(--font-mono); font-size: 11px; color: var(--text-mid); margin: 0; white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow: auto; }
.safety-panel {
  background: rgba(245, 158, 11, 0.05);
  border: 1px solid rgba(245, 158, 11, 0.25);
  border-radius: 8px;
  padding: 14px 18px;
}
.safety-title { font-size: 13px; font-weight: 600; color: var(--warn); margin-bottom: 10px; }
.safety-list { margin: 0; padding-left: 18px; font-size: 12px; color: var(--text-mid); line-height: 1.8; }
.safety-list code { font-family: var(--font-mono); background: var(--bg-surface); padding: 1px 5px; border-radius: 3px; color: var(--warn); }
.center { display: flex; gap: 10px; align-items: center; justify-content: center; padding: 40px; color: var(--text-sub); }
.loading-tip { font-size: 13px; }

/* F6 responsive */
@media (max-width: 768px) {
  .grid { grid-template-columns: 1fr; }
  .page-head { flex-direction: column; align-items: stretch; }
}
</style>
