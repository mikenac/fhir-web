"""Alembic environment configuration for DuckDB migrations."""

from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy import engine_from_config

from alembic import context
from alembic.ddl.impl import DefaultImpl

from app.config import get_settings
from app.db.models import Base


# Register DuckDB as using the default Alembic DDL implementation.
# DuckDB's SQL is close enough to standard SQL that the default impl works.
class DuckDBImpl(DefaultImpl):
    __dialect__ = "duckdb"

# Alembic Config object
config = context.config

# Set up Python logging from the .ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point Alembic at our ORM metadata for autogenerate support
target_metadata = Base.metadata

# Read the database URL from app settings (not alembic.ini)
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Ensure the DuckDB file directory exists
db_path = settings.database_url.replace("duckdb:///", "")
if db_path and db_path != ":memory:":
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without connecting)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with a sync engine."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
