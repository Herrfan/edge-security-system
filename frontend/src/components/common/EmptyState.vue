<script setup lang="ts">
defineProps<{
  title?: string
  hint?: string
  kind?: 'empty' | 'offline' | 'blocked' | 'loading' | 'error'
}>()
</script>

<template>
  <div class="empty">
    <div class="empty-icon">
      <span v-if="kind === 'offline'">🪐</span>
      <span v-else-if="kind === 'blocked'">🛑</span>
      <span v-else-if="kind === 'error'">⚠️</span>
      <span v-else-if="kind === 'loading'">⏳</span>
      <span v-else>📭</span>
    </div>
    <div class="empty-title">{{ title ?? '暂无数据' }}</div>
    <div v-if="hint" class="empty-hint">{{ hint }}</div>
    <slot name="actions" />
  </div>
</template>

<style scoped>
.empty {
  padding: 48px 20px; text-align: center;
  color: var(--text-sub);
}
.empty-icon { font-size: 36px; margin-bottom: var(--space-3); }
.empty-title { font-size: var(--fs-lg); color: var(--text-mid); font-weight: 500; }
.empty-hint { font-size: var(--fs-sm); margin-top: var(--space-2); color: var(--text-dim); line-height: 1.6; }
</style>
