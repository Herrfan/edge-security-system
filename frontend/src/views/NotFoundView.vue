<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="nf-wrap">
    <div class="nf-code">404</div>
    <div class="nf-title">页面未找到</div>
    <div class="nf-hint">您访问的路由不存在，或尚未在 Phase F1-F7 中实现。</div>
    <RouterLink to="/dashboard" class="nf-link">← 返回安全态势总览</RouterLink>
  </div>
</template>

<style scoped>
.nf-wrap {
  min-height: 60vh;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: var(--text-sub); text-align: center;
}
.nf-code { font-size: 96px; font-weight: 700; color: var(--accent); font-family: var(--font-mono); line-height: 1; text-shadow: 0 0 30px rgba(52, 120, 246, 0.3); }
.nf-title { font-size: 20px; font-weight: 600; color: var(--text-mid); margin: 12px 0 6px; }
.nf-hint { font-size: 13px; margin-bottom: 20px; }
.nf-link {
  color: var(--accent); text-decoration: none; font-size: 13px;
  padding: 8px 18px; border: 1px solid var(--border); border-radius: 6px;
  transition: background 0.15s;
}
.nf-link:hover { background: var(--bg-surface); }
</style>
