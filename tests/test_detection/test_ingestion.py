"""Ingestion tests — normal samples + bad rows."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.services.ingestion import import_file, iter_records


@pytest.fixture(scope="module")
def sample_csv() -> Path:
    """Re-run the generator so the test is self-contained."""
    import sys
    ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(ROOT))
    from scripts.generate_sample_data import generate
    return generate(n_per_class=300, seed=99)


class TestImportCSV:
    def test_import_summary(self, sample_csv):
        summary = import_file(sample_csv)
        assert summary.total_rows == 900
        assert summary.imported == 900
        assert summary.failed == 0

    def test_iter_records(self, sample_csv):
        flows = list(iter_records(sample_csv))
        assert len(flows) == 900
        # A flow from our CSV has features populated
        has_features = sum(1 for f in flows if f.features)
        assert has_features > 0


@pytest.fixture
def bad_csv(tmp_path) -> Path:
    """A CSV with missing / malformed rows mixed in."""
    p = tmp_path / "bad.csv"
    with p.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([
            "src_ip", "dst_ip", "src_port", "dst_port", "protocol",
            "duration_ms", "packets_src_to_dst", "packets_dst_to_src",
            "bytes_src_to_dst", "bytes_dst_to_src",
        ])
        # good
        w.writerow(["10.0.0.1", "10.0.0.2", "5000", "80", "TCP", "100", "10", "8", "500", "300"])
        # missing dst_port
        w.writerow(["10.0.0.1", "10.0.0.2", "5000", "", "TCP", "100", "10", "8", "500", "300"])
        # negative port (will fail FlowRecord validation)
        w.writerow(["10.0.0.1", "10.0.0.2", "5000", "-1", "TCP", "100", "10", "8", "500", "300"])
        # good
        w.writerow(["10.0.0.1", "10.0.0.2", "5001", "443", "tcp", "200", "20", "15", "1000", "900"])
    return p


class TestImportBadCSV:
    def test_failed_rows_counted(self, bad_csv):
        summary = import_file(bad_csv)
        assert summary.total_rows == 4
        assert summary.imported == 2
        assert summary.failed == 2
        assert len(summary.errors) >= 2
