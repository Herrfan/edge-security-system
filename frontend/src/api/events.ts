import { apiGet, apiPost } from './client'
import type { SecurityEvent, IngestionSummary } from '@/types/api'

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

export function seedEvents(n = 3000) {
  return apiPost<{ imported_flows: number; events_created: number }>(
    '/api/v1/events/seed',
    { n },
  )
}

/**
 * Import flows from a CSV file uploaded by the client.
 * Multipart upload — not JSON. Uses fetch directly because apiPost sends JSON.
 */
export async function importFlows(file: File): Promise<IngestionSummary> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/v1/flows/import', {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({})))?.detail || res.statusText
    throw new Error(`flows/import failed: ${res.status} ${detail}`)
  }
  return res.json() as Promise<IngestionSummary>
}
