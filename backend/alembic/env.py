"""Alembic env.py — async SQLAlchemy with asyncpg."""
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base
from app.models import models   # noqa — import all models to populate metadata
from app.config import get_settings

config = context.config
fileConfig(config.config_file_name)

settings = get_settings()
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)

# NOTE: we intentionally do NOT call config.set_main_option() here.
# alembic.ini uses ConfigParser, which treats "%" as interpolation syntax and
# crashes on URL-encoded passwords (e.g. "%40", "%25"). We pass the URL
# directly to the engine instead.
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = create_async_engine(
        db_url,
        poolclass=pool.NullPool,
        connect_args={"statement_cache_size": 0},  # Supabase pooler compatibility
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online():
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
