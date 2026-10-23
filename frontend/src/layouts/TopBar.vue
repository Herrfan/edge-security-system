<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { health as fetchHealth } from '@/api/metrics'
import type { HealthInfo } from '@/types/api'

const info = ref<HealthInfo | null>(null)
const bad = ref(false)
const errMsg = ref('')

async function poll() {
  try {
    const r = await fetchHealth()
    info.value = r
    bad.value = r.status !== 'ok'
  } catch (e) {
    bad.value = true
    errMsg.value = (e as Error).message
  }
}

onMounted(() => {
  poll()
  setInterval(poll, 20000)
})
</script>

<template>
  <header class="topbar">
    <div class="brand">
      <span class="dot" />
      <h1>Edge Security</h1>
      <span class="sub">安全态势感知 · 自适应防御</span>
    </div>
    <div class="top-right">
      <span v-if="info" class="server-tag" :class="{ bad }">
        {{ bad ? '● 离线' : '● connected' }}
      </span>
      <span v-if="info" class="ver">
        {{ info.service }} · v{{ info.version }} · Python {{ info.python }}
      </span>
      <span v-if="errMsg" class="err-tag">{{ errMsg }}</span>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 24px;
  background: linear-gradient(90deg, #141729, #1c2040);
  border-bottom: 1px solid #2a2e4d;
}
.brand { display: flex; align-items: baseline; gap: 10px; }
.brand h1 { font-size: 17px; margin: 0; letter-spacing: 0.5px; }
.brand .sub { font-size: 12px; color: #8a8fb8; }
.brand .dot {
  width: 10px; height: 10px; border-radius: 50%; background: #4f8cff;
  box-shadow: 0 0 10px #4f8cff; margin-right: 4px;
}
.top-right { display: flex; gap: 14px; align-items: center; font-size: 12px; }
.server-tag { padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.server-tag:not(.bad) { background: rgba(41, 195, 139, 0.15); color: #29c38b; }
.server-tag.bad { background: rgba(255, 90, 95, 0.15); color: #ff5a5f; }
.ver { color: #8a8fb8; font-family: ui-monospace, Menlo, monospace; }
.err-tag { color: #ff8a8f; }
</style>
