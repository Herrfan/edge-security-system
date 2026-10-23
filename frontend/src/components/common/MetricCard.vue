<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    name: string
    value: number | string | null | undefined
    unit?: string
    sub?: string
    unavailable?: boolean
  }>(),
  { unit: '', sub: '', unavailable: false },
)

const display = computed(() => {
  if (props.unavailable || props.value === null || props.value === undefined) return '—'
  return typeof props.value === 'number' ? (props.value % 1 === 0 ? props.value.toFixed(0) : props.value.toFixed(2)) : props.value
})
</script>

<template>
  <div class="metric-card" :class="{ unavailable }">
    <div class="metric-name">{{ name }}</div>
    <div class="metric-value">{{ display }}<span v-if="unit" class="unit">{{ unit }}</span></div>
    <div v-if="sub" class="metric-sub">{{ sub }}</div>
  </div>
</template>

<style scoped>
.metric-card {
  background: #171a2e;
  border: 1px solid #2a2e4d;
  border-radius: 8px;
  padding: 14px 16px;
  display: flex; flex-direction: column; gap: 4px;
}
.metric-card.unavailable .metric-value { color: #5a5f8a; font-size: 14px; font-style: italic; }
.metric-name { font-size: 12px; color: #8a8fb8; font-family: ui-monospace, Menlo, monospace; }
.metric-value { font-size: 26px; font-weight: 700; color: #4f8cff; font-family: ui-monospace, Menlo, monospace; line-height: 1.1; }
.unit { font-size: 13px; font-weight: 400; color: #8a8fb8; margin-left: 4px; }
.metric-sub { font-size: 11px; color: #5a5f8a; margin-top: 2px; }
</style>
