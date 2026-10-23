// Simple ISO → "2026-10-23 14:05:21" formatter.
// Intentionally zero-dep (no dayjs).
export function formatDateTime(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(
    d.getMinutes(),
  )}:${pad(d.getSeconds())}`
}

export function formatNumber(n: unknown, decimals = 3): string {
  if (n === null || n === undefined) return '—'
  const num = Number(n)
  if (isNaN(num)) return String(n)
  return num % 1 === 0 ? String(num) : num.toFixed(decimals)
}

// Backend enum → human-readable label. DO NOT just echo backend values to the user —
// this lets us keep UX labels stable if backend enum values change.
export const SEVERITY_LABEL: Record<string, string> = {
  CRITICAL: '严重',
  HIGH: '高危',
  MEDIUM: '中危',
  LOW: '低危',
  INFO: '信息',
}

export const STATUS_LABEL: Record<string, string> = {
  NEEDS_APPROVAL: '待审批',
  APPROVED: '已批准',
  REJECTED: '已驳回',
  NEEDS_VALIDATION: '待校验',
  EXECUTED: '已执行',
  EXPIRED: '已过期',
  DRAFT: '草稿',
}
