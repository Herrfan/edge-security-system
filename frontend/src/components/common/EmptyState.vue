<script setup lang="ts">
defineProps<{
  title?: string
  hint?: string
  kind?: 'empty' | 'offline' | 'blocked'
}>()
</script>

<template>
  <div class="empty">
    <div class="empty-icon">
      <span v-if="kind === 'offline'">🪐</span>
      <span v-else-if="kind === 'blocked'">🛑</span>
      <span v-else>📭</span>
    </div>
    <div class="empty-title">{{ title ?? '暂无数据' }}</div>
    <div v-if="hint" class="empty-hint">{{ hint }}</div>
    <slot name="actions" />
  </div>
</template>

<style scoped>
.empty { padding: 48px 20px; text-align: center; color: #8a8fb8; }
.empty-icon { font-size: 36px; margin-bottom: 10px; }
.empty-title { font-size: 15px; color: #c5c8e4; font-weight: 500; }
.empty-hint { font-size: 12px; margin-top: 6px; color: #6a70a0; line-height: 1.6; }
</style>
