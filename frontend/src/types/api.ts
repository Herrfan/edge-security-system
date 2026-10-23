// ---- Common domain types — mirror backend Pydantic models ----
// Fields MUST match backend; if backend schema changes update this file
// together with docs/frontend-api-mapping.md.

export type Severity = 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export type ActionType =
  | 'BLOCK_IP'
  | 'BLOCK_PORT'
  | 'RATE_LIMIT'
  | 'ALERT_ONLY'
  | 'NO_ACTION'

export type PolicyStatus =
  | 'DRAFT'
  | 'NEEDS_VALIDATION'
  | 'NEEDS_APPROVAL'
  | 'APPROVED'
  | 'REJECTED'
  | 'EXPIRED'
  | 'READY'
  | 'EXECUTING'
  | 'EXECUTED'

export type ExecutionMode = 'DRY_RUN' | 'REAL'
export type ExecutionStatus =
  | 'UNKNOWN'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'ROLLED_BACK'

export interface SecurityEvent {
  event_id: string
  created_at: string
  asset_id: string
  flow_id?: string | null
  flow_summary?: string | null
  predicted_label: string
  score: number
  severity: Severity
  model_id?: string | null
  model_version?: string | null
  evidence_summary?: string | null
  status?: string
  trace_id?: string | null
}

export interface Evidence {
  document_id: string
  chunk_id: string
  source: string
  source_ref?: string
  title?: string
  content?: string
  retrieval_method?: string
  retrieval_score?: number
}

export interface PolicyProposal {
  policy_id: string
  created_at?: string
  event_id?: string
  action_type: ActionType
  parameters?: Record<string, unknown>
  risk_level?: Severity
  rationale?: string
  evidence_ids?: string[]
  ttl_seconds?: number
  status?: PolicyStatus
  requires_approval?: boolean
  expires_at?: string | null
}

export interface ValidationResult {
  policy_id: string
  is_valid: boolean
  reasons: string[]
}

export interface ExecutionRecord {
  execution_id: string
  policy_id: string
  mode: ExecutionMode
  status: ExecutionStatus
  started_at: string
  finished_at?: string | null
  stdout_summary?: string | null
  stderr_summary?: string | null
  rollback_status?: string | null
  trace_id?: string | null
  duration_ms?: number | null
}

export interface HealthInfo {
  status: string
  service: string
  version: string
  python?: string
  pid?: number
}

export interface IngestionSummary {
  source_path: string
  total_rows: number
  imported: number
  failed: number
  errors: string[]
}

export interface MetricSeries {
  value: number
  [labelKey: string]: unknown
}

export interface MetricBlock {
  status: string
  help: string
  series: MetricSeries[]
}

export interface MetricsOverview {
  generated_at: string
  config: Record<string, unknown>
  system: {
    cpu_percent: number | null
    rss_bytes: number | null
    cpu_status: string
    rss_status: string
  }
  metrics: Record<string, MetricBlock>
}

export interface ApiEnvelope<T> {
  data?: T
  error?: { detail?: string; code?: string }
}
