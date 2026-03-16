"""Sync SQLAlchemy engine and session factory for DuckDB."""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

# Module-level engine and session factory, initialized at app startup.
_engine = None
_session_factory = None


def init_engine():
    """Create the sync engine and session factory from settings.

    Called once during app startup via the lifespan context manager.
    Ensures the data directory exists for file-based DuckDB.
    """
    global _engine, _session_factory

    settings = get_settings()

    # Ensure the directory for the DuckDB file exists
    # database_url format: duckdb:///path/to/file.duckdb
    db_path = settings.database_url.replace("duckdb:///", "")
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    _engine = create_engine(
        settings.database_url,
        echo=settings.debug,
    )

    _session_factory = sessionmaker(
        bind=_engine,
        class_=Session,
        expire_on_commit=False,
    )


def dispose_engine():
    """Dispose the engine, closing all connections.

    Called during app shutdown via the lifespan context manager.
    """
    global _engine
    if _engine:
        _engine.dispose()
        _engine = None


def get_engine():
    """Return the current engine (for Alembic or direct use)."""
    return _engine


def get_session_factory():
    """Return the current session factory."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_engine() first.")
    return _session_factory
