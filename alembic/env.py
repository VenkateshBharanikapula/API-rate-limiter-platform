"""
Alembic environment script.

Notes:
  - Migrations run with the SYNC driver (psycopg2), not asyncpg. Alembic's
    autogenerate machinery doesn't play well inside an async context, so we
    deliberately use a separate sync URL (DATABASE_URL_SYNC) just for this.
  - The DB URL and target metadata are pulled from the app itself
    (app.core.config, app.db.base) rather than duplicated here, so model
    changes are always picked up automatically by `alembic revision --autogenerate`.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base

# Import all models here so they're registered on Base.metadata before
# autogenerate compares it against the live database schema.
from app.models import client, rate_limit, usage, audit_log  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL scripts without a live DB connection (`alembic upgrade --sql`)."""
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
    """Run migrations against a live DB connection (the normal case)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
