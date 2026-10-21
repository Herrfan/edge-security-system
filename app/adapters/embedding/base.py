"""Embedding provider abstraction.

Every embedding source must implement :class:`EmbeddingProvider`. The system
always falls back to :class:`MockEmbedding` when the real provider is
unavailable — but it MUST surface `retrieval_status=DEGRADED` to the caller
instead of silently pretending vectors are real.
"""
from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract interface. Two impls: Ollama (real) and Mock (degraded)."""

    @property
    @abstractmethod
    def dim(self) -> int: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """True for degraded providers — callers MUST mark retrieval_status DEGRADED."""
        ...

    @abstractmethod
    def embed(self, text: str) -> np.ndarray: ...


# ---------------- Mock fallback ------------------------------------------


class MockEmbedding(EmbeddingProvider):
    """Deterministic hash-based "embedding" — usable for tests when Ollama is down.

    NOT semantically meaningful — do not use mock vectors for real retrieval.
    A simple hash-of-chars normalization yields a 32-dim vector that changes
    with the text. Exists so retrieval code paths can be exercised offline.
    """

    def __init__(self, dim: int = 32) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def name(self) -> str:
        return "mock-hash"

    @property
    def is_mock(self) -> bool:
        return True

    def embed(self, text: str) -> np.ndarray:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        # Spread the hash across dim floats in [-1, 1]
        vec = np.zeros(self._dim, dtype=np.float32)
        for i in range(self._dim):
            chunk = h[i % len(h): i % len(h) + 8]
            f = int.from_bytes(chunk, "big", signed=False) / 2**64
            vec[i] = float(f * 2.0 - 1.0)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec


# ---------------- Factory -----------------------------------------------


def get_provider(kind: str = "ollama", *, dim_hint: int = 768) -> EmbeddingProvider:
    """Construct a provider by name. Auto-falls back to Mock on failure."""
    if kind == "ollama":
        try:
            from app.adapters.embedding.ollama_embed import OllamaEmbedding
            return OllamaEmbedding()
        except Exception as e:
            logger.warning("OllamaEmbedding init failed (%s) → falling back to MockEmbedding", e)
    # Default / fallback
    return MockEmbedding(dim=dim_hint)
