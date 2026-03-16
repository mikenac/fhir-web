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


def run_migrations() -> None:
    """Run Alembic migrations programmatically, upgrading the database to head.

    This is called at app startup so that the DuckDB tables always exist,
    even on a fresh Render deploy where the database file has just been created.

    Alembic is idempotent: if the database is already up to date, this is a no-op.

    DuckDB only allows a single writer connection at a time.  To avoid a
    deadlock we temporarily dispose the app engine (releasing its write lock),
    run the migration with Alembic's own short-lived engine, then reinitialize
    the app engine so it is ready to serve requests.
    """
    import os

    from alembic import command
    from alembic.config import Config

    global _engine, _session_factory

    # Resolve the backend/ directory regardless of where the process was
    # launched from.  __file__ is  backend/app/db/engine.py, so we go up
    # three levels: db/ -> app/ -> backend/
    backend_dir = os.path.dirname(  # backend/
        os.path.dirname(            # app/
            os.path.dirname(        # db/
                os.path.abspath(__file__)
            )
        )
    )

    import sys

    # Release the write lock so Alembic can open its own connection.
    print("run_migrations: disposing engine", flush=True, file=sys.stderr)
    if _engine is not None:
        _engine.dispose()
    print("run_migrations: engine disposed", flush=True, file=sys.stderr)

    # Point Alembic at the ini file and override script_location with an
    # absolute path so it works no matter what the working directory is.
    print("run_migrations: creating Config", flush=True, file=sys.stderr)
    alembic_cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    print("run_migrations: setting script_location", flush=True, file=sys.stderr)
    alembic_cfg.set_main_option(
        "script_location", os.path.join(backend_dir, "alembic")
    )

    # upgrade("head") applies every pending migration in order.
    print("run_migrations: calling command.upgrade", flush=True, file=sys.stderr)
    command.upgrade(alembic_cfg, "head")
    print("run_migrations: upgrade complete", flush=True, file=sys.stderr)

    # Reinitialize the app engine now that Alembic has finished and released
    # its connection.  _session_factory is recreated so it binds to the new
    # engine instance.
    print("run_migrations: reinitializing engine", flush=True, file=sys.stderr)
    settings = get_settings()
    _engine = create_engine(settings.database_url, echo=settings.debug)
    _session_factory = sessionmaker(
        bind=_engine,
        class_=Session,
        expire_on_commit=False,
    )
    print("run_migrations: done", flush=True, file=sys.stderr)
