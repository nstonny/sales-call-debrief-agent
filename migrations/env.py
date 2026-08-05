import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# --- Load our app config (reads DATABASE_URL from .env) ---
from debrief_agent.core.config import DATABASE_URL
from debrief_agent.core.database import Base

# --- Import models so they register themselves on Base.metadata ---
import debrief_agent.models  # noqa: F401

# Alembic Config object — access to values in alembic.ini
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata autogenerate will compare against
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode — generates SQL script without a live DB connection
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """
    Emit migration SQL to stdout instead of running it.
    Useful for reviewing what will change before applying.
    """
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — connects to the DB and runs migrations directly
# ---------------------------------------------------------------------------
def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Create an async engine, connect, and run migrations via run_sync
    (Alembic's migration runner is synchronous internally).
    """
    connectable = create_async_engine(DATABASE_URL, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
