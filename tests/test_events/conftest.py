"""Shared pytest fixtures for event tests — isolated in-memory SQLite."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base


@pytest.fixture()
async def event_session() -> AsyncSession:
    """Fresh in-memory SQLite session. Each test gets its own transaction."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    session = factory()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()
