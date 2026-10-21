"""Offline data ingestion service.

Reads raw CSV / JSONL files and converts each row into a FlowRecord.

Field mapping is explicit — the ingestion layer does NOT guess column names.
If the raw column names differ from FlowRecord field names, pass a mapping.
This matches the "no silent data loss" principle from the task book.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from app.adapters.dataset.csv_adapter import RawRows, read_any
from app.core.errors import AppError, ErrorCode
from app.domain.common import Protocol
from app.domain.flow import FlowRecord


@dataclass
class IngestionSummary:
    source_path: str
    total_rows: int
    imported: int
    failed: int
    errors: List[str]


# ---- Default mapping from our synthetic CSV -------------------------------
DEFAULT_FIELD_MAP: Dict[str, str] = {
    # FlowRecord field  -> raw CSV column
    "src_ip":                "src_ip",
    "dst_ip":                "dst_ip",
    "src_port":              "src_port",
    "dst_port":              "dst_port",
    "protocol":              "protocol",
    "duration_ms":           "duration_ms",
    "packets_src_to_dst":    "packets_src_to_dst",
    "packets_dst_to_src":    "packets_dst_to_src",
    "bytes_src_to_dst":      "bytes_src_to_dst",
    "bytes_dst_to_src":      "bytes_dst_to_src",
}

# Feature column prefix — columns in the CSV named `feat_*` or matching
# the known list below are treated as numeric features and collected into
# FlowRecord.features.
KNOWN_FEATURE_COLS = {
    "pkt_rate", "byte_rate", "pkt_ratio", "avg_pkt_size",
    "dst_port_common", "is_short", "byte_pkt_ratio",
}


def _protocol_coerce(value: Any) -> Protocol:
    """Normalise protocol strings into the Protocol enum."""
    if isinstance(value, Protocol):
        return value
    s = str(value or "").strip().upper()
    try:
        return Protocol(s)
    except ValueError:
        # Heuristic fallback
        if s.startswith("TCP"):
            return Protocol.TCP
        if s.startswith("UDP"):
            return Protocol.UDP
        if s.startswith("ICMP"):
            return Protocol.ICMP
        return Protocol.OTHER


def import_file(
    path: str | Path,
    *,
    field_map: Optional[Dict[str, str]] = None,
    feature_cols: Optional[List[str]] = None,
    dataset_id: Optional[str] = None,
) -> IngestionSummary:
    """Read a file, validate each row, emit FlowRecords into the DB (Phase 3).

    Phase 2 scope: we don't write to the DB yet — we just parse and report.
    The caller can iterate over `yield_records()` if they want the objects.
    """
    raw: RawRows = read_any(path)
    fm = field_map or DEFAULT_FIELD_MAP
    fcols = feature_cols or list(KNOWN_FEATURE_COLS)

    ok = 0
    fail = 0
    errors: List[str] = []
    for i, row in enumerate(raw.rows, start=1):
        try:
            _row_to_flow(row, fm, fcols, dataset_id=dataset_id or Path(path).name)
            ok += 1
        except Exception as e:
            fail += 1
            errors.append(f"row {i}: {type(e).__name__}: {e}")

    return IngestionSummary(
        source_path=raw.source_path,
        total_rows=raw.total_records,
        imported=ok,
        failed=fail,
        errors=errors[:50],  # cap to avoid flooding logs
    )


def _row_to_flow(
    row: Dict[str, Any],
    field_map: Dict[str, str],
    feature_cols: List[str],
    *,
    dataset_id: str,
) -> FlowRecord:
    """Convert one raw row → FlowRecord. Raises on missing required fields."""
    missing = [target for target, source in field_map.items() if row.get(source) in (None, "")]
    if missing:
        raise ValueError(f"missing fields: {missing}")

    base = {target: row[source] for target, source in field_map.items()}
    base["protocol"] = _protocol_coerce(base["protocol"])

    features: Dict[str, float] = {}
    for col in feature_cols:
        v = row.get(col)
        if v is None or v == "":
            continue
        try:
            features[col] = float(v)
        except (TypeError, ValueError):
            # Non-numeric feature → skip silently and let downstream decide
            continue

    base["features"] = features
    base["dataset_id"] = dataset_id
    base["source_ref"] = dataset_id
    # feature_schema_version is fixed at "v1" in Phase 2
    base["feature_schema_version"] = "v1"

    return FlowRecord(**base)


def iter_records(
    path: str | Path,
    *,
    field_map: Optional[Dict[str, str]] = None,
    feature_cols: Optional[List[str]] = None,
    dataset_id: Optional[str] = None,
) -> Iterable[FlowRecord]:
    """Lazily yield FlowRecords from a file (skips bad rows silently)."""
    raw: RawRows = read_any(path)
    fm = field_map or DEFAULT_FIELD_MAP
    fcols = feature_cols or list(KNOWN_FEATURE_COLS)
    for row in raw.rows:
        try:
            yield _row_to_flow(row, fm, fcols, dataset_id=dataset_id or Path(path).name)
        except Exception:
            continue
