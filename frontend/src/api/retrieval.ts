import { apiGet, apiPost } from './client'

export interface KnowledgeSyncResult {
  documents: number
  chunks: number
  provider: string
}

export interface RetrievalHit {
  chunk_id: string
  document_id: string
  rowid: number
  distance: number
  score: number
}

export interface RetrievalResult {
  status: 'OK' | 'DEGRADED' | 'EMPTY' | 'ERROR'
  hits: RetrievalHit[]
  count: number
  provider: string
  is_mock: boolean
  mode: string
}

/** Sync knowledge from an absolute server-side file path. */
export function syncKnowledge(inputPath: string, resetFirst = true) {
  return apiPost<KnowledgeSyncResult>('/api/v1/knowledge/sync', {
    input_path: inputPath,
    reset_first: resetFirst,
  })
}

/** Convenience: sync the repo's default knowledge JSONL. */
export function syncDefaultKnowledge() {
  return apiPost<KnowledgeSyncResult>('/api/v1/knowledge/sync-default', {})
}

export function searchRetrieval(
  query: string,
  mode: 'hybrid' | 'keyword' | 'vector' | null = null,
  topK = 10,
) {
  const body: Record<string, unknown> = { query, top_k: topK }
  if (mode) body.mode = mode
  return apiPost<RetrievalResult>('/api/v1/retrieval', body)
}

export function retrievalStatus() {
  return apiGet<Record<string, unknown>>('/api/v1/retrieval/status')
}
