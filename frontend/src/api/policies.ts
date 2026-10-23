import { apiGet, apiPost } from './client'
import type { ExecutionRecord, PolicyProposal, PolicyStatus, ValidationResult } from '@/types/api'

export function listProposals(status?: PolicyStatus, limit = 50) {
  return apiGet<PolicyProposal[]>('/api/v1/policy-proposals', {
    status: status ?? '',
    limit,
  })
}

export function getProposal(policyId: string) {
  return apiGet<PolicyProposal[]>(`/api/v1/policy-proposals`, { limit: 200 }).then((list) =>
    list.find((p) => p.policy_id === policyId) ?? null,
  )
  // Backend doesn't have GET /policy-proposal/{id}; list + client-side lookup.
}

export function generateProposal(eventId: string) {
  return apiPost<{
    proposal: PolicyProposal
    evidences: unknown[]
    evidence_count: number
    retrieval_status: string
    llm_provider: string
    llm_is_mock: boolean
    llm_latency_ms: number
  }>('/api/v1/policy-proposal/generate', { event_id: eventId })
}

export function validateProposal(policyId: string, srcIp?: string, dstPort?: number) {
  return apiPost<ValidationResult>('/api/v1/policy-proposal/validate', {
    policy_id: policyId,
    src_ip: srcIp ?? null,
    dst_port: dstPort ?? null,
  })
}

export function approveProposal(
  policyId: string,
  approve: boolean,
  reason?: string,
  approver?: string,
) {
  return apiPost<{
    policy_id: string
    status: 'APPROVED' | 'REJECTED'
    approver?: string | null
    reason?: string | null
  }>('/api/v1/policy-proposal/approve', {
    policy_id: policyId,
    approve,
    reason: reason ?? null,
    approver: approver ?? null,
  })
}

export function executeProposal(policyId: string, mode: 'DRY_RUN' | 'REAL' = 'DRY_RUN') {
  return apiPost<ExecutionRecord & { validator_reasons?: string[] }>(
    '/api/v1/policy-proposal/execute',
    { policy_id: policyId, mode },
  )
}
