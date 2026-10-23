import { apiGet } from './client'
import type { HealthInfo, MetricsOverview } from '@/types/api'

export function health() {
  return apiGet<HealthInfo>('/health')
}

export function metricsOverview() {
  return apiGet<MetricsOverview>('/api/v1/metrics/overview')
}

export function metricsExport(format: 'json' | 'csv' = 'json') {
  return apiGet<string>(`/api/v1/metrics/export`, { format })
}
