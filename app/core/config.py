"""Application configuration.

All runtime knobs live here. Loaded from environment variables + .env file.
Only contains plumbing — no business rules.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All app configuration in one place."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "edge-security-system"
    app_version: str = "0.1.0"
    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_log_level: str = "INFO"

    # --- Database ---
    database_url: str = "sqlite:///./data/app.db"

    # --- LLM (Ollama) ---
    ollama_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen2.5:3b"
    llm_timeout_seconds: int = 60
    llm_provider: str = "ollama"  # ollama | mock

    # --- Embedding ---
    embedding_provider: str = "ollama"  # ollama | mock
    embedding_model: str = "nomic-embed-text"

    # --- Observability / auth ---
    auth_enabled: bool = False  # 默认关闭；生产部署时 True
    auth_jwt_secret: str = ""   # HMAC HS256 secret — 空字符串时 auth_enabled 必须 False
    auth_token_ttl_minutes: int = 60
    metrics_persist_enabled: bool = False  # 默认关闭；显式 True 才在 shutdown 自动 dump
    metrics_snapshot_interval_minutes: int = 0  # 后台定时快照（0 = 仅 shutdown，需 metrics_persist_enabled=True）
    vm_remote_write_url: str = ""  # 空 = 不推 VictoriaMetrics；填了就 shutdown 自动 push latest snapshot
    authorized_assets: List[str] = Field(
        default_factory=lambda: ["127.0.0.0/8"],
        description="CIDR ranges that are authorized for dry-run simulation only.",
    )
    allow_real_execution: bool = False  # MUST stay false in Phase 1-6
    default_execution_mode: str = "DRY_RUN"  # DRY_RUN | REAL

    # --- Retrieval ---
    retrieval_mode: str = "hybrid"  # keyword | vector | hybrid
    vector_backend: str = "sqlite_vec"
    vector_provider: str = "ollama"  # ollama | mock

    # --- Paths ---
    data_dir: Path = Field(default_factory=lambda: REPO_ROOT / "data")
    models_dir: Path = Field(default_factory=lambda: REPO_ROOT / "models")
    log_dir: Path = Field(default_factory=lambda: REPO_ROOT / "logs")
    knowledge_index_dir: Path = Field(
        default_factory=lambda: REPO_ROOT / "data" / "knowledge_index"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton Settings instance."""
    return Settings()
