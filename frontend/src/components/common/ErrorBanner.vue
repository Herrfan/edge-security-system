<script setup lang="ts">
defineProps<{ message: string; detail?: string }>()
</script>

<template>
  <div class="error-banner" role="alert">
    <div class="error-head">⚠ 请求失败</div>
    <div class="error-msg">{{ message }}</div>
    <div v-if="detail && detail !== message" class="error-detail">{{ detail }}</div>
  </div>
</template>

<style scoped>
.error-banner {
  background: rgba(255, 90, 95, 0.1);
  border: 1px solid rgba(255, 90, 95, 0.35);
  border-radius: 8px;
  padding: 12px 14px;
  color: #ff8a8f;
  font-size: 13px;
}
.error-head { font-weight: 600; margin-bottom: 4px; }
.error-detail { font-size: 12px; color: #c5c8e4; font-family: ui-monospace, Menlo, monospace; margin-top: 4px; word-break: break-all; }
</style>
