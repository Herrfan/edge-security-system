"""Dataset adapters — read raw data files into intermediate dicts.

We intentionally use the standard-library csv module here instead of polars
because the local polars binary is broken and we want to keep Phase 2
zero-extra-dependency. If pandas or polars becomes available later, swap
the adapter implementation — the ingestion service above only sees dicts.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class RawRows:
    """Parsed dataset before field mapping."""
    rows: List[Dict[str, Any]]
    source_path: str
    total_records: int
    total_valid: int
    warnings: List[str]


def read_csv(path: str | Path, *, encoding: str = "utf-8-sig") -> RawRows:
    """Parse a CSV file. Missing numeric fields become None (not dropped)."""
    p = Path(path)
    rows: List[Dict[str, Any]] = []
    warnings: List[str] = []
    with p.open("r", encoding=encoding, newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"CSV {p} has no header")
        for lineno, raw in enumerate(reader, start=2):
            # Convert obvious numbers; leave everything else as str
            cleaned: Dict[str, Any] = {}
            for k, v in raw.items():
                if v is None or v == "":
                    cleaned[k] = None
                    continue
                try:
                    if "." in v:
                        cleaned[k] = float(v)
                    else:
                        cleaned[k] = int(v)
                except ValueError:
                    cleaned[k] = v  # keep as-is; validation happens upstream
            rows.append(cleaned)

    return RawRows(
        rows=rows,
        source_path=str(p),
        total_records=len(rows),
        total_valid=len(rows),
        warnings=warnings,
    )


def read_jsonl(path: str | Path) -> RawRows:
    """Parse a JSON-lines file (one JSON object per line)."""
    p = Path(path)
    rows: List[Dict[str, Any]] = []
    warnings: List[str] = []
    total = 0
    with p.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            total += 1
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                warnings.append(f"line {lineno}: JSON error {e}")
    return RawRows(
        rows=rows,
        source_path=str(p),
        total_records=total,
        total_valid=len(rows),
        warnings=warnings,
    )


def read_any(path: str | Path) -> RawRows:
    """Auto-detect by extension."""
    ext = Path(path).suffix.lower()
    if ext == ".csv":
        return read_csv(path)
    if ext in (".jsonl", ".json"):
        # .json is usually an array; handle both cases
        text = Path(path).read_text(encoding="utf-8").strip()
        if text.startswith("["):
            data = json.loads(text)
            if not isinstance(data, list):
                raise ValueError(".json file must contain a top-level array")
            return RawRows(
                rows=list(data),
                source_path=str(path),
                total_records=len(data),
                total_valid=len(data),
                warnings=[],
            )
        return read_jsonl(path)
    raise ValueError(f"Unsupported file extension: {ext}")
