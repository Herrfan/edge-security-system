<script setup lang="ts">
defineProps<{ kind?: 'live' | 'offline' | 'demo' | 'blocked' }>()

const labelMap: Record<string, { text: string; cls: string }> = {
  live:    { text: '真实后端数据', cls: 'tag-live' },
  offline: { text: '离线实验数据', cls: 'tag-offline' },
  demo:    { text: '演示数据', cls: 'tag-demo' },
  blocked: { text: '未接入', cls: 'tag-blocked' },
}
</script>

<template>
  <span v-if="kind" class="ds-badge" :class="labelMap[kind].cls">{{ labelMap[kind].text }}</span>
</template>

<style scoped>
.ds-badge {
  display: inline-block; font-size: 11px; padding: 2px 7px; border-radius: 10px;
  font-weight: 600; letter-spacing: 0.5px;
}
.tag-live    { background: rgba(41, 195, 139, 0.15); color: #29c38b; }
.tag-offline { background: rgba(79, 140, 255, 0.15); color: #4f8cff; }
.tag-demo    { background: rgba(255, 180, 84, 0.18); color: #ffb454; }
.tag-blocked { background: rgba(255, 90, 95, 0.15); color: #ff5a5f; }
</style>
