<script setup lang="ts">
/**
 * Event Trend Line Chart — SOC v2 版.
 * 改为多系列（按 severity 分 CRITICAL/HIGH/MEDIUM/LOW 4 条线），
 * SOC 深蓝配色。bucketing 事件 created_at → 小时桶。
 * 来自 client-side events — 标注"前端推导 · 时间范围=当前返回集".
 */
import { computed, onMounted, onBeforeUnmount, ref, watch, nextTick } from 'vue'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import * as echarts from 'echarts/core'
import type { SecurityEvent, Severity } from '@/types/api'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{ events: SecurityEvent[] }>()

const SERIES: { sev: Severity; name: string; color: string }[] = [
  { sev: 'CRITICAL', name: '严重', color: '#F04452' },
  { sev: 'HIGH',     name: '高危', color: '#F59E0B' },
  { sev: 'MEDIUM',   name: '中危', color: '#3478F6' },
  { sev: 'LOW',      name: '低危', color: '#10B981' },
]

/** "YYYY-MM-DD HH" bucket key */
function hourBucket(iso: string): string { return iso.slice(0, 13).replace('T', ' ') }

const trendData = computed(() => {
  if (!props.events.length) return { keys: [] as string[], series: [] as number[][] }
  const m = new Map<string, Record<string, number>>()
  for (const e of props.events) {
    if (!e.created_at) continue
    const k = hourBucket(e.created_at)
    if (!m.has(k)) m.set(k, {})
    const bucket = m.get(k)!
    bucket[e.severity] = (bucket[e.severity] || 0) + 1
  }
  const keys = [...m.keys()].sort()
  const series = SERIES.map(({ sev }) => keys.map((k) => m.get(k)?.[sev] || 0))
  return { keys, series }
})

const needsData = computed(() => props.events.length === 0)
const tooFewPoints = computed(() => trendData.value.keys.length < 2)

const chartRef = ref<HTMLElement | null>(null)
let inst: echarts.ECharts | null = null

function resize() { inst?.resize() }

function render() {
  if (!inst) return
  const { keys, series } = trendData.value
  inst.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0D1930', borderColor: '#1E3A5F',
      textStyle: { color: '#E8F0FF', fontSize: 12 },
      axisPointer: { lineStyle: { color: '#3478F6', type: 'dashed' } },
    },
    legend: {
      data: SERIES.map((s) => s.name),
      top: 0, right: 0,
      itemWidth: 12, itemHeight: 8, itemGap: 14,
      textStyle: { color: '#9CB0D0', fontSize: 11 },
    },
    grid: { top: 32, right: 12, bottom: 28, left: 36 },
    xAxis: {
      type: 'category', boundaryGap: false,
      data: keys.map((k) => k.slice(-2) + ':00'),
      axisLine: { lineStyle: { color: '#1E3A5F' } },
      axisLabel: { color: '#9CB0D0', fontSize: 10, interval: 0 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value', minInterval: 1,
      axisLine: { show: false }, axisTick: { show: false },
      splitLine: { lineStyle: { color: 'var(--bg-hover)', type: 'dashed' } },
      axisLabel: { color: '#9CB0D0', fontSize: 11 },
    },
    series: SERIES.map(({ name, color }, i) => ({
      name, type: 'line', stack: 'all',
      smooth: true, symbol: 'circle', symbolSize: 4,
      lineStyle: { color, width: 2 },
      itemStyle: { color },
      areaStyle: i === SERIES.length - 1
        ? { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(52, 120, 246, 0.25)' },
            { offset: 1, color: 'rgba(52, 120, 246, 0.01)' },
          ]) }
        : undefined,
      data: series[i],
    })),
  }, true)
}

onMounted(async () => {
  await nextTick()
  if (chartRef.value) {
    inst = echarts.init(chartRef.value)
    render()
    window.addEventListener('resize', resize)
  }
})
onBeforeUnmount(() => { window.removeEventListener('resize', resize); inst?.dispose() })
watch(() => props.events, () => render(), { deep: true })
</script>

<template>
  <div class="card">
    <div class="head">
      <span class="title">威胁趋势分析</span>
      <span class="badge">前端推导 · 时间范围={{ trendData.keys.length ? trendData.keys[0].slice(-5) : '—' }}…{{ trendData.keys.length ? trendData.keys[trendData.keys.length-1].slice(-5) : '—' }}</span>
    </div>
    <div v-if="needsData" class="empty">暂无事件数据</div>
    <div v-else-if="tooFewPoints" class="empty">事件采样时间点不足 2 小时，无法绘制趋势</div>
    <div v-else ref="chartRef" class="chart" />
  </div>
</template>

<style scoped>
.card {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-4);
  display: flex; flex-direction: column;
}
.head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-2); }
.title { font-size: var(--fs-xl); font-weight: 600; color: var(--text-hi); letter-spacing: 0.3px; }
.badge {
  font-size: var(--fs-xs); color: var(--text-sub);
  background: var(--bg-surface); border: 1px solid var(--border);
  padding: 2px 8px; border-radius: var(--radius-sm);
}
.chart { height: 240px; width: 100%; }
.empty { height: 240px; display: flex; align-items: center; justify-content: center; color: var(--text-sub); font-size: var(--fs-sm); text-align: center; padding: 0 var(--space-4); }
</style>
