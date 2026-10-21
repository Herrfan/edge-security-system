"""Ollama embedding provider — nomic-embed-text via HTTP.

Ollama is a local inference engine; we call its API endpoint directly with
requests (no heavy client SDK). Defaults to 127.0.0.1:11434.
"""
from __future__ import annotations

import logging
from typing import List

import numpy as np
import requests

from app.adapters.embedding.base import EmbeddingProvider
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class OllamaEmbedding(EmbeddingProvider):
    """Real local embedding via Ollama."""

    def __init__(self) -> None:
        s = get_settings()
        self._base = s.ollama_base_url.rstrip("/")
        self._model = s.embedding_model
        self._timeout = s.llm_timeout_seconds
        # Probe dim on first call — nomic-embed-text defaults to 768
        self._dim: int | None = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            self._dim = len(self.embed("probe"))
        return self._dim

    @property
    def name(self) -> str:
        return f"ollama:{self._model}"

    @property
    def is_mock(self) -> bool:
        return False

    def embed(self, text: str) -> np.ndarray:
        resp = requests.post(
            f"{self._base}/api/embeddings",
            json={"model": self._model, "prompt": text},
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"ollama embedding error {resp.status_code}: {resp.text[:200]}")
        emb = resp.json()["embedding"]
        arr = np.asarray(emb, dtype=np.float32)
        if self._dim is None:
            self._dim = arr.shape[0]
        return arr

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Small batch — Ollama doesn't have batch endpoint; issue sequentially."""
        return [self.embed(t) for t in texts]
