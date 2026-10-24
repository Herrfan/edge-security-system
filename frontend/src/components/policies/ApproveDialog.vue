<script setup lang="ts">
/**
 * Approve or reject a policy that must currently be in NEEDS_APPROVAL state.
 * Calls POST /api/v1/policy-proposal/approve. Backend enforces the state machine;
 * frontend only collects approve=true/false + optional reason + approver display.
 */
import { ref } from 'vue'
import { approveProposal } from '@/api/policies'

const props = defineProps<{ policyId: string }>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'done'): void
}>()

const approve = ref(true)
const reason = ref('frontend operator approve')
const approver = ref('operator@edge.local')
const submitting = ref(false)
const result = ref<{ ok: boolean; status?: string; err?: string } | null>(null)

async function submit() {
  submitting.value = true
  result.value = null
  try {
    const r = await approveProposal(
      props.policyId,
      approve.value,
      reason.value || undefined,
      approver.value || undefined,
    )
    result.value = { ok: true, status: r.status }
  } catch (e) {
    const err = e as { message?: string; status?: number; detail?: string }
    result.value = { ok: false, err: err.detail || err.message || String(e) }
  } finally {
    submitting.value = false
  }
}

function handleDone() {
  emit('done')
  emit('close')
}
</script>

<template>
  <div class="mask" @click.self="$emit('close')">
    <div class="dialog">
      <div class="title">审批策略 · <code class="mono">{{ policyId }}</code></div>

      <!-- Approval choice -->
      <div class="row">
        <label class="opt" :class="{ picked: approve }" @click="approve = true">
          <input type="radio" v-model="approve" :value="true" />
          <span class="opt-label">✅ 批准</span>
          <span class="opt-desc">状态 NEEDS_APPROVAL → APPROVED，可执行</span>
        </label>
        <label class="opt" :class="{ picked: !approve }" @click="approve = false">
          <input type="radio" v-model="approve" :value="false" />
          <span class="opt-label">❌ 驳回</span>
          <span class="opt-desc">状态 NEEDS_APPROVAL → REJECTED，不可执行</span>
        </label>
      </div>

      <div class="field">
        <label>审批理由</label>
        <input v-model="reason" placeholder="audit note" maxlength="200" />
      </div>
      <div class="field">
        <label>审批人</label>
        <input v-model="approver" placeholder="operator@edge.local" maxlength="100" />
      </div>

      <!-- Result banner -->
      <div v-if="result" class="result" :class="{ ok: result.ok, err: !result.ok }">
        <div v-if="result.ok">
          ✓ {{ policyId }} → <strong>{{ result.status }}</strong> · 审批完成
        </div>
        <div v-else>⚠ {{ result.err }}</div>
      </div>

      <div class="btns">
        <button class="btn btn-cancel" :disabled="submitting" @click="$emit('close')">取消</button>
        <button class="btn btn-submit" :disabled="submitting || result?.ok" @click="submit">
          {{ submitting ? '提交中…' : (approve ? '批准' : '驳回') }}
        </button>
        <button v-if="result?.ok" class="btn btn-close" @click="handleDone">完成 · 关闭</button>
      </div>

      <div class="warn">
        后端强制状态机校验：仅 NEEDS_APPROVAL → APPROVED/REJECTED 合法，非法状态返回 <strong>409 Conflict</strong>。
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
  min-width: 440px; max-width: 520px; padding: 20px 24px; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
}
.title { font-size: 15px; font-weight: 600; color: var(--text-mid); margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
.mono { font-family: var(--font-mono); background: var(--bg-surface); padding: 2px 6px; border-radius: 3px; color: var(--text-sub); font-size: 12px; }
.row { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
.opt {
  display: flex; flex-direction: column; gap: 3px;
  padding: 10px 12px; border-radius: 6px; cursor: pointer;
  background: var(--bg-panel); border: 1px solid var(--border);
}
.opt.picked.approve { border-color: rgba(16, 185, 129, 0.6); background: rgba(16, 185, 129, 0.08); }
.opt.picked.reject  { border-color: rgba(240, 68, 82, 0.6); background: rgba(240, 68, 82, 0.08); }
.opt-label { font-weight: 600; color: var(--text-mid); }
.opt-desc { color: var(--text-sub); font-size: 12px; }
.opt input { display: none; }

.field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; }
.field label { font-size: 11px; color: var(--text-sub); text-transform: uppercase; letter-spacing: 0.5px; }
.field input {
  background: var(--bg-panel); border: 1px solid var(--border); color: var(--text-hi);
  padding: 7px 10px; border-radius: 5px; font-size: 13px; font-family: inherit;
}
.field input:focus { border-color: var(--accent); outline: none; }

.result { padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; font-size: 12px; }
.result.ok  { background: rgba(16, 185, 129, 0.1); color: var(--ok); border: 1px solid rgba(16, 185, 129, 0.3); }
.result.err { background: rgba(240, 68, 82, 0.1);  color: var(--err); border: 1px solid rgba(240, 68, 82, 0.3); }

.btns { display: flex; gap: 8px; justify-content: flex-end; }
.btn { padding: 7px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; border: none; }
.btn-cancel { background: var(--bg-surface); color: var(--text-sub); border: 1px solid var(--border); }
.btn-submit { background: var(--ok); color: var(--bg-root); font-weight: 600; }
.btn-close  { background: var(--accent); color: #fff; font-weight: 600; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.warn { margin-top: 14px; font-size: 11px; color: var(--text-dim); line-height: 1.5; }
.warn strong { color: var(--warn); }
</style>
