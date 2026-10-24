<script setup lang="ts">
defineProps<{ kind?: 'live' | 'offline' | 'demo' | 'blocked' }>()

const labelMap: Record<string, { text: string; cls: string }> = {
  live:    { text: '真实后端', cls: 'tag-live' },
  offline: { text: '离线数据', cls: 'tag-offline' },
  demo:    { text: '演示模式', cls: 'tag-demo' },
  blocked: { text: '未接入', cls: 'tag-blocked' },
}
</script>

<template>
  <span v-if="kind" class="ds-badge" :class="labelMap[kind].cls">{{ labelMap[kind].text }}</span>
</template>

<style scoped>
.ds-badge {
  display: inline-block; font-size: 10px; padding: 2px 8px; border-radius: 10px;
  font-weight: 600; letter-spacing: 0.3px;
  border: 1px solid transparent;
}
.tag-live    { background: var(--ok-soft);     color: var(--ok);       border-color: rgba(16, 185, 129, 0.3); }
.tag-offline { background: var(--accent);      color: #fff; }
.tag-demo    { background: var(--warn-soft);   color: var(--warn);     border-color: rgba(245, 158, 11, 0.3); }
.tag-blocked { background: var(--err-soft);    color: var(--err);      border-color: rgba(240, 68, 82, 0.3); }
</style>
