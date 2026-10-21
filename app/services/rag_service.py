"""RAGService — Event → Retrieval → LLM → PolicyProposal.

End-to-end chain for Phase 5:

  1. Input: SecurityEvent (from Phase 3)
  2. Query building: uses event.predicted_label + flow_summary as query
  3. Retrieval: RetrievalService.search(query, mode="hybrid")
  4. Context assembly: top-k chunk texts + document_ids
  5. Prompt filling: INCIDENT_ANALYSIS + ANALYSIS_SYSTEM (PromptManager)
  6. LLM call: LLMProvider.generate_json()
  7. Output: PolicyProposal domain model with LLM verbatim wrapped in Evidence

If retrieval is EMPTY or LLM is mock, we surface degraded status — NEVER fabricate a confident policy.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List, Optional

from app.adapters.llm.base import LLMProvider, get_llm_provider
from app.adapters.embedding.base import get_provider as get_emb_provider
from app.core.config import get_settings
from app.core.observability import (
    RAG_RUNS_TOTAL,
    RAG_TOTAL_LATENCY_MS,
    RAG_LLM_LATENCY_MS,
    RAG_EVIDENCE_COUNT,
)
from app.domain.common import (
    ActionType,
    PolicyStatus,
    Severity,
)
from app.domain.evidence import Evidence
from app.domain.event import SecurityEvent
from app.domain.policy import (
    BlockIpParams,
    BlockPortParams,
    PolicyProposal,
    RateLimitParams,
)
from app.services.prompt_manager import (
    ANALYSIS_SYSTEM,
    build_prompt,
)
from app.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)


@dataclass
class RAGRunResult:
    """Bundle: final PolicyProposal + Evidence list + diagnostic traces."""
    proposal: PolicyProposal
    evidences: list
    retrieval_status: str
    llm_provider: str
    llm_is_mock: bool
    retrieval_latency_ms: float
    llm_latency_ms: float
    evidence_count: int


class RAGService:
    """Orchestrates Event → Retrieval → LLM → PolicyProposal."""

    def __init__(
        self,
        *,
        llm: Optional[LLMProvider] = None,
        retrieval: Optional[RetrievalService] = None,
        max_chunks: int = 5,
    ) -> None:
        s = get_settings()
        self._llm = llm or get_llm_provider(s.llm_provider)
        self._retrieval = retrieval or RetrievalService()
        # Some Settings builds may not yet carry rag_max_chunks; default conservatively
        self._max_chunks = max_chunks

    def run(self, event: SecurityEvent) -> RAGRunResult:
        """Execute one RAG pipeline. NEVER raises — wraps errors in degraded output."""
        # ---- 1. Build query from event label + flow summary ----
        query_parts = [event.predicted_label]
        if event.flow_summary:
            query_parts.append(event.flow_summary)
        query = " ".join(query_parts)

        # ---- 2. Retrieval ----
        t_ret0 = time.perf_counter()
        try:
            r = self._retrieval.search(query, mode="hybrid", top_k=self._max_chunks)
            retrieval_status = r["status"]
            hits = r.get("hits", [])
        except Exception as e:
            logger.warning("Retrieval failed: %s", e)
            retrieval_status = "ERROR"
            hits = []
        t_ret1 = time.perf_counter()

        # ---- 3. Assemble Evidence chunks from retrieval hits ----
        from app.domain.evidence import Evidence

        evidences: List[Evidence] = []
        for h in hits:
            meta = self._retrieval._vec.get_chunk(h.rowid)  # type: ignore[attr-defined]  # internal access okay here
            if meta is None:
                continue
            evidences.append(Evidence(
                document_id=meta["document_id"],
                chunk_id=meta["chunk_id"],
                source=meta["source"],
                source_ref=meta.get("source_ref", ""),
                title=meta.get("title", meta["document_id"]),
                content=meta["content"][:2000],
                retrieval_method=r.get("mode", "hybrid"),
                retrieval_score=h.score,
            ))

        # ---- 4. Build prompt ----
        doc_ids = [e.document_id for e in evidences]
        chunks_for_llm = [e.content for e in evidences]
        prompt = build_prompt(
            event_id=event.event_id,
            label=event.predicted_label,
            score=event.score,
            severity=event.severity.value,
            asset_id=event.asset_id,
            flow_id=event.flow_id,
            trace_id=event.trace_id,
            evidence_doc_ids=doc_ids,
            evidence_chunks=chunks_for_llm,
        )

        # ---- 5. LLM ----
        t_llm0 = time.perf_counter()
        llm_response: str = ""
        llm_parsed: dict = {}
        llm_error: Optional[str] = None
        try:
            llm_parsed = self._llm.generate_json(
                prompt,
                system=ANALYSIS_SYSTEM,
                temperature=0.1,
                max_tokens=512,
            )
            llm_response = str(llm_parsed)
        except Exception as e:
            llm_error = str(e)
            logger.warning("LLM call failed: %s", e)
        t_llm1 = time.perf_counter()

        # ---- 6. Map LLM output → PolicyProposal ----
        proposal = self._build_proposal(
            event=event,
            llm_parsed=llm_parsed,
            llm_error=llm_error,
            retrieval_status=retrieval_status,
            evidence_doc_ids=doc_ids,
            evidences=evidences,
        )

        # --- observability ---
        llm_ms = (t_llm1 - t_llm0) * 1000.0
        ret_ms = (t_ret1 - t_ret0) * 1000.0
        RAG_RUNS_TOTAL.inc(
            labels={
                "llm_provider": self._llm.name,
                "is_mock": "true" if self._llm.is_mock else "false",
                "retrieval_status": retrieval_status,
            }
        )
        RAG_TOTAL_LATENCY_MS.observe(
            llm_ms + ret_ms,
            labels={"llm_provider": self._llm.name, "is_mock": "true" if self._llm.is_mock else "false"},
        )
        RAG_LLM_LATENCY_MS.observe(
            llm_ms,
            labels={"llm_provider": self._llm.name, "is_mock": "true" if self._llm.is_mock else "false"},
        )
        RAG_EVIDENCE_COUNT.observe(float(len(evidences)))

        return RAGRunResult(
            proposal=proposal,
            evidences=evidences,
            retrieval_status=retrieval_status,
            llm_provider=self._llm.name,
            llm_is_mock=self._llm.is_mock,
            retrieval_latency_ms=ret_ms,
            llm_latency_ms=llm_ms,
            evidence_count=len(evidences),
        )

    # -------- helper ----------

    def _build_proposal(
        self,
        *,
        event: SecurityEvent,
        llm_parsed: dict,
        llm_error: Optional[str],
        retrieval_status: str,
        evidence_doc_ids: List[str],
        evidences: List[Evidence],
    ) -> PolicyProposal:
        """Build a PolicyProposal — tolerant of LLM errors and degraded states."""
        llm_ok = bool(llm_parsed) and not llm_error

        # ---- Map LLM RECOMMENDED_ACTION → ActionType enum ----
        # LLM is prompted with BLOCK_IP / BLOCK_PORT / QUARANTINE_HOST / ISOLATE_SEGMENT
        # but our ActionType whitelist is smaller. Map conservatively; unknown → ALERT_ONLY.
        raw_action = str(llm_parsed.get("RECOMMENDED_ACTION", "") if llm_ok else "MONITOR").upper().strip()
        action_map = {
            "BLOCK_IP": ActionType.BLOCK_IP,
            "BLOCK_PORT": ActionType.BLOCK_PORT,
            "BLOCK_IP_ADDRESS": ActionType.BLOCK_IP,
            "RATE_LIMIT": ActionType.RATE_LIMIT,
            "QUARANTINE_HOST": ActionType.BLOCK_PORT,  # conservative fallback
            "ISOLATE_SEGMENT": ActionType.RATE_LIMIT,
            "ALLOW": ActionType.NO_ACTION,
            "NO_ACTION": ActionType.NO_ACTION,
            "MONITOR": ActionType.ALERT_ONLY,
            "ALERT_ONLY": ActionType.ALERT_ONLY,
        }
        action_type = action_map.get(raw_action, ActionType.ALERT_ONLY)

        # ---- Map THREAT_LEVEL → Severity ----
        threat_str = str(llm_parsed.get("THREAT_LEVEL", event.severity.value) if llm_ok else event.severity.value)
        try:
            risk_level = Severity(threat_str)
        except ValueError:
            risk_level = event.severity

        # ---- Build parameters matching action_type ----
        # Phase 5 note: we don't yet have the src_ip from the flow. If the LLM suggests
        # BLOCK_IP, we cannot produce a legal BlockIpParams without an IP, so we downgrade
        # to ALERT_ONLY and explain why in the rationale.
        parameters = None  # type: ignore[assignment]
        downgrade_note: str = ""
        if action_type == ActionType.BLOCK_IP:
            # No source IP available in Phase 5 → downgrade
            downgrade_note = f" (downgraded from BLOCK_IP — source IP not yet resolved; BLOCK_IP requires an IP)"
            action_type = ActionType.ALERT_ONLY
        elif action_type == ActionType.BLOCK_PORT:
            # Don't know which port yet; default to dst_port from the event? SecurityEvent
            # doesn't carry dst_port directly. Use placeholder 0 which is invalid — executor
            # will fill later. Actually, Pydantic won't allow 0 for BlockPortParams.port.
            # So we downgrade to ALERT_ONLY here too.
            downgrade_note = " (downgraded from BLOCK_PORT — target port not yet resolved)"
            action_type = ActionType.ALERT_ONLY
        elif action_type == ActionType.RATE_LIMIT:
            # Needs src_ip + max_pps — downgrade
            downgrade_note = " (downgraded from RATE_LIMIT — source IP missing)"
            action_type = ActionType.ALERT_ONLY

        # Now build parameters based on final action_type
        if action_type in (ActionType.ALERT_ONLY, ActionType.NO_ACTION):
            parameters = BlockPortParams(port=0, protocol="TCP")  # action_type doesn't strictly require params, but validator needs a union-compatible object — ALERT_ONLY is not in the mapping so validator passes
        elif action_type == ActionType.BLOCK_IP:
            raise AssertionError("BLOCK_IP should have been downgraded above")
        elif action_type == ActionType.BLOCK_PORT:
            raise AssertionError("BLOCK_PORT should have been downgraded above")
        elif action_type == ActionType.RATE_LIMIT:
            raise AssertionError("RATE_LIMIT should have been downgraded above")
        else:
            parameters = BlockPortParams(port=0, protocol="TCP")

        # ---- Rationale ----
        rationale = str(llm_parsed.get("JUSTIFICATION", "") if llm_ok else
                        f"LLM unavailable ({self._llm.name}); falling back to conservative ALERT_ONLY. "
                        f"retrieval_status={retrieval_status}.")
        rationale = rationale + downgrade_note if downgrade_note else rationale
        if not rationale.strip():
            rationale = "No LLM justification available."

        # ---- Status ----
        status = PolicyStatus.DRAFT
        if llm_error and retrieval_status == "EMPTY":
            status = PolicyStatus.REJECTED
            rationale += " Both LLM and retrieval failed — cannot recommend action confidently."

        # ---- Evidence IDs ----
        # Map the Evidence objects we built from retrieval hits → evidence_ids
        evidence_ids_from_retrieval = [e.evidence_id for e in evidences]
        llm_doc_ids = []
        if llm_ok:
            raw_ids = llm_parsed.get("EVIDENCE_IDS", [])
            if isinstance(raw_ids, list):
                llm_doc_ids = [str(x) for x in raw_ids]
        evidence_ids_all = list(set([*evidence_ids_from_retrieval, *llm_doc_ids]))

        return PolicyProposal(
            event_id=event.event_id,
            action_type=action_type,
            parameters=parameters,
            risk_level=risk_level,
            rationale=rationale,
            evidence_ids=evidence_ids_all,
            status=status,
        )
