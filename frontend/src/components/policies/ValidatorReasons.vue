<script setup lang="ts">
/**
 * Displays deterministic validation results for a policy proposal.
 * Is_valid = green + checkmark; reasons as bullet list.
 */
defineProps<{
  isValid: boolean
  reasons: string[]
}>()
</script>

<template>
  <div class="validator" :class="{ 'is-valid': isValid, 'is-invalid': !isValid }">
    <div class="validator-head">
      <span class="indicator">{{ isValid ? '✓' : '✗' }}</span>
      <span class="label">
        Validator: <strong>{{ isValid ? 'PASSED' : 'BLOCKED' }}</strong>
      </span>
    </div>
    <div v-if="reasons?.length" class="reasons">
      <div v-for="(r, i) in reasons" :key="i" class="reason">
        {{ r }}
      </div>
    </div>
    <div v-else class="no-reasons">No validator messages.</div>
  </div>
</template>

<style scoped>
.validator {
  background: var(--bg-nav); border-radius: 6px; padding: 10px 12px;
  border: 1px solid;
}
.validator.is-valid   { border-color: rgba(16, 185, 129, 0.35); }
.validator.is-invalid { border-color: rgba(240, 68, 82, 0.35); }
.validator-head { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; font-size: 12px; }
.indicator {
  width: 18px; height: 18px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 12px;
}
.is-valid   .indicator { background: rgba(16, 185, 129, 0.2); color: var(--ok); }
.is-invalid .indicator { background: rgba(240, 68, 82, 0.2);  color: var(--err); }
.is-valid   .label strong { color: var(--ok); }
.is-invalid .label strong { color: var(--err); }
.label { color: var(--text-mid); }
.reasons { display: flex; flex-direction: column; gap: 3px; font-size: 12px; }
.reason { color: var(--warn); padding-left: 12px; position: relative; }
.reason::before { content: '▸'; position: absolute; left: 0; color: var(--warn); }
.no-reasons { color: var(--text-dim); font-style: italic; font-size: 11px; }
</style>
