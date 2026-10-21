"""End-to-end verification of Phase 4 retrieval.

Steps:
  1. sync_knowledge (JSONL → VecIndex via Ollama/Mock embeddings)
  2. RetrievalService.search on three real queries
  3. Print results
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.knowledge_ingestion import sync_knowledge  # noqa: E402
from app.services.retrieval import RetrievalService  # noqa: E402

SAMPLE_DOCS = ROOT / "data" / "knowledge" / "security_knowledge.jsonl"
TMP_DB = ROOT / "data" / "knowledge_index" / "knowledge.db"

if __name__ == "__main__":
    print("=== Step 1: sync_knowledge ===")
    t0 = time.perf_counter()
    summary = sync_knowledge(SAMPLE_DOCS, reset_first=True)
    t1 = time.perf_counter()
    print(f"  {summary}  ({t1 - t0:.2f}s)")

    svc = RetrievalService()

    print(f"\n=== Step 2: retrieval.status (count={svc.count()}) ===")

    queries = [
        "port scan traffic SYN packets short duration",
        "SSH brute force failed attempts port 22",
        "Log4j RCE JNDI injection CVE",
    ]

    for q in queries:
        for mode in ("keyword", "vector", "hybrid"):
            print(f"\n--- query: {q!r}  mode={mode} ---")
            t0 = time.perf_counter()
            result = svc.search(q, mode=mode, top_k=3)
            t1 = time.perf_counter()
            print(f"  status={result['status']}  provider={result['provider']}  "
                  f"is_mock={result['is_mock']}  ({(t1 - t0) * 1000:.1f}ms)")
            for h in result["hits"][:3]:
                print(f"    doc={h.document_id:30s} rowid={h.rowid} score={h.score:.3f}  "
                      f"chunk_id={h.chunk_id}")
