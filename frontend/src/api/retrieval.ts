import { apiGet, apiPost } from './client'

export interface KnowledgeSyncResult {
  documents: number
  chunks: number
  provider: string
}

export interface RetrievalHit {
  rowid: number
  score: number
  rank: number
}

export interface RetrievalResult {
  status: 'OK' | 'EMPTY' | 'ERROR'
  mode: string
  hits: RetrievalHit[]
}

export function syncKnowledge(
  inputPath: string = 'data/knowledge',
  resetFirst = false,
  provider = 'ollama',
) {
  return apiPost<KnowledgeSyncResult>('/api/v1/knowledge/sync', {
    input_path: inputPath,
    reset_first: resetFirst,
    provider,
  })
}

export function searchRetrieval(query: string, mode: 'hybrid' | 'keyword' | 'vector' = 'hybrid', topK = 5) {
  return apiPost<RetrievalResult>('/api/v1/retrieval', { query, mode, top_k: topK })
}

export function retrievalStatus() {
  return apiGet<Record<string, unknown>>('/api/v1/retrieval/status')
}
