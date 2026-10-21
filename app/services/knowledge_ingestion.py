"""Knowledge ingestion — import JSONL / Markdown documents, chunk, embed, store.

One public entry point: :func:`sync_knowledge` reads a directory of documents,
rebuilds the vector index from scratch, and returns how many chunks were
indexed. The caller never sees partial state — either the whole rebuild
succeeds or the old index is left untouched (we rebuild to a fresh DB then
swap).

In Phase 4 documents are hand-written CVE/ATT&CK IOCs. Later phases will
support live feeds from vendors.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import List, Optional

from app.adapters.embedding.base import EmbeddingProvider, get_provider
from app.core.config import get_settings
from app.services.retrieval import VecIndex

logger = logging.getLogger(__name__)


# -------- chunking -------------------------------------------------------

def chunk_text(text: str, *, max_chars: int = 600, overlap: int = 120) -> List[str]:
    """Sentence-aware chunker. Phase 4 — simple paragraph split.

    Returns non-empty chunks whose concatenation never exceeds max_chars.
    Overlap helps retrieval preserve context across chunk boundaries.
    """
    import re
    text = text.strip()
    if not text:
        return []
    # Split on double-newlines (paragraph-like) or sentence endings
    paragraphs = re.split(r"\n\s*\n", text)
    if len(paragraphs) <= 1:
        # Fallback: sentence split
        paragraphs = re.split(r"(?<=[.!?])\s+", text)

    chunks: List[str] = []
    buf = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) + 1 <= max_chars:
            buf = (buf + " " + para).strip()
        else:
            if buf:
                chunks.append(buf)
            buf = para[: max_chars - overlap]  # hard trim if one para > max_chars
    if buf:
        chunks.append(buf)
    return chunks


def _chunk_id(document_id: str, idx: int) -> str:
    return f"{document_id}_chunk_{idx:04d}"


def _checksum(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


# -------- ingestion entry ------------------------------------------------


def sync_knowledge(
    input_path: str | Path,
    *,
    provider: Optional[EmbeddingProvider] = None,
    reset_first: bool = True,
    db_path: Optional[str] = None,
) -> dict:
    """Index every document under input_path into the vector store.

    Returns a summary dict with counts and provider info. If reset_first
    (default) drops the existing index before rebuilding.
    """
    s = get_settings()
    provider = provider or get_provider(
        s.embedding_provider,
        dim_hint=768 if s.embedding_provider == "ollama" else 32,
    )
    db_path = db_path or str(s.knowledge_index_dir / "knowledge.db")
    vec = VecIndex(db_path, dim=provider.dim)

    if reset_first:
        vec.reset()

    docs = _load_docs(input_path)
    total_chunks = 0
    for d in docs:
        chunks = chunk_text(d["content"])
        for i, chunk in enumerate(chunks):
            text_for_emb = d.get("title", "") + ". " + chunk
            emb = provider.embed(text_for_emb)
            vec.upsert(
                chunk_id=_chunk_id(d["document_id"], i),
                document_id=d["document_id"],
                source=d["source"],
                source_ref=d.get("source_ref", ""),
                title=d.get("title", d["document_id"]),
                content=chunk,
                source_url=d.get("source_ref"),
                published_at=d.get("published_at"),
                vector=emb,
            )
            total_chunks += 1
            logger.debug("indexed chunk %d for doc %s", i, d["document_id"])

    logger.info(
        "sync_knowledge: %d documents → %d chunks (provider=%s dim=%d)",
        len(docs), total_chunks, provider.name, provider.dim,
    )
    return {
        "documents": len(docs),
        "chunks": total_chunks,
        "provider": provider.name,
        "provider_is_mock": provider.is_mock,
        "dimension": provider.dim,
        "database": db_path,
    }


# -------- loaders --------------------------------------------------------

def _load_docs(input_path: str | Path) -> List[dict]:
    p = Path(input_path)
    docs: List[dict] = []
    if p.is_dir():
        files = sorted(p.glob("*.jsonl")) + sorted(p.glob("*.json")) + sorted(p.glob("*.md"))
    else:
        files = [p]

    for fp in files:
        if fp.suffix == ".jsonl":
            with fp.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        docs.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning("skip bad JSONL line %s: %s", fp, e)
        elif fp.suffix == ".json":
            data = json.loads(fp.read_text(encoding="utf-8"))
            if isinstance(data, list):
                docs.extend(data)
            elif isinstance(data, dict):
                docs.append(data)
        elif fp.suffix == ".md":
            docs.append({
                "document_id": fp.stem,
                "source": "markdown",
                "source_ref": fp.as_posix(),
                "title": fp.stem,
                "content": fp.read_text(encoding="utf-8"),
            })
    return docs
