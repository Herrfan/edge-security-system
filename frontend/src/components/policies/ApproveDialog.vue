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
  background: #141729; border: 1px solid #2a2e4d; border-radius: 10px;
  min-width: 440px; max-width: 520px; padding: 20px 24px; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
}
.title { font-size: 15px; font-weight: 600; color: #c5c8e4; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
.mono { font-family: ui-monospace, Menlo, monospace; background: #1f2340; padding: 2px 6px; border-radius: 3px; color: #8a8fb8; font-size: 12px; }
.row { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
.opt {
  display: flex; flex-direction: column; gap: 3px;
  padding: 10px 12px; border-radius: 6px; cursor: pointer;
  background: #171a2e; border: 1px solid #2a2e4d;
}
.opt.picked.approve { border-color: rgba(41, 195, 139, 0.6); background: rgba(41, 195, 139, 0.08); }
.opt.picked.reject  { border-color: rgba(255, 90, 95, 0.6); background: rgba(255, 90, 95, 0.08); }
.opt-label { font-weight: 600; color: #c5c8e4; }
.opt-desc { color: #8a8fb8; font-size: 12px; }
.opt input { display: none; }

.field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; }
.field label { font-size: 11px; color: #8a8fb8; text-transform: uppercase; letter-spacing: 0.5px; }
.field input {
  background: #171a2e; border: 1px solid #2a2e4d; color: #e4e7f7;
  padding: 7px 10px; border-radius: 5px; font-size: 13px; font-family: inherit;
}
.field input:focus { border-color: #4f8cff; outline: none; }

.result { padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; font-size: 12px; }
.result.ok  { background: rgba(41, 195, 139, 0.1); color: #29c38b; border: 1px solid rgba(41, 195, 139, 0.3); }
.result.err { background: rgba(255, 90, 95, 0.1);  color: #ff5a5f; border: 1px solid rgba(255, 90, 95, 0.3); }

.btns { display: flex; gap: 8px; justify-content: flex-end; }
.btn { padding: 7px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; border: none; }
.btn-cancel { background: #1f2340; color: #8a8fb8; border: 1px solid #2a2e4d; }
.btn-submit { background: #29c38b; color: #0f1120; font-weight: 600; }
.btn-close  { background: #4f8cff; color: #fff; font-weight: 600; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.warn { margin-top: 14px; font-size: 11px; color: #5a5f8a; line-height: 1.5; }
.warn strong { color: #ffb454; }
</style>
