<script setup lang="ts">
/**
 * Risk Distribution — SOC v2 版.
 * 改为环形图（参考图片风格），SOC 深蓝配色。
 * 来自 client-side events severity 统计 — 标注"前端推导"。
 */
import { computed, onMounted, onBeforeUnmount, ref, watch, nextTick } from 'vue'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import * as echarts from 'echarts/core'
import type { SecurityEvent, Severity } from '@/types/api'

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{ events: SecurityEvent[] }>()

const ORDER: Severity[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
const COLORS: Record<Severity, string> = {
  CRITICAL: '#F04452', HIGH: '#F59E0B', MEDIUM: '#3478F6', LOW: '#10B981', INFO: '#64748B',
}
const LABELS: Record<Severity, string> = {
  CRITICAL: '严重', HIGH: '高危', MEDIUM: '中危', LOW: '低危', INFO: '信息',
}

const slices = computed(() => {
  const m: Record<string, number> = {}
  for (const e of props.events) m[e.severity] = (m[e.severity] || 0) + 1
  return ORDER
    .filter((sev) => (m[sev] || 0) > 0)
    .map((sev) => ({ name: LABELS[sev], value: m[sev], itemStyle: { color: COLORS[sev] } }))
})

const total = computed(() => props.events.length)
const isEmpty = computed(() => total.value === 0)

const chartRef = ref<HTMLElement | null>(null)
let inst: echarts.ECharts | null = null

function resize() { inst?.resize() }

function render() {
  if (!inst) return
  inst.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: '#0D1930', borderColor: '#1E3A5F',
      textStyle: { color: '#E8F0FF', fontSize: 12 },
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      orient: 'vertical', right: 8, top: 'center',
      itemWidth: 10, itemHeight: 10, itemGap: 10,
      textStyle: { color: '#9CB0D0', fontSize: 11 },
    },
    series: [{
      type: 'pie',
      radius: ['52%', '72%'],
      center: ['38%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 4, borderColor: '#0D1930', borderWidth: 2 },
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold', color: '#E8F0FF' },
      },
      data: slices.value,
    }],
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
      <span class="title">风险等级分布</span>
      <span class="badge">前端推导 · 样本 {{ total }}</span>
    </div>
    <div v-if="isEmpty" class="empty">暂无事件数据</div>
    <template v-else>
      <div class="center-label">
        <div class="total">{{ total }}</div>
        <div class="sub">总事件</div>
      </div>
      <div ref="chartRef" class="chart" />
    </template>
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
.chart { height: 220px; width: 100%; position: relative; }
.center-label {
  position: absolute; top: 45%; left: 34%;
  transform: translate(-50%, -50%);
  text-align: center; z-index: 1;
  pointer-events: none;
}
.center-label .total { font-size: 24px; font-weight: 700; color: var(--text-hi); font-family: var(--font-mono); }
.center-label .sub { font-size: var(--fs-xs); color: var(--text-dim); }
.empty { height: 220px; display: flex; align-items: center; justify-content: center; color: var(--text-sub); font-size: var(--fs-sm); }
</style>
