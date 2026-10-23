<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'
import DataSourceBadge from '@/components/common/DataSourceBadge.vue'

const route = useRoute()

interface NavItem {
  path: string
  label: string
  icon: string
  kind: 'live' | 'blocked'
}

const items: NavItem[] = [
  { path: '/dashboard',  label: '安全态势总览',  icon: '📊', kind: 'live' },
  { path: '/traffic',    label: '流量分析',      icon: '🔍', kind: 'blocked' },
  { path: '/events',     label: '安全事件',      icon: '⚠️', kind: 'live' },
  { path: '/knowledge',  label: '威胁知识库',    icon: '📚', kind: 'live' },
  { path: '/policies',   label: '策略工作台',    icon: '🛡️', kind: 'live' },
  { path: '/evaluation', label: '评估中心',      icon: '📈', kind: 'blocked' },
  { path: '/audit',      label: '审计日志',      icon: '📝', kind: 'blocked' },
  { path: '/settings',   label: '系统设置',      icon: '⚙️', kind: 'live' },
]
</script>

<template>
  <aside class="sidebar">
    <div v-for="it in items" :key="it.path">
      <RouterLink
        :to="it.path"
        class="nav-item"
        :class="{ active: route.path === it.path, blocked: it.kind === 'blocked' }"
      >
        <span class="icon">{{ it.icon }}</span>
        <span class="label">{{ it.label }}</span>
        <DataSourceBadge :kind="it.kind" />
      </RouterLink>
    </div>

    <div class="safety-note">
      <div class="note-title">⚠ 安全边界</div>
      <div class="note-body">
        默认 DRY_RUN · allow_real_execution = false · 不执行真实防火墙变更
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 220px;
  background: #141729;
  border-right: 1px solid #2a2e4d;
  padding: 16px 12px;
  display: flex; flex-direction: column; gap: 2px;
}
.nav-item {
  display: flex; align-items: center; gap: 8px;
  padding: 9px 12px; border-radius: 6px;
  color: #8a8fb8; text-decoration: none; font-size: 13px;
  transition: background 0.15s, color 0.15s;
}
.nav-item:hover { background: #1f2340; color: #e4e7f7; }
.nav-item.active { background: rgba(79, 140, 255, 0.12); color: #4f8cff; }
.nav-item.blocked { opacity: 0.7; }
.icon { font-size: 14px; }
.label { flex: 1; }
.safety-note {
  margin-top: auto;
  padding: 10px 12px;
  background: rgba(255, 180, 84, 0.08);
  border: 1px solid rgba(255, 180, 84, 0.25);
  border-radius: 6px;
  font-size: 11px; color: #ffb454; line-height: 1.5;
}
.note-title { font-weight: 600; margin-bottom: 4px; }
</style>
