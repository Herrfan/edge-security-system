/**
 * Traffic / detection API layer.
 *
 * Wraps:
 *   POST /api/v1/flows/import  — multipart file upload → IngestionSummary
 *
 * Does NOT expose /detection/predict (requires server-side absolute path)
 * or /detection/train (offline sklearn fitting only). flows/import already
 * runs detection internally and returns imported_flows + events_created +
 * detector_used + detector_version — that is all TrafficAnalysisView needs.
 */
import { apiPost } from './client'
import type { IngestionSummary } from '@/types/api'

/**
 * Import flows from a CSV file uploaded by the client (multipart).
 * Uses fetch directly because apiPost sends JSON.
 */
export async function importFlows(file: File, datasetId?: string): Promise<IngestionSummary> {
  const form = new FormData()
  form.append('file', file)
  if (datasetId) form.append('dataset_id', datasetId)

  const res = await fetch('/api/v1/flows/import', { method: 'POST', body: form })
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({})))?.detail || res.statusText
    throw new Error(`flows/import failed: ${res.status} ${detail}`)
  }
  return res.json() as Promise<IngestionSummary>
}

export interface PredictResult {
  detector_id: string
  model_id: string
  model_version: string
  n_flows: number
  predictions: {
    flow_id: string
    predicted_label: string
    score: number
    latency_ms: number
  }[]
}

/**
 * Run a named detector over a server-side file path.
 * NOTE: Not exposed in TrafficAnalysisView — requires server-side path, which
 * the browser cannot provide. Kept here for completeness / dev tools.
 */
export function predictFlows(inputFile: string, detectorId = 'rule-demo', maxRecords?: number) {
  const body: { detector_id: string; input_file: string; max_records?: number | null } = {
    detector_id: detectorId,
    input_file: inputFile,
  }
  if (maxRecords != null) body.max_records = maxRecords
  return apiPost<PredictResult>('/api/v1/detection/predict', body)
}
