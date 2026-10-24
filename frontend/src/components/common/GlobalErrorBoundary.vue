<script setup lang="ts">
/**
 * GlobalErrorBoundary — Phase F6.
 *
 * Polls GET /health every 30s. If the backend is unreachable, shows a
 * fixed top banner explaining the problem and a manual "重试" button.
 * When the backend comes back, banner auto-hides.
 *
 * This is the unified "后端挂了" error surface — previously each page
 * handled its own network error via ErrorBanner. Now the top-level
 * banner catches it for the whole SPA.
 */
import { onMounted, onBeforeUnmount, ref } from 'vue'

const status = ref<'checking' | 'ok' | 'down'>('checking')
const lastChecked = ref<string>('')
let timer: number | null = null

async function check() {
  try {
    const resp = await fetch('/health', { method: 'GET', cache: 'no-store' })
    if (resp.ok) {
      status.value = 'ok'
      lastChecked.value = new Date().toLocaleTimeString()
    } else {
      status.value = 'down'
      lastChecked.value = new Date().toLocaleTimeString()
    }
  } catch {
    status.value = 'down'
    lastChecked.value = new Date().toLocaleTimeString()
  }
}

function retry() { check() }

onMounted(() => { check(); timer = window.setInterval(check, 30000) })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <Transition name="slide">
    <div v-if="status === 'down'" class="banner" role="alert" aria-live="assertive">
      <div class="bb-icon">⚠️</div>
      <div class="bb-body">
        <div class="bb-title">后端服务不可达</div>
        <div class="bb-desc">
          无法连接到 <code>/health</code> 端点。所有数据请求都会失败。
          请确认 FastAPI 服务正在运行（<code>python -m uvicorn app.main:app</code>）。
        </div>
        <div class="bb-meta">上次检查：{{ lastChecked }} · 每 30 秒自动重试</div>
      </div>
      <button class="bb-retry" @click="retry">🔄 立即重试</button>
    </div>
  </Transition>
</template>

<style scoped>
.banner {
  position: fixed; top: 0; left: 0; right: 0; z-index: 2000;
  background: rgba(240, 68, 82, 0.95);
  backdrop-filter: blur(8px);
  border-bottom: 2px solid var(--err);
  color: #fff;
  padding: 10px 18px;
  display: flex; gap: 14px; align-items: center;
  box-shadow: 0 4px 20px rgba(240, 68, 82, 0.4);
}
.bb-icon { font-size: 26px; }
.bb-body { flex: 1; min-width: 0; }
.bb-title { font-weight: 700; font-size: 14px; margin-bottom: 3px; }
.bb-desc { font-size: 12px; opacity: 0.9; line-height: 1.6; }
.bb-desc code { background: rgba(0, 0, 0, 0.25); padding: 1px 5px; border-radius: 3px; font-size: 11px; }
.bb-meta { font-size: 10px; opacity: 0.7; margin-top: 3px; }
.bb-retry {
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.5);
  color: #fff;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.bb-retry:hover { background: rgba(255, 255, 255, 0.35); }

.slide-enter-active, .slide-leave-active { transition: transform 0.2s ease, opacity 0.2s ease; }
.slide-enter-from { transform: translateY(-100%); opacity: 0; }
.slide-leave-to { transform: translateY(-100%); opacity: 0; }
</style>
