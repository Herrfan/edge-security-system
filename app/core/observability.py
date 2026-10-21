"""Lightweight in-process Prometheus-compatible metrics.

NO external dependency (no prometheus_client). Implements only what Phase 7
needs: ``Counter``, ``Gauge`` and ``Histogram`` with label support and
Prometheus exposition-format rendering.

Design goals:

- Thread-safe under concurrent FastAPI requests (single ``threading.Lock``).
- Exposes the canonical Prometheus text format so a real Prometheus server
  can scrape ``/metrics`` directly.
- Each metric also serialises to a simple JSON dict for the overview endpoint.
- Metrics that are never set retain value ``unavailable`` in the overview —
  we MUST NOT fabricate zeroes for missing signals (任务书 §7).
"""
from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Base classes
# ---------------------------------------------------------------------------


_LABEL_VALUE_INVALID = re_sub_chars = None  # placeholder; imports at bottom


class _LabeledSeries:
    """One concrete time-series identified by a frozen label tuple."""

    __slots__ = ("labels", "_lock")

    def __init__(self, labels: Tuple[Tuple[str, str], ...]) -> None:
        self.labels = labels
        self._lock = threading.Lock()


class Counter:
    """Monotonically-increasing integer counter with label dimensions."""

    def __init__(self, name: str, help_text: str, label_names: Iterable[str]) -> None:
        self.name = name
        self.help = help_text
        self.label_names: Tuple[str, ...] = tuple(label_names)
        self._series: Dict[Tuple[Tuple[str, str], ...], _CounterSeries] = {}
        self._lock = threading.Lock()

    def _get_or_create(self, label_values: Tuple[str, ...]) -> "_CounterSeries":
        if len(label_values) != len(self.label_names):
            raise ValueError(
                f"{self.name}: expected {len(self.label_names)} label values, got {len(label_values)}"
            )
        key = tuple(zip(self.label_names, label_values))
        s = self._series.get(key)
        if s is None:
            with self._lock:
                s = self._series.get(key)
                if s is None:
                    s = _CounterSeries(key)
                    self._series[key] = s
        return s

    def inc(self, value: float = 1.0, *, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment. ``labels`` must match declared label_names."""
        if labels is None:
            labels = {}
        lv = self._resolve_labels(labels)
        self._get_or_create(lv).inc(value)

    def _resolve_labels(self, labels: Dict[str, str]) -> Tuple[str, ...]:
        return tuple(str(labels.get(n, "")) for n in self.label_names)

    # ---- internal ----

    def _collect(self) -> List[Tuple[Tuple[Tuple[str, str], ...], float]]:
        """Return [(label_tuple, value), ...] sorted by labels."""
        out = []
        for key, s in sorted(self._series.items()):
            out.append((key, s.value()))
        return out


class _CounterSeries(_LabeledSeries):
    def __init__(self, labels) -> None:
        super().__init__(labels)
        self._value = 0.0

    def inc(self, v: float = 1.0) -> None:
        if v < 0:
            raise ValueError("Counter.decrease is forbidden")
        with self._lock:
            self._value += v

    def value(self) -> float:
        with self._lock:
            return self._value


class Gauge:
    """Single numeric value (can go up or down)."""

    def __init__(self, name: str, help_text: str, label_names: Iterable[str]) -> None:
        self.name = name
        self.help = help_text
        self.label_names: Tuple[str, ...] = tuple(label_names)
        self._series: Dict[Tuple[Tuple[str, str], ...], _GaugeSeries] = {}
        self._lock = threading.Lock()

    def set(self, value: float, *, labels: Optional[Dict[str, str]] = None) -> None:
        lv = self._resolve_labels(labels or {})
        self._get_or_create(lv).set(value)

    def inc(self, value: float = 1.0, *, labels: Optional[Dict[str, str]] = None) -> None:
        lv = self._resolve_labels(labels or {})
        self._get_or_create(lv).inc(value)

    def dec(self, value: float = 1.0, *, labels: Optional[Dict[str, str]] = None) -> None:
        lv = self._resolve_labels(labels or {})
        self._get_or_create(lv).inc(-value)

    def get(self, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Return current value or None if never set (unavailable)."""
        lv = self._resolve_labels(labels or {})
        s = self._series.get(tuple(zip(self.label_names, lv)))
        return s.value() if s else None

    def _resolve_labels(self, labels: Dict[str, str]) -> Tuple[str, ...]:
        return tuple(str(labels.get(n, "")) for n in self.label_names)

    def _get_or_create(self, label_values: Tuple[str, ...]) -> "_GaugeSeries":
        key = tuple(zip(self.label_names, label_values))
        s = self._series.get(key)
        if s is None:
            with self._lock:
                s = self._series.get(key)
                if s is None:
                    s = _GaugeSeries(key)
                    self._series[key] = s
        return s

    def _collect(self) -> List[Tuple[Tuple[Tuple[str, str], ...], float]]:
        out = []
        for key, s in sorted(self._series.items()):
            out.append((key, s.value()))
        return out


class _GaugeSeries(_LabeledSeries):
    def __init__(self, labels) -> None:
        super().__init__(labels)
        self._value: Optional[float] = None

    def set(self, v: float) -> None:
        with self._lock:
            self._value = v

    def inc(self, v: float) -> None:
        with self._lock:
            self._value = (self._value or 0.0) + v

    def value(self) -> Optional[float]:
        with self._lock:
            return self._value


class Histogram:
    """Prometheus-style histogram with static upper-bound buckets.

    Default buckets mirror common latency distributions. Each call to
    :meth:`observe` increments the appropriate cumulative bucket and the total
    sum/count.
    """

    DEFAULT_BUCKETS_MS = (
        1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0, 10000.0,
        math.inf,
    )

    def __init__(
        self,
        name: str,
        help_text: str,
        label_names: Iterable[str],
        buckets: Optional[Iterable[float]] = None,
    ) -> None:
        self.name = name
        self.help = help_text
        self.label_names: Tuple[str, ...] = tuple(label_names)
        self.buckets: Tuple[float, ...] = tuple(sorted(buckets or self.DEFAULT_BUCKETS_MS))
        self._series: Dict[Tuple[Tuple[str, str], ...], _HistogramSeries] = {}
        self._lock = threading.Lock()

    def observe(self, value: float, *, labels: Optional[Dict[str, str]] = None) -> None:
        if math.isnan(value):
            return  # silently skip NaN — signals a bug upstream
        lv = self._resolve_labels(labels or {})
        self._get_or_create(lv).observe(value)

    def _resolve_labels(self, labels: Dict[str, str]) -> Tuple[str, ...]:
        return tuple(str(labels.get(n, "")) for n in self.label_names)

    def _get_or_create(self, label_values: Tuple[str, ...]) -> "_HistogramSeries":
        key = tuple(zip(self.label_names, label_values))
        s = self._series.get(key)
        if s is None:
            with self._lock:
                s = self._series.get(key)
                if s is None:
                    s = _HistogramSeries(key, self.buckets)
                    self._series[key] = s
        return s

    def _collect(self) -> List[Tuple[str, Tuple[Tuple[str, str], ...], float, str]]:
        """Return [(suffix, labels, value, le_str)] sorted."""
        out = []
        for key, s in sorted(self._series.items()):
            counts = s.bucket_counts()
            for upper, cnt in zip(self.buckets, counts):
                le = "+Inf" if math.isinf(upper) else f"{upper:g}"
                out.append((f"{self.name}_bucket", key, cnt, le))
            out.append((f"{self.name}_sum", key, s.sum(), ""))
            out.append((f"{self.name}_count", key, s.count(), ""))
        return out


class _HistogramSeries(_LabeledSeries):
    def __init__(self, labels, buckets: Tuple[float, ...]) -> None:
        super().__init__(labels)
        self.buckets = buckets
        self._counts = [0] * len(buckets)
        self._sum = 0.0
        self._count = 0

    def observe(self, v: float) -> None:
        with self._lock:
            self._count += 1
            self._sum += v
            for i, upper in enumerate(self.buckets):
                if v <= upper:
                    self._counts[i] += 1

    def sum(self) -> float:
        with self._lock:
            return self._sum

    def count(self) -> int:
        with self._lock:
            return self._count

    def bucket_counts(self) -> List[int]:
        # Prometheus bucket convention: each observation increments ALL
        # buckets with le >= value. So self._counts is ALREADY cumulative.
        return list(self._counts)


# ---------------------------------------------------------------------------
# Registry + Prometheus exposition formatting
# ---------------------------------------------------------------------------


class Registry:
    """Singleton registry — every metric registers itself here on construction."""

    _instance: Optional["Registry"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._metrics: Dict[str, Any] = {}  # name → Counter | Gauge | Histogram

    @classmethod
    def instance(cls) -> "Registry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, metric: Any) -> Any:
        if metric.name in self._metrics:
            raise ValueError(f"metric name {metric.name!r} already registered")
        self._metrics[metric.name] = metric
        return metric

    def get(self, name: str) -> Optional[Any]:
        return self._metrics.get(name)

    def all(self) -> List[Any]:
        """Return metrics in registration order."""
        return list(self._metrics.values())

    # ---- rendering ----

    def exposition_text(self) -> str:
        """Render all registered metrics in Prometheus text format."""
        lines: List[str] = []
        for m in self.all():
            _render_metric(m, lines)
        return "\n".join(lines) + "\n"

    def to_overview(self) -> Dict[str, Any]:
        """Compact JSON-friendly snapshot for ``/metrics/overview``.

        Metrics that have never been observed carry explicit
        ``status: unavailable`` instead of a fabricated zero.
        """
        out: Dict[str, Any] = {}
        for m in self.all():
            collected = m._collect()
            if not collected:
                out[m.name] = {
                    "status": "unavailable",
                    "help": getattr(m, "help", ""),
                    "series": [],
                }
                continue
            series = []
            for item in collected:
                if isinstance(m, Histogram):
                    suffix, lbls, val, le = item  # type: ignore[misc]
                    d = _labels_to_dict(lbls)
                    if le:
                        d["le"] = le
                    d["value"] = val
                    series.append(d)
                else:
                    lbls, val = item
                    series.append({**_labels_to_dict(lbls), "value": val})
            out[m.name] = {
                "status": "ok",
                "help": getattr(m, "help", ""),
                "series": series,
            }
        return out


def _labels_to_dict(lbls: Tuple[Tuple[str, str], ...]) -> Dict[str, str]:
    return {k: v for k, v in lbls}


def _escape_label_value(v: str) -> str:
    # Prometheus format: \ → \\, " → \", newline → \n
    return v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _labels_to_str(lbls: Tuple[Tuple[str, str], ...]) -> str:
    if not lbls:
        return ""
    parts = [f'{k}="{_escape_label_value(str(v))}"' for k, v in lbls]
    return "{" + ",".join(parts) + "}"


def _render_metric(m: Any, lines: List[str]) -> None:
    lines.append(f"# HELP {m.name} {m.help}")
    if isinstance(m, Counter):
        lines.append(f"# TYPE {m.name} counter")
        for lbls, val in m._collect():
            lines.append(f"{m.name}{_labels_to_str(lbls)} {_fmt_val(val)}")
    elif isinstance(m, Gauge):
        lines.append(f"# TYPE {m.name} gauge")
        for lbls, val in m._collect():
            lines.append(f"{m.name}{_labels_to_str(lbls)} {_fmt_val(val)}")
    elif isinstance(m, Histogram):
        lines.append(f"# TYPE {m.name} histogram")
        rows = m._collect()
        # Group by label key, emit _bucket / _sum / _count in canonical order
        groups: Dict[Tuple[Tuple[str, str], ...], List[Tuple[str, float, str]]] = defaultdict(list)
        for suffix, lbls, val, le in rows:
            groups[lbls].append((suffix, val, le))
        for lbls in sorted(groups.keys()):
            entries = groups[lbls]
            # Reorder: buckets in le asc, then _sum, then _count
            def _sort_key(row: Tuple[str, float, str]):
                suffix, _, le = row
                if suffix.endswith("_bucket"):
                    bucket_order = m.buckets.index(float(le) if le != "+Inf" else math.inf)
                    return (0, bucket_order)
                if suffix.endswith("_sum"):
                    return (1, 0)
                return (2, 0)
            for suffix, val, le in sorted(entries, key=_sort_key):
                if suffix.endswith("_bucket"):
                    lbls_ext = lbls + (("le", le),)
                else:
                    lbls_ext = lbls
                lines.append(f"{suffix}{_labels_to_str(lbls_ext)} {_fmt_val(val)}")


def _fmt_val(v: float) -> str:
    if isinstance(v, float) and math.isnan(v):
        return "NaN"
    if isinstance(v, float) and math.isinf(v):
        return "+Inf" if v > 0 else "-Inf"
    # Prefer integer formatting when exact
    if isinstance(v, int) or (isinstance(v, float) and v == int(v)):
        return f"{int(v)}"
    return f"{v}"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _now() -> float:
    """Best-effort wall-clock time in seconds."""
    return time.time()


def get_registry() -> Registry:
    return Registry.instance()


# ---------------------------------------------------------------------------
# Built-in metrics — import-time registration against the singleton registry
# ---------------------------------------------------------------------------

_reg = Registry.instance()

# --- Info / config (expose versions as a Gauge set to 1) ---
INFO_GAUGE: Gauge = _reg.register(Gauge(
    "edgy_info",
    "Static build/version labels. Value is always 1.",
    ("app_name", "app_version", "llm_model", "embedding_model", "vector_backend"),
))

# --- Detection ---
DETECTIONS_TOTAL: Counter = _reg.register(Counter(
    "edgy_detections_total",
    "Number of detection runs completed.",
    ("detector_id", "label"),
))
DETECTION_LATENCY_MS: Histogram = _reg.register(Histogram(
    "edgy_detection_latency_ms",
    "Single-flow detection latency in milliseconds.",
    ("detector_id",),
))
EVENTS_SEEDED_TOTAL: Counter = _reg.register(Counter(
    "edgy_events_seeded_total",
    "Number of SecurityEvents ingested from offline datasets.",
    ("detector_id",),
))

# --- Retrieval ---
RETRIEVAL_CALLS_TOTAL: Counter = _reg.register(Counter(
    "edgy_retrieval_calls_total",
    "Number of retrieval calls (BM25 / vec / hybrid).",
    ("mode", "backend"),
))
RETRIEVAL_LATENCY_MS: Histogram = _reg.register(Histogram(
    "edgy_retrieval_latency_ms",
    "Retrieval latency (BM25+vec + RRF) in milliseconds.",
    ("mode", "backend"),
))
RETRIEVAL_HITS_PER_QUERY: Histogram = _reg.register(Histogram(
    "edgy_retrieval_hits_per_query",
    "Number of hits returned per retrieval request.",
    ("mode",),
    buckets=(0, 1, 2, 3, 5, 10, 20, 50, 100, math.inf),
))

# --- RAG ---
RAG_RUNS_TOTAL: Counter = _reg.register(Counter(
    "edgy_rag_runs_total",
    "Number of complete RAG pipelines run.",
    ("llm_provider", "is_mock", "retrieval_status"),
))
RAG_TOTAL_LATENCY_MS: Histogram = _reg.register(Histogram(
    "edgy_rag_total_latency_ms",
    "End-to-end RAG latency (retrieval + prompt build + LLM call) in ms.",
    ("llm_provider", "is_mock"),
))
RAG_LLM_LATENCY_MS: Histogram = _reg.register(Histogram(
    "edgy_rag_llm_latency_ms",
    "LLM call latency only (does NOT include retrieval).",
    ("llm_provider", "is_mock"),
))
RAG_EVIDENCE_COUNT: Histogram = _reg.register(Histogram(
    "edgy_rag_evidence_count",
    "Number of evidence chunks attached to a RAG-generated policy.",
    (),
    buckets=(0, 1, 2, 3, 5, 10, 20, math.inf),
))

# --- Policy validation ---
POLICY_VALIDATIONS_TOTAL: Counter = _reg.register(Counter(
    "edgy_policy_validations_total",
    "Deterministic policy validation runs.",
    ("is_valid",),
))

# --- Executor ---
EXECUTIONS_TOTAL: Counter = _reg.register(Counter(
    "edgy_executions_total",
    "Policy executions attempted (dry-run or real).",
    ("mode", "action_type", "status"),
))
EXECUTION_LATENCY_MS: Histogram = _reg.register(Histogram(
    "edgy_execution_latency_ms",
    "Time spent inside Executor.execute() including dry-run echo.",
    ("mode", "action_type"),
))
EXECUTIONS_INFLIGHT: Gauge = _reg.register(Gauge(
    "edgy_executions_inflight",
    "Number of Executor.execute() calls currently running.",
    ("mode",),
))

# --- Knowledge base ---
KNOWLEDGE_CHUNKS_TOTAL: Gauge = _reg.register(Gauge(
    "edgy_knowledge_chunks_total",
    "Number of knowledge chunks currently indexed.",
    ("backend",),
))
KNOWLEDGE_DOCUMENTS_TOTAL: Gauge = _reg.register(Gauge(
    "edgy_knowledge_documents_total",
    "Number of knowledge source documents currently indexed.",
    ("backend",),
))

# --- Optional system metrics (unavailable when psutil is missing) ---
PROCESS_CPU_PERCENT: Gauge = _reg.register(Gauge(
    "edgy_process_cpu_percent",
    "Process CPU percentage — unavailable when psutil not installed.",
    (),
))
PROCESS_RSS_BYTES: Gauge = _reg.register(Gauge(
    "edgy_process_rss_bytes",
    "Process resident memory (bytes) — unavailable when psutil not installed.",
    (),
))
