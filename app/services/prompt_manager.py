"""PromptManager — hardcoded RAG prompt templates.

Phase 5: keep templates in code. Later we'll move them to a config file / DB.
Two prompts matter:

1. `ANALYSIS_SYSTEM` — system role (defensive security analyst persona)
2. `INCIDENT_ANALYSIS` — user prompt template (fills with event + evidence)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


ANALYSIS_SYSTEM = """You are a defensive security analyst supporting an edge network security system.
Your job is to triage a detected security event, consult available threat intelligence,
and propose a policy action (in dry-run).

Rules:
- NEVER invent evidence; only cite what the retrieved knowledge actually says.
- If evidence is weak or conflicting, say so explicitly in JUSTIFICATION.
- Keep RECOMMENDED_ACTION within the allowed set: ALLOW / MONITOR / QUARANTINE_HOST / BLOCK_IP / BLOCK_PORT / ISOLATE_SEGMENT.
- THREAT_LEVEL must be one of: INFO / LOW / MEDIUM / HIGH / CRITICAL.
- Return valid JSON — no markdown fences, no prose outside the JSON object."""


INCIDENT_ANALYSIS = """## Security Event
- Event ID: {event_id}
- Label (detector): {label}
- Confidence Score: {score}
- Severity (system): {severity}
- Asset: {asset_id}
- Flow ID: {flow_id}
- Trace ID: {trace_id}

## Relevant Security Knowledge (top {n_chunks} retrieved via hybrid RRF)
{evidence_block}

## Instructions
Based on the event and the retrieved knowledge above, return a single JSON object with these fields:

{{
  "THREAT_LEVEL": "INFO|LOW|MEDIUM|HIGH|CRITICAL",
  "RECOMMENDED_ACTION": "ALLOW|MONITOR|QUARANTINE_HOST|BLOCK_IP|BLOCK_PORT|ISOLATE_SEGMENT",
  "JUSTIFICATION": "one-sentence rationale citing evidence where possible",
  "EVIDENCE_IDS": ["list of document_id values you consulted"]
}}"""


# ------------------------- helpers ---------------------------------------

def format_evidence_block(doc_ids: list[str], chunks: list[str]) -> str:
    """Render retrieved chunks as a numbered list for the LLM."""
    if not doc_ids:
        return "(no evidence retrieved — retrieval may have failed)"
    lines = []
    for i, (did, c) in enumerate(zip(doc_ids, chunks), start=1):
        # Truncate each chunk to avoid blowing context
        snippet = c[:500]
        lines.append(f"[{i}] source={did}\n{snippet}\n")
    return "\n".join(lines)


def build_prompt(
    *,
    event_id: str,
    label: str,
    score: float,
    severity: str,
    asset_id: str,
    flow_id: str | None,
    trace_id: str | None,
    evidence_doc_ids: list[str],
    evidence_chunks: list[str],
) -> str:
    """Fill the INCIDENT_ANALYSIS template with real values."""
    return INCIDENT_ANALYSIS.format(
        event_id=event_id,
        label=label,
        score=round(score, 4),
        severity=severity,
        asset_id=asset_id,
        flow_id=flow_id or "(unknown)",
        trace_id=trace_id or "(unknown)",
        n_chunks=len(evidence_doc_ids),
        evidence_block=format_evidence_block(evidence_doc_ids, evidence_chunks),
    )
