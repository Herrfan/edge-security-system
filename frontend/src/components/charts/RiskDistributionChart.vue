<script setup lang="ts">
/**
 * Risk Distribution Bar Chart — Phase F3 Dashboard.
 *
 * Derived client-side from listEvents({limit}) results, NOT from any backend
 * risk-distribution endpoint. Explicitly labeled "前端推导" so users never
 * mistake it for a backend-aggregated statistic.
 */
import { computed, onMounted, onBeforeUnmount, ref, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { SecurityEvent, Severity } from '@/types/api'

const props = defineProps<{ events: SecurityEvent[] }>()

const ORDER: Severity[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
const COLORS: Record<Severity, string> = {
  CRITICAL: '#ff5a5f', HIGH: '#ffb454', MEDIUM: '#4f8cff', LOW: '#29c38b', INFO: '#8a8fb8',
}

const counts = computed(() => {
  const m: Record<string, number> = {}
  for (const e of props.events) m[e.severity] = (m[e.severity] || 0) + 1
  return ORDER.map((sev) => ({ severity: sev, count: m[sev] || 0 }))
})

const isEmpty = computed(() => props.events.length === 0)

const chartRef = ref<HTMLElement | null>(null)
let inst: echarts.ECharts | null = null

function render() {
  if (!inst) return
  const option = {
    tooltip: { trigger: 'axis', backgroundColor: '#1f2340', borderColor: '#2a2e4d', textStyle: { color: '#e4e7f7', fontSize: 12 } },
    grid: { top: 10, right: 16, bottom: 24, left: 40 },
    xAxis: {
      type: 'category',
      data: counts.value.map((c) => c.severity),
      axisLine: { lineStyle: { color: '#2a2e4d' } },
      axisLabel: { color: '#8a8fb8', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#1f2340' } },
      axisLabel: { color: '#8a8fb8', fontSize: 11 },
    },
    series: [{
      type: 'bar',
      barMaxWidth: 48,
      data: counts.value.map((c) => ({
        value: c.count,
        itemStyle: { color: COLORS[c.severity], borderRadius: [3, 3, 0, 0] },
      })),
    }],
  }
  inst.setOption(option, true)
}

onMounted(async () => {
  await nextTick()
  if (chartRef.value) {
    inst = echarts.init(chartRef.value)
    render()
  }
})
onBeforeUnmount(() => { inst?.dispose() })
watch(() => props.events, () => render(), { deep: true })
</script>

<template>
  <div class="chart-wrap">
    <div class="chart-head">
      <span class="chart-title">风险分布 (按 severity)</span>
      <span class="derived-tag">前端推导 · 样本 {{ events.length }}</span>
    </div>
    <div v-if="isEmpty" class="empty">暂无事件数据</div>
    <div v-else ref="chartRef" style="height: 260px; width: 100%" />
  </div>
</template>

<style scoped>
.chart-wrap { background: #11132a; border-radius: 10px; border: 1px solid #2a2e4d; padding: 12px 14px; }
.chart-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.chart-title { font-size: 13px; font-weight: 600; color: #e4e7f7; letter-spacing: 0.3px; }
.derived-tag { font-size: 10px; color: #8a8fb8; background: #1f2340; padding: 2px 6px; border-radius: 4px; border: 1px solid #2a2e4d; }
.empty { height: 260px; display: flex; align-items: center; justify-content: center; color: #8a8fb8; font-size: 13px; }
</style>
