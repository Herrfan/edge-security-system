<script setup lang="ts">
defineProps<{
  title: string
  hint?: string
  kind?: 'blocked' | 'offline' | 'demo'
}>()
</script>

<template>
  <div class="page">
    <h2 class="page-title">{{ title }}</h2>
    <div class="page-sub">
      <slot name="subtitle" />
    </div>

    <div class="ph-wrap">
      <div class="ph-icon">
        <span v-if="kind === 'blocked'">🛑 未接入</span>
        <span v-else-if="kind === 'demo'">🟡 演示数据</span>
        <span v-else-if="kind === 'offline'">💾 离线实验</span>
        <span v-else>📭 暂无数据</span>
      </div>
      <p v-if="hint" class="ph-hint">{{ hint }}</p>
      <p class="ph-note">
        后端对应能力尚未完整提供，或前端将在 Phase F2-F7 分阶段接入。
        具体阻塞项见 <code>docs/frontend-implementation-plan.md</code>。
      </p>
    </div>

    <slot />
  </div>
</template>

<style scoped>
.page { padding: 0; }
.page-title { font-size: 18px; font-weight: 600; margin: 0 0 4px; }
.page-sub { color: #8a8fb8; font-size: 12px; margin-bottom: 20px; }
.ph-wrap {
  border: 1px dashed #2a2e4d; border-radius: 10px; padding: 40px 30px;
  text-align: center; color: #8a8fb8; background: #141729;
}
.ph-icon { font-size: 16px; color: #ffb454; font-weight: 600; margin-bottom: 10px; }
.ph-hint { color: #c5c8e4; font-size: 13px; margin: 10px 0; line-height: 1.6; }
.ph-note { color: #5a5f8a; font-size: 12px; line-height: 1.6; }
.ph-note code { background: #1f2340; padding: 2px 6px; border-radius: 3px; font-family: ui-monospace, Menlo, monospace; }
</style>
