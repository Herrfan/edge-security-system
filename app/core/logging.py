"""Structured logging with data-class redaction.

Redaction rules are deterministic and applied at the logging layer so
developers never accidentally write raw IPs, ports, or packet payloads
to disk. The Filter is registered on the root logger at startup.
"""
from __future__ import annotations

import logging
import re
from typing import Any

# IPv4 address pattern
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# Generic port in context (e.g. `:8080`, `port=443`)
_PORT_RE = re.compile(r"\b(port=|:)(\d{2,5})\b", re.IGNORECASE)
# Typical credential-looking strings: api_key=xxx, password=xxx
_SECRET_KV_RE = re.compile(
    r"(?i)(\b(?:api[_-]?key|secret|password|token|auth|credential)\s*[:=]\s*)([^\s&,;'\"]+)"
)
# Dict keys that indicate the value should be masked regardless of content
_SENSITIVE_KEY_RE = re.compile(
    r"(?i)^(api[_-]?key|secret|password|token|auth|credential|api_key|api-key)$"
)


def _redact_value(value: Any) -> Any:
    """Recursively redact a single value used in log messages."""
    if isinstance(value, str):
        s = _SECRET_KV_RE.sub(lambda m: m.group(1) + "***REDACTED***", value)
        s = _IPV4_RE.sub("*.*.*.*", s)
        s = _PORT_RE.sub(lambda m: m.group(1) + "***", s)
        return s
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            # If the key explicitly indicates a secret, mask the value wholesale
            if isinstance(k, str) and _SENSITIVE_KEY_RE.match(k):
                out[k] = "***REDACTED***" if isinstance(v, str) else _redact_value(v)
            else:
                out[k] = _redact_value(v)
        return out
    if isinstance(value, (list, tuple)):
        return [_redact_value(v) for v in value]
    return value


class RedactionFilter(logging.Filter):
    """Replace sensitive-looking content before a LogRecord is emitted."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Redact the rendered message
        if isinstance(record.msg, str):
            record.msg = _redact_value(record.msg)
        # Redact individual args used in %-formatting
        if record.args:
            record.args = tuple(_redact_value(a) for a in record.args)
        # Redact any extra attributes pydantic/logging may inject
        for attr_name in ("payload", "data", "context", "extra"):
            extra = getattr(record, attr_name, None)
            if extra is not None:
                try:
                    setattr(record, attr_name, _redact_value(extra))
                except Exception:
                    pass
        return True


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger with redaction. Safe to call repeatedly."""
    root = logging.getLogger()
    # Avoid double-adding filters on reload
    existing = [type(f).__name__ for f in root.filters]
    if "RedactionFilter" not in existing:
        root.addFilter(RedactionFilter())

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
