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
  background: #141729; border-radius: 6px; padding: 10px 12px;
  border: 1px solid;
}
.validator.is-valid   { border-color: rgba(41, 195, 139, 0.35); }
.validator.is-invalid { border-color: rgba(255, 90, 95, 0.35); }
.validator-head { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; font-size: 12px; }
.indicator {
  width: 18px; height: 18px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 12px;
}
.is-valid   .indicator { background: rgba(41, 195, 139, 0.2); color: #29c38b; }
.is-invalid .indicator { background: rgba(255, 90, 95, 0.2);  color: #ff5a5f; }
.is-valid   .label strong { color: #29c38b; }
.is-invalid .label strong { color: #ff5a5f; }
.label { color: #c5c8e4; }
.reasons { display: flex; flex-direction: column; gap: 3px; font-size: 12px; }
.reason { color: #ffb454; padding-left: 12px; position: relative; }
.reason::before { content: '▸'; position: absolute; left: 0; color: #ffb454; }
.no-reasons { color: #5a5f8a; font-style: italic; font-size: 11px; }
</style>
