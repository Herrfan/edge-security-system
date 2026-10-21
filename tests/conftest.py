"""Shared pytest fixtures.

The ``client`` fixture is a generator — using ``with TestClient(app) as c:``
ensures the FastAPI lifespan runs (init_db + mark_info_gauges). Session-scoped
so the DB + metrics registry are shared across tests for speed.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    """Session-scoped TestClient with lifespan active."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to repo root (d:\\edge security system)."""
    return Path(__file__).resolve().parent.parent
