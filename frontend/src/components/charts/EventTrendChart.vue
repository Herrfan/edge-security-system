<script setup lang="ts">
/**
 * Event Trend Line Chart — Phase F3 Dashboard.
 *
 * Buckets events by created_at hour, plotted as event counts over time.
 * Derived client-side from listEvents({limit}) results — NO backend trend API.
 * Explicitly labeled "前端推导 · 时间范围=当前返回的事件集".
 */
import { computed, onMounted, onBeforeUnmount, ref, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { SecurityEvent } from '@/types/api'

const props = defineProps<{ events: SecurityEvent[] }>()

/** "YYYY-MM-DD HH" bucket key (UTC) */
function hourBucket(iso: string): string {
  // ISO 8601 with Z: "2026-10-24T00:04:54.123456Z"
  return iso.slice(0, 13).replace('T', ' ')
}

const buckets = computed(() => {
  if (!props.events.length) return { keys: [] as string[], values: [] as number[] }
  const m = new Map<string, number>()
  for (const e of props.events) {
    if (!e.created_at) continue
    const k = hourBucket(e.created_at)
    m.set(k, (m.get(k) || 0) + 1)
  }
  const keys = [...m.keys()].sort()
  const values = keys.map((k) => m.get(k) || 0)
  return { keys, values }
})

const needsData = computed(() => props.events.length === 0)
const tooFew = computed(() => buckets.value.keys.length < 2)

const chartRef = ref<HTMLElement | null>(null)
let inst: echarts.ECharts | null = null

function render() {
  if (!inst) return
  const { keys, values } = buckets.value
  const option = {
    tooltip: { trigger: 'axis', backgroundColor: '#1f2340', borderColor: '#2a2e4d', textStyle: { color: '#e4e7f7', fontSize: 12 } },
    grid: { top: 10, right: 16, bottom: 30, left: 40 },
    xAxis: {
      type: 'category',
      data: keys.map((k) => k.slice(-2) + ':00'),  // "23:00"
      axisLine: { lineStyle: { color: '#2a2e4d' } },
      axisLabel: { color: '#8a8fb8', fontSize: 10, interval: 0 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#1f2340' } },
      axisLabel: { color: '#8a8fb8', fontSize: 11 },
    },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { color: '#4f8cff', width: 2 },
      itemStyle: { color: '#4f8cff' },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(79, 140, 255, 0.45)' },
            { offset: 1, color: 'rgba(79, 140, 255, 0.02)' },
          ],
        },
      },
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
      <span class="chart-title">事件时间趋势 (按小时)</span>
      <span class="derived-tag">前端推导 · 时间范围={{ events.length ? hourBucket(events[events.length-1].created_at || '') + '…' + hourBucket(events[0].created_at || '') : '—' }}</span>
    </div>
    <div v-if="needsData" class="empty">暂无事件数据</div>
    <div v-else-if="tooFew" class="empty">事件时间点不足 2 小时 (仅 {{ buckets.keys.length }} 个)，无法绘制趋势</div>
    <div v-else ref="chartRef" style="height: 260px; width: 100%" />
  </div>
</template>

<style scoped>
.chart-wrap { background: #11132a; border-radius: 10px; border: 1px solid #2a2e4d; padding: 12px 14px; }
.chart-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.chart-title { font-size: 13px; font-weight: 600; color: #e4e7f7; letter-spacing: 0.3px; }
.derived-tag { font-size: 10px; color: #8a8fb8; background: #1f2340; padding: 2px 6px; border-radius: 4px; border: 1px solid #2a2e4d; max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty { height: 260px; display: flex; align-items: center; justify-content: center; color: #8a8fb8; font-size: 13px; text-align: center; padding: 0 16px; }
</style>
