<script setup lang="ts">
import { onMounted, ref, onUnmounted } from 'vue'
import { health as fetchHealth } from '@/api/metrics'
import type { HealthInfo } from '@/types/api'

const info = ref<HealthInfo | null>(null)
const bad = ref(false)
const errMsg = ref('')
const now = ref(new Date())

let timer: number | null = null
let clockTimer: number | null = null

async function poll() {
  try {
    const r = await fetchHealth()
    info.value = r
    bad.value = r.status !== 'ok'
    errMsg.value = ''
  } catch (e) {
    bad.value = true
    errMsg.value = (e as Error).message
  }
}

onMounted(() => {
  poll()
  timer = window.setInterval(poll, 20000)
  clockTimer = window.setInterval(() => { now.value = new Date() }, 1000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (clockTimer) clearInterval(clockTimer)
})

function fmtTime(d: Date) {
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
</script>

<template>
  <header class="topbar">
    <!-- Left: brand + nav breadcrumb -->
    <div class="brand">
      <span class="brand-icon">🛡️</span>
      <div class="brand-text">
        <h1>边缘网络安全态势感知与自适应防御系统</h1>
        <span class="sub">SOC · Edge Security</span>
      </div>
    </div>

    <!-- Right: health + time + user -->
    <div class="top-right">
      <span class="health" :class="{ bad }" v-if="info || errMsg">
        <span class="dot" />
        <span class="label">{{ bad ? '系统异常' : '系统运行正常' }}</span>
      </span>
      <span class="ver" v-if="info && !bad">
        v{{ info.version }}
      </span>
      <span class="clock">{{ fmtTime(now) }}</span>
      <div class="user">
        <span class="avatar">👤</span>
        <span class="uname">admin</span>
        <span class="caret">▾</span>
      </div>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  display: flex; justify-content: space-between; align-items: center;
  height: var(--topbar-h);
  padding: 0 var(--space-6);
  background: var(--bg-nav);
  border-bottom: 1px solid var(--border);
}
.brand { display: flex; align-items: center; gap: var(--space-3); }
.brand-icon {
  font-size: 22px;
  width: 38px; height: 38px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(52, 120, 246, 0.15);
  border: 1px solid rgba(52, 120, 246, 0.35);
  border-radius: var(--radius-md);
}
.brand-text { display: flex; flex-direction: column; line-height: 1.2; }
.brand h1 { font-size: 15px; font-weight: 700; margin: 0; letter-spacing: 0.3px; color: var(--text-hi); }
.brand .sub { font-size: var(--fs-xs); color: var(--text-sub); }

.top-right { display: flex; gap: var(--space-4); align-items: center; font-size: var(--fs-sm); }

.health {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px; border-radius: 20px;
  background: var(--ok-soft); color: var(--ok);
  font-size: var(--fs-xs); font-weight: 600;
}
.health .dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--ok);
  box-shadow: 0 0 6px var(--ok);
}
.health.bad { background: var(--err-soft); color: var(--err); }
.health.bad .dot { background: var(--err); box-shadow: 0 0 6px var(--err); }

.ver { color: var(--text-sub); font-family: var(--font-mono); }
.clock {
  font-family: var(--font-mono); font-size: var(--fs-sm);
  color: var(--text-mid);
  background: var(--bg-surface);
  padding: 4px 10px; border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

.user {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
}
.user:hover { border-color: var(--accent); }
.avatar { font-size: 16px; }
.uname { font-size: var(--fs-sm); color: var(--text-mid); font-weight: 500; }
.caret { font-size: 10px; color: var(--text-dim); }

@media (max-width: 768px) {
  .brand h1 { font-size: 13px; }
  .clock { display: none; }
  .ver { display: none; }
}
</style>
