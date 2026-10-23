<script setup lang="ts">
/**
 * Expandable policy candidate card.
 * Collapsed: summary row (id, event, action, status, risk).
 * Expanded: + params + rationale + evidence_ids + validator + approval/exec buttons.
 */
import { ref, computed } from 'vue'
import type { PolicyProposal, ValidationResult } from '@/types/api'
import StatusTag from '../common/StatusTag.vue'
import ValidatorReasons from './ValidatorReasons.vue'
import EvidenceChunk from './EvidenceChunk.vue'
import ApproveDialog from './ApproveDialog.vue'
import ExecuteDialog from './ExecuteDialog.vue'
import { validateProposal, generateProposal } from '@/api/policies'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{
  proposal: PolicyProposal
  evidences?: { chunk_id: string; document_id: string; source?: string; title?: string; content?: string; retrieval_score?: number; retrieval_method?: string }[]
  eventId?: string  // optional: event_id used to regenerate
}>()

const expanded = ref(false)
const validating = ref(false)
const validation = ref<ValidationResult | null>(null)
const genLoading = ref(false)
const genError = ref('')

// Approval + execution dialogs
const approveOpen = ref(false)
const executeOpen = ref(false)

const expandLabel = computed(() => expanded.value ? '收起 ▲' : '展开详情 ▼')

async function runValidate() {
  validating.value = true
  try {
    validation.value = await validateProposal(props.proposal.policy_id)
  } catch (e) {
    validation.value = { policy_id: props.proposal.policy_id, is_valid: false, reasons: [(e as Error).message] }
  } finally {
    validating.value = false
  }
}

async function regenerate() {
  if (!props.eventId) return
  genLoading.value = true
  genError.value = ''
  try {
    await generateProposal(props.eventId)
  } catch (e) {
    genError.value = (e as Error).message
  } finally {
    genLoading.value = false
  }
}
</script>

<template>
  <div class="card">
    <!-- Collapsed header (always visible) -->
    <div class="card-head" @click="expanded = !expanded">
      <span class="mono pid">{{ proposal.policy_id }}</span>
      <span class="evt">evt: <span class="mono">{{ proposal.event_id || '—' }}</span></span>
      <span class="act">{{ proposal.action_type }}</span>
      <StatusTag v-if="proposal.status" :status="proposal.status">{{ proposal.status }}</StatusTag>
      <span class="risk" v-if="proposal.risk_level">{{ proposal.risk_level }}</span>
      <span class="time">{{ formatDateTime(proposal.created_at) }}</span>
      <span class="expand-btn">{{ expandLabel }}</span>
    </div>

    <!-- Expanded section -->
    <div v-if="expanded" class="card-body" @click.stop>
      <!-- Parameters -->
      <div v-if="proposal.parameters && Object.keys(proposal.parameters).length" class="section">
        <div class="section-title">Parameters</div>
        <pre class="pre">{{ JSON.stringify(proposal.parameters, null, 2) }}</pre>
      </div>

      <!-- Rationale -->
      <div v-if="proposal.rationale" class="section">
        <div class="section-title">Rationale</div>
        <p class="rationale">{{ proposal.rationale }}</p>
      </div>

      <!-- Evidence IDs (from proposal.evidence_ids) -->
      <div v-if="proposal.evidence_ids?.length" class="section">
        <div class="section-title">Evidence IDs ({{ proposal.evidence_ids.length }})</div>
        <div class="ev-ids">
          <code v-for="eid in proposal.evidence_ids" :key="eid">{{ eid }}</code>
        </div>
      </div>

      <!-- Evidences from generate response -->
      <div v-if="evidences?.length" class="section">
        <div class="section-title">Retrieved Evidences ({{ evidences.length }})</div>
        <div class="ev-list">
          <EvidenceChunk v-for="ev in evidences" :key="ev.chunk_id" v-bind="ev" />
        </div>
      </div>

      <!-- Validator -->
      <div class="section">
        <div class="section-title">
          Validator
          <button v-if="!validation" class="mini-btn" :disabled="validating" @click="runValidate">
            {{ validating ? 'running…' : 'Run deterministic validate' }}
          </button>
        </div>
        <ValidatorReasons v-if="validation" :is-valid="validation.is_valid" :reasons="validation.reasons" />
        <div v-else class="placeholder">Click "Run deterministic validate" to check policy soundness.</div>
      </div>

      <!-- Actions: Approve + Dry-run Execute -->
      <div class="section actions">
        <button
          v-if="proposal.status === 'NEEDS_APPROVAL'"
          class="btn btn-approve"
          @click="approveOpen = true"
        >✅ Approve / Reject</button>

        <button
          v-if="proposal.status === 'APPROVED'"
          class="btn btn-exec"
          @click="executeOpen = true"
        >
          🔧 Execute (DRY_RUN — no real firewall change)
        </button>

        <span v-else-if="proposal.status === 'NEEDS_APPROVAL'" class="hint">— awaiting approval before execute —</span>
        <span v-else class="hint">— current status: {{ proposal.status }} —</span>

        <button v-if="eventId" class="mini-btn" :disabled="genLoading" @click="regenerate">
          {{ genLoading ? 'generating…' : '🔄 Regenerate' }}
        </button>
        <span v-if="genError" class="err">{{ genError }}</span>
      </div>
    </div>

    <!-- Dialogs -->
    <ApproveDialog v-if="approveOpen" :policy-id="proposal.policy_id" @close="approveOpen = false" @done="expanded = false" />
    <ExecuteDialog v-if="executeOpen" :policy-id="proposal.policy_id" @close="executeOpen = false" @done="expanded = false" />
  </div>
