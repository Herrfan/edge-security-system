<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    name: string
    value: number | string | null | undefined
    unit?: string
    sub?: string
    unavailable?: boolean
    tone?: 'default' | 'danger' | 'warn' | 'ok' | 'info'
    delta?: { dir: 'up' | 'down' | 'flat'; pct?: number }
  }>(),
  { unit: '', sub: '', unavailable: false, tone: 'default' },
)

const display = computed(() => {
  if (props.unavailable || props.value === null || props.value === undefined) return '—'
  if (typeof props.value === 'number') {
    if (props.value % 1 === 0) return props.value.toLocaleString()
    return props.value.toFixed(2)
  }
  return props.value
})

const toneClass = computed(() => `tone-${props.tone}`)
</script>

<template>
  <div class="metric-card" :class="[toneClass, { unavailable }]">
    <div class="m-head">
      <div class="metric-name">{{ name }}</div>
      <div v-if="delta" class="delta" :class="`dir-${delta.dir}`">
        <span class="arrow">{{ delta.dir === 'up' ? '↑' : delta.dir === 'down' ? '↓' : '→' }}</span>
        <span v-if="delta.pct != null" class="pct">{{ delta.pct }}%</span>
      </div>
    </div>
    <div class="m-value-row">
      <div class="metric-value">{{ display }}</div>
      <span v-if="unit" class="unit">{{ unit }}</span>
    </div>
    <div v-if="sub" class="metric-sub">{{ sub }}</div>
  </div>
</template>

<style scoped>
.metric-card {
  position: relative;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-4) var(--space-4) calc(var(--space-4) + 3px);
  display: flex; flex-direction: column; gap: 6px;
  overflow: visible;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.metric-card:hover { border-color: var(--border-strong); box-shadow: var(--shadow-hover); }

/* Tone-specific left accent bar */
.metric-card::before {
  content: '';
  position: absolute; left: 0; top: 0; bottom: 0;
  width: 3px;
  background: transparent;
  border-radius: var(--radius-lg) 0 0 var(--radius-lg);
}
.metric-card.tone-danger::before { background: var(--err); }
.metric-card.tone-warn::before  { background: var(--warn); }
.metric-card.tone-ok::before    { background: var(--ok); }
.metric-card.tone-info::before  { background: var(--accent); }

.metric-card.unavailable .metric-value { color: var(--text-dim); font-size: var(--fs-base); font-style: italic; }

.m-head { display: flex; align-items: center; justify-content: space-between; }
.metric-name { font-size: var(--fs-xs); color: var(--text-sub); text-transform: uppercase; letter-spacing: 0.8px; }

.delta { font-size: var(--fs-xs); display: inline-flex; align-items: center; gap: 2px; }
.delta.dir-up   { color: var(--err); }
.delta.dir-down { color: var(--ok); }
.delta.dir-flat { color: var(--text-dim); }

.m-value-row { display: flex; align-items: baseline; gap: 2px; }
.metric-value {
  font-size: 26px; font-weight: 700;
  color: var(--text-hi);
  font-family: var(--font-mono);
  line-height: 1;
  letter-spacing: 0.5px;
}
.metric-card.tone-danger .metric-value { color: var(--err); }
.metric-card.tone-warn  .metric-value { color: var(--warn); }
.metric-card.tone-ok    .metric-value { color: var(--ok); }
.metric-card.tone-info  .metric-value { color: var(--accent); }

.unit { font-size: var(--fs-sm); font-weight: 400; color: var(--text-sub); margin-left: 4px; }
.metric-sub { font-size: var(--fs-xs); color: var(--text-dim); margin-top: 2px; }
</style>
