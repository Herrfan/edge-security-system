<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, TitleComponent, LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([LineChart, GridComponent, TooltipComponent, TitleComponent, LegendComponent, CanvasRenderer])

const props = withDefaults(
  defineProps<{
    title?: string
    labels: string[]
    values: number[]
    height?: string
    color?: string
  }>(),
  { title: '', height: '260px', color: '#29c38b' },
)

const option = computed(() => ({
  title: props.title ? { text: props.title, textStyle: { color: '#c5c8e4', fontSize: 13 }, left: 6 } : undefined,
  tooltip: { trigger: 'axis', backgroundColor: '#1f2340', borderColor: '#2a2e4d', textStyle: { color: '#e4e7f7', fontSize: 12 } },
  grid: { top: props.title ? 40 : 12, right: 16, bottom: 24, left: 40 },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: props.labels,
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
    type: 'line',
    data: props.values,
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    itemStyle: { color: props.color },
    lineStyle: { color: props.color, width: 2 },
    areaStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: props.color + '40' },
          { offset: 1, color: props.color + '05' },
        ],
      },
    },
  }],
}))
</script>

<template>
  <div class="chart-wrap" :style="{ height }">
    <VChart :option="option" autoresize />
  </div>
</template>

<style scoped>
.chart-wrap { background: #171a2e; border: 1px solid #2a2e4d; border-radius: 8px; padding: 4px; }
</style>
