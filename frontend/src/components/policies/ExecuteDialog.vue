<script setup lang="ts">
/**
 * Execute a policy in DRY_RUN mode ONLY.
 * The UI explicitly does NOT expose REAL mode — this is a product-level safety boundary.
 * Backend still accepts REAL + approval_token, but frontend never shows it.
 */
import { ref } from 'vue'
import { executeProposal } from '@/api/policies'
import type { ExecutionRecord } from '@/types/api'

const props = defineProps<{ policyId: string }>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'done'): void
}>()

const executing = ref(false)
const result = ref<(ExecutionRecord & { validator_reasons?: string[] }) | null>(null)
const err = ref('')

async function run() {
  executing.value = true
  err.value = ''
  result.value = null
  try {
    result.value = await executeProposal(props.policyId, 'DRY_RUN')
  } catch (e) {
    err.value = (e as Error).message
  } finally {
    executing.value = false
  }
}
</script>

<template>
  <div class="mask" @click.self="$emit('close')">
    <div class="dialog">
      <div class="title">干跑执行 · <code class="mono">{{ policyId }}</code></div>

      <!-- Safety banner -->
      <div class="safety">
        <span class="safety-icon">🛡️</span>
        <div>
          <strong>DRY_RUN 模式（默认）</strong>
          <div class="safety-sub">
            仅模拟执行，输出将应用的防火墙规则 <strong>预览</strong>；
            <span class="warn-text">不修改任何真实防火墙 / 安全设备</span>。
          </div>
        </div>
      </div>

      <!-- Run button -->
      <button class="btn btn-run" :disabled="executing" @click="run">
        {{ executing ? '执行中…' : '▶ 开始干跑执行 (DRY_RUN)' }}
      </button>

      <!-- Result -->
      <div v-if="result" class="result">
        <div class="result-row">
          <span class="lbl">execution_id</span>
          <code class="mono">{{ result.execution_id }}</code>
        </div>
        <div class="result-row">
          <span class="lbl">status</span>
          <code class="mono status" :class="result.status.toLowerCase()">{{ result.status }}</code>
        </div>
        <div class="result-row">
          <span class="lbl">mode</span>
          <code class="mono">{{ result.mode }}</code>
        </div>
        <div class="result-row" v-if="result.duration_ms != null">
          <span class="lbl">duration</span>
          <code class="mono">{{ result.duration_ms.toFixed(1) }} ms</code>
        </div>
        <div v-if="result.stdout_summary" class="section">
          <div class="section-title">stdout_summary</div>
          <pre class="pre">{{ result.stdout_summary }}</pre>
        </div>
        <div v-if="result.stderr_summary" class="section">
          <div class="section-title">stderr_summary</div>
          <pre class="pre stderr">{{ result.stderr_summary }}</pre>
        </div>
        <div v-if="result.validator_reasons?.length" class="section">
          <div class="section-title">validator_reasons</div>
          <div class="reasons">
            <div v-for="(r, i) in result.validator_reasons" :key="i">{{ r }}</div>
          </div>
        </div>
      </div>

      <div v-if="err" class="error-banner">⚠ {{ err }}</div>

      <div class="btns">
        <button class="btn btn-close" @click="$emit('close')">{{ result || err ? '关闭' : '取消' }}</button>
      </div>

      <div class="foot-note">
        真实执行（REAL mode）需后端显式触发并携带 approval_token，前端永不暴露此按钮。
      </div>
    </div>
  </div>
</template>

<style scoped>
.mask {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.6);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.dialog {
  background: var(--bg-nav); border: 1px solid var(--border); border-radius: 10px;
  min-width: 480px; max-width: 560px; padding: 20px 24px; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
}
.title { font-size: 15px; font-weight: 600; color: var(--text-mid); margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
.mono { font-family: var(--font-mono); background: var(--bg-surface); padding: 2px 6px; border-radius: 3px; color: var(--text-sub); font-size: 12px; }

.safety {
  display: flex; gap: 12px; align-items: flex-start;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.25);
  border-radius: 6px; padding: 12px 14px; margin-bottom: 16px;
}
.safety-icon { font-size: 20px; }
.safety strong { color: var(--ok); font-size: 13px; }
.safety-sub { font-size: 12px; color: var(--text-mid); margin-top: 4px; }
.warn-text { color: var(--warn); font-weight: 600; }

.btn-run {
  background: var(--accent); color: #fff; border: none; padding: 10px 18px; border-radius: 6px;
  font-size: 13px; font-weight: 600; cursor: pointer; width: 100%; margin-bottom: 16px;
}
.btn-run:disabled { opacity: 0.5; cursor: not-allowed; }

.result { display: flex; flex-direction: column; gap: 6px; font-size: 12px; }
.result-row { display: flex; gap: 10px; align-items: center; }
.lbl { color: var(--text-sub); min-width: 80px; }
.mono { font-family: var(--font-mono); color: var(--text-mid); font-size: 12px; }
.mono.status { font-weight: 600; padding: 2px 8px; border-radius: 4px; }
.mono.status.succeeded, .mono.status.executed { background: rgba(16, 185, 129, 0.15); color: var(--ok); }
.mono.status.failed, .mono.status.rolled_back { background: rgba(240, 68, 82, 0.15); color: var(--err); }
.section { display: flex; flex-direction: column; gap: 4px; margin-top: 8px; }
.section-title { font-size: 11px; color: var(--text-sub); text-transform: uppercase; letter-spacing: 0.5px; }
.pre { background: var(--bg-panel); padding: 8px 10px; border-radius: 4px; font-family: var(--font-mono); font-size: 11px; color: var(--text-mid); white-space: pre-wrap; word-break: break-all; margin: 0; }
.pre.stderr { color: var(--err); }
.reasons { display: flex; flex-direction: column; gap: 2px; color: var(--warn); font-size: 12px; padding-left: 12px; }

.error-banner { background: rgba(240, 68, 82, 0.1); border: 1px solid rgba(240, 68, 82, 0.3); color: var(--err); padding: 10px 14px; border-radius: 6px; font-size: 12px; margin-top: 10px; }

.btns { display: flex; justify-content: flex-end; margin-top: 14px; }
.btn-close { background: var(--bg-surface); color: var(--text-mid); border: 1px solid var(--border); padding: 7px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; }
.foot-note { margin-top: 14px; font-size: 11px; color: var(--text-dim); line-height: 1.5; }
</style>
