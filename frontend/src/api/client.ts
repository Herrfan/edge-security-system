// Unified fetch wrapper. Handles:
//  - base URL (empty string in prod — same origin as FastAPI mounting dist/)
//  - timeout (default 15s)
//  - HTTP error extraction ({detail: "..."} bodies)
//  - JSON parsing
// Frontend MUST NOT swallow network errors silently — caller decides how to render.

const DEFAULT_TIMEOUT_MS = 15_000

export class ApiError extends Error {
  status: number
  detail?: string

  constructor(status: number, message: string, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(path, { ...init, signal: controller.signal })
    const contentType = res.headers.get('content-type') || ''
    const body = contentType.includes('application/json')
      ? await res.json().catch(() => null)
      : await res.text().catch(() => '')

    if (!res.ok) {
      const detail =
        (body && typeof body === 'object' && (body as { detail?: string }).detail) ||
        (typeof body === 'string' && body) ||
        res.statusText
      throw new ApiError(res.status, `HTTP ${res.status} ${res.statusText}`, detail)
    }

    return body as T
  } catch (err) {
    if (err instanceof ApiError) throw err
    if ((err as { name?: string })?.name === 'AbortError') {
      throw new ApiError(0, `timeout after ${timeoutMs}ms`)
    }
    throw new ApiError(0, (err as Error).message || 'network error')
  } finally {
    clearTimeout(timer)
  }
}

// ---------- Convenience methods ----------

export function apiGet<T>(path: string, query?: Record<string, string | number | boolean | null | undefined>) {
  const qs = query
    ? Object.entries(query)
        .filter(([, v]) => v !== undefined && v !== null && v !== '')
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join('&')
    : ''
  return request<T>(qs ? `${path}?${qs}` : path, { method: 'GET' })
}

export function apiPost<T>(path: string, json?: unknown) {
  return request<T>(path, {
    method: 'POST',
    headers: json ? { 'Content-Type': 'application/json' } : {},
    body: json ? JSON.stringify(json) : undefined,
  })
}

export function apiPut<T>(path: string, json?: unknown) {
  return request<T>(path, {
    method: 'PUT',
    headers: json ? { 'Content-Type': 'application/json' } : {},
    body: json ? JSON.stringify(json) : undefined,
  })
}

export function apiDelete<T>(path: string) {
  return request<T>(path, { method: 'DELETE' })
}
