"""Async database engine and session lifecycle."""

from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.db.base import Base


def _prepare_sqlite_directory(database_url: str) -> None:
    """Create the parent directory for file-backed SQLite databases."""
    prefix = "sqlite+aiosqlite:///"
    if database_url.startswith(prefix) and not database_url.endswith(":memory:"):
        Path(database_url.removeprefix(prefix)).parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_engine() -> AsyncEngine:
    """Create the process-wide asynchronous database engine."""
    settings = get_settings()
    _prepare_sqlite_directory(settings.database_url)
    return create_async_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide async session factory."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a database session for request dependencies."""
    async with get_session_factory()() as session:
        yield session


async def initialize_database() -> None:
    """Create tables for simple local development when explicitly enabled."""
    if not get_settings().database_auto_create:
        return
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def dispose_database() -> None:
    """Dispose the database engine on application shutdown."""
    await get_engine().dispose()