</template>

<style scoped>
.card {
  background: #171a2e;
  border: 1px solid #2a2e4d;
  border-radius: 8px;
  margin-bottom: 10px;
  overflow: hidden;
}
.card-head {
  display: flex; gap: 10px; align-items: center; padding: 10px 14px;
  cursor: pointer; font-size: 12px;
}
.card-head:hover { background: #1f2340; }
.mono { font-family: ui-monospace, Menlo, monospace; }
.pid { color: #4f8cff; font-size: 11px; font-weight: 600; }
.evt { color: #8a8fb8; }
.act { color: #c5c8e4; font-weight: 600; }
.risk { color: #ffb454; font-weight: 600; }
.time { margin-left: auto; color: #5a5f8a; font-family: ui-monospace, Menlo, monospace; font-size: 11px; }
.expand-btn { color: #8a8fb8; font-size: 11px; }

.card-body { border-top: 1px solid #2a2e4d; padding: 14px; display: flex; flex-direction: column; gap: 12px; }
.section { display: flex; flex-direction: column; gap: 6px; }
.section-title {
  font-size: 11px; color: #8a8fb8; letter-spacing: 0.5px; text-transform: uppercase;
  display: flex; justify-content: space-between; align-items: center;
}
.pre {
  background: #141729; border-radius: 4px; padding: 8px 10px;
  font-family: ui-monospace, Menlo, monospace; font-size: 11px; color: #c5c8e4;
  max-height: 180px; overflow: auto; margin: 0; white-space: pre-wrap; word-break: break-all;
}
.rationale { color: #c5c8e4; font-size: 13px; line-height: 1.6; margin: 0; background: #141729; padding: 8px 10px; border-radius: 4px; border-left: 2px solid #4f8cff; }
.ev-ids { display: flex; flex-wrap: wrap; gap: 6px; }
.ev-ids code { background: #141729; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-family: ui-monospace, Menlo, monospace; color: #8a8fb8; }
.ev-list { display: flex; flex-direction: column; gap: 8px; }
.placeholder { color: #5a5f8a; font-style: italic; font-size: 12px; padding: 6px 0; }

.actions { flex-direction: row; flex-wrap: wrap; gap: 8px; align-items: center; padding-top: 8px; border-top: 1px solid #2a2e4d; }
.btn { padding: 7px 14px; border-radius: 6px; font-size: 12px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; border: none; font-weight: 500; }
.btn-approve { background: rgba(41, 195, 139, 0.2); color: #29c38b; border: 1px solid rgba(41, 195, 139, 0.4); }
.btn-exec   { background: rgba(79, 140, 255, 0.2); color: #4f8cff; border: 1px solid rgba(79, 140, 255, 0.4); }
.mini-btn {
  background: transparent; color: #8a8fb8; border: 1px solid #2a2e4d;
  padding: 4px 10px; border-radius: 4px; font-size: 11px; cursor: pointer;
}
.mini-btn:hover { color: #c5c8e4; border-color: #3a3f65; }
.mini-btn[disabled] { opacity: 0.5; cursor: not-allowed; }
.hint { color: #5a5f8a; font-size: 11px; font-style: italic; }
.err { color: #ff5a5f; font-size: 11px; }
</style>
