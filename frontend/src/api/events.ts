import { apiGet, apiPost } from './client'
import type { SecurityEvent } from '@/types/api'

export interface ListEventsQuery {
  limit?: number
  severity?: string
  status?: string
  predicted_label?: string
}

export function listEvents(q?: ListEventsQuery) {
  return apiGet<SecurityEvent[]>('/api/v1/events', q as Record<string, string | number>)
}

export function getEvent(eventId: string) {
  return apiGet<SecurityEvent>(`/api/v1/events/${eventId}`)
}

export function seedEvents(maxRecords?: number, assetId = 'default-asset') {
  // Uses the convenience POST /api/v1/events/seed-default helper which
  // defaults to repo's data/samples/flows_sample.csv + rule-demo detector.
  return apiPost<{
    seeded_events: number
    detector_id: string
    input_file?: string
    max_records?: number | null
  }>('/api/v1/events/seed-default', {
    max_records: maxRecords ?? null,
    asset_id: assetId,
  })
}
