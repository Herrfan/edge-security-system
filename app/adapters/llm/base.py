"""LLM provider abstraction.

Two implementations:

- :class:`OllamaLLM`    — real call to local Ollama (qwen2.5:3b default)
- :class:`MockLLM`      — deterministic rule-based fallback, used when Ollama
                          is unavailable. ALWAYS surfaces is_mock=True so callers
                          mark retrieval_status=DEGRADED.
"""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import requests

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract interface. All LLMs must implement :meth:`generate`."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def is_mock(self) -> bool: ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
    ) -> str:
        """Return raw text response. Caller is responsible for parsing."""
        ...

    def generate_json(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
    ) -> Dict[str, Any]:
        """Generate and parse JSON from response. Tolerant of stray markdown."""
        raw = self.generate(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
        return _parse_json_tolerant(raw)


# ---------------- OllamaLLM ----------------------------------------------


class OllamaLLM(LLMProvider):
    """Local Ollama via HTTP. Default model qwen2.5:3b (CPU-friendly)."""

    def __init__(self) -> None:
        s = get_settings()
        self._base = s.ollama_base_url.rstrip("/")
        self._model = s.llm_model
        self._timeout = s.llm_timeout_seconds

    @property
    def name(self) -> str:
        return f"ollama:{self._model}"

    @property
    def is_mock(self) -> bool:
        return False

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        resp = requests.post(
            f"{self._base}/api/generate",
            json=payload,
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"ollama generate error {resp.status_code}: {resp.text[:200]}")
        return resp.json().get("response", "")


# ---------------- MockLLM ------------------------------------------------

class MockLLM(LLMProvider):
    """Heuristic replacement used when Ollama is down.

    Uses the incident label + severity directly to produce a structured JSON.
    NOT intelligent — exists so RAGService logic paths can be tested offline.
    """

    @property
    def name(self) -> str:
        return "mock-rule"

    @property
    def is_mock(self) -> bool:
        return True

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
    ) -> str:
        # Simple keyword detection within the prompt to produce stable JSON
        label = "unknown"
        if "brute" in prompt.lower():
            label = "brute_force"
        elif "port" in prompt.lower() and ("scan" in prompt.lower() or "syn" in prompt.lower()):
            label = "port_scan"
        elif "log4j" in prompt.lower() or "rce" in prompt.lower() or "jndi" in prompt.lower():
            label = "rce"
        elif "ddos" in prompt.lower() or "flood" in prompt.lower():
            label = "ddos"
        elif "normal" in prompt.lower() or "benign" in prompt.lower():
            label = "normal"

        action_map = {
            "brute_force": "BLOCK_IP",
            "port_scan": "BLOCK_IP",
            "rce": "QUARANTINE_HOST",
            "ddos": "BLOCK_IP",
            "normal": "MONITOR",
            "unknown": "MONITOR",
        }
        threat_map = {
            "brute_force": "HIGH",
            "port_scan": "MEDIUM",
            "rce": "CRITICAL",
            "ddos": "HIGH",
            "normal": "INFO",
            "unknown": "MEDIUM",
        }
        response = {
            "THREAT_LEVEL": threat_map[label],
            "RECOMMENDED_ACTION": action_map[label],
            "JUSTIFICATION": f"MockLLM heuristically mapped label={label} to {action_map[label]}.",
            "IS_RAG_USED": False,
        }
        return json.dumps(response)


# ---------------- Factory ------------------------------------------------


def get_llm_provider(kind: str = "ollama") -> LLMProvider:
    try:
        if kind == "ollama":
            return OllamaLLM()
    except Exception as e:
        logger.warning("OllamaLLM init failed (%s) → falling back to MockLLM", e)
    return MockLLM()


# ---------------- JSON parsing helper ------------------------------------


def _parse_json_tolerant(raw: str) -> Dict[str, Any]:
    """Try json.loads directly; else extract first {...} block greedily."""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Fallback: find the first balanced {...} in the response
    start = raw.find("{")
    if start < 0:
        raise ValueError(f"LLM output has no JSON object: {raw[:200]}")
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(raw[start: i + 1])
    raise ValueError(f"LLM JSON block not closed: {raw[start:start+200]}")
