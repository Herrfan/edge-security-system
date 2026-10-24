<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import DataSourceBadge from '@/components/common/DataSourceBadge.vue'
import { listEvents } from '@/api/events'
import { onMounted, ref, onUnmounted } from 'vue'

const route = useRoute()

interface NavItem {
  path: string
  label: string
  icon: string
  kind: 'live' | 'blocked'
  badge?: number  // 右侧角标数量（如事件未读数）
}

// 实时拉取事件计数用于 badge（参考图片有红色角标）
const eventCount = ref(0)
let pollTimer: number | null = null
async function refreshBadge() {
  try {
    const events = await listEvents({ limit: 1 })
    eventCount.value = events.length  // 注意：API 不返回 total，只能用已加载的数组长度
  } catch { /* 忽略 */ }
}

onMounted(() => { refreshBadge(); pollTimer = window.setInterval(refreshBadge, 30000) })
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })

const items = computed<NavItem[]>(() => [
  { path: '/dashboard',  label: '安全态势总览',  icon: '📊', kind: 'live' },
  { path: '/traffic',    label: '流量分析与检测',  icon: '🔍', kind: 'live' },
  { path: '/events',     label: '安全事件中心',    icon: '⚠️', kind: 'live', badge: eventCount.value > 0 ? undefined : undefined },
  { path: '/knowledge',  label: '威胁知识库',      icon: '📚', kind: 'live' },
  { path: '/policies',   label: '策略工作台',      icon: '🛡️', kind: 'live' },
  { path: '/evaluation', label: '评估中心',        icon: '📈', kind: 'blocked' },
  { path: '/audit',      label: '审计日志',        icon: '📝', kind: 'blocked' },
  { path: '/settings',   label: '系统设置',        icon: '⚙️', kind: 'live' },
])
</script>

<template>
  <aside class="sidebar">
    <!-- Section: 核心监控 -->
    <div class="nav-section">
      <div class="section-label">核心监控</div>
      <RouterLink
        v-for="it in items.slice(0, 3)" :key="it.path"
        :to="it.path"
        class="nav-item"
        :class="{ active: route.path === it.path, blocked: it.kind === 'blocked' }"
      >
        <span class="icon">{{ it.icon }}</span>
        <span class="label">{{ it.label }}</span>
        <DataSourceBadge :kind="it.kind" />
      </RouterLink>
    </div>

    <!-- Section: 防御与响应 -->
    <div class="nav-section">
      <div class="section-label">防御与响应</div>
      <RouterLink
        v-for="it in items.slice(3, 5)" :key="it.path"
        :to="it.path"
        class="nav-item"
        :class="{ active: route.path === it.path, blocked: it.kind === 'blocked' }"
      >
        <span class="icon">{{ it.icon }}</span>
        <span class="label">{{ it.label }}</span>
        <DataSourceBadge :kind="it.kind" />
      </RouterLink>
    </div>

    <!-- Section: 管理 -->
    <div class="nav-section">
      <div class="section-label">管理</div>
      <RouterLink
        v-for="it in items.slice(5)" :key="it.path"
        :to="it.path"
        class="nav-item"
        :class="{ active: route.path === it.path, blocked: it.kind === 'blocked' }"
      >
        <span class="icon">{{ it.icon }}</span>
        <span class="label">{{ it.label }}</span>
        <DataSourceBadge :kind="it.kind" />
      </RouterLink>
    </div>

    <!-- Bottom: safety boundary + edge node status (SOC footer pattern) -->
    <div class="sidebar-footer">
      <div class="safety-card">
        <div class="safety-head">
          <span class="s-icon">🛡️</span>
          <span class="s-title">安全边界</span>
        </div>
        <div class="safety-body">
          默认 DRY_RUN · allow_real_execution = false
        </div>
      </div>
      <div class="edge-node">
        <span class="node-icon">🖥️</span>
        <span class="node-label">边缘节点状态</span>
        <span class="node-count">在线 1/2</span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-w);
  height: 100%;
  background: var(--bg-nav);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  padding: var(--space-3) 0;
  overflow-y: auto;
}

/* Section labels */
.nav-section { margin-bottom: var(--space-1); }
.section-label {
  padding: var(--space-2) var(--space-4) var(--space-1);
  font-size: 10px; color: var(--text-dim);
  text-transform: uppercase; letter-spacing: 1px;
  font-weight: 600;
}

/* Nav items */
.nav-item {
  display: flex; align-items: center; gap: var(--space-2);
  padding: 10px var(--space-4);
  color: var(--text-sub);
  text-decoration: none;
  font-size: var(--fs-sm);
  border-left: 3px solid transparent;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
  margin: 1px 6px;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  position: relative;
}
.nav-item:hover {
  background: var(--bg-surface);
  color: var(--text-hi);
}
.nav-item.active {
  background: rgba(52, 120, 246, 0.12);
  color: var(--text-hi);
  border-left-color: var(--accent);
  font-weight: 600;
  box-shadow: -3px 0 8px rgba(52, 120, 246, 0.2);
}
.nav-item.blocked { opacity: 0.55; }
.nav-item.blocked:hover { opacity: 0.85; }

.icon { font-size: 15px; width: 20px; text-align: center; }
.label { flex: 1; }

/* Footer */
.sidebar-footer {
  margin-top: auto;
  padding: var(--space-3) var(--space-3) 0;
  display: flex; flex-direction: column; gap: var(--space-2);
}
.safety-card {
  background: var(--bg-surface);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
}
.safety-head { display: flex; align-items: center; gap: 6px; margin-bottom: 2px; }
.s-icon { font-size: 12px; }
.s-title { font-size: var(--fs-xs); color: var(--warn); font-weight: 600; }
.safety-body { font-size: 10px; color: var(--text-dim); line-height: 1.4; }

.edge-node {
  display: flex; align-items: center; gap: 6px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  font-size: var(--fs-xs);
}
.node-icon { font-size: 14px; }
.node-label { color: var(--text-sub); flex: 1; }
.node-count { color: var(--cyan); font-weight: 600; font-family: var(--font-mono); }

@media (max-width: 768px) {
  .sidebar { width: 64px; padding: var(--space-2) 0; }
  .section-label, .label, .edge-node .node-label, .edge-node .node-count { display: none; }
  .nav-item { justify-content: center; padding: 10px; }
  .icon { width: auto; }
  .safety-card, .edge-node { display: none; }
}
</style>
