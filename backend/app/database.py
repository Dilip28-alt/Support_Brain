"""
Database configuration — SQLAlchemy async engine + pgvector.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

# Convert standard postgres:// to postgresql+asyncpg://
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql://") or _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    _db_url,
    echo=False,          # set True for SQL debug logs
    pool_pre_ping=True,
    poolclass=NullPool,  # Supabase pooler compatibility across async loops
    connect_args={"statement_cache_size": 0},  # Supabase pooler (pgbouncer) compatibility
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields an async db session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Enable pgvector extension (idempotent) and ensure tables/columns exist."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.execute(text("""
            ALTER TABLE email_messages 
            ADD COLUMN IF NOT EXISTS related_message_id UUID REFERENCES email_messages(id) ON DELETE SET NULL;
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_email_messages_related_message_id ON email_messages (related_message_id);
        """))
        try:
            await conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_email_reply_outgoing 
                ON email_messages (related_message_id) 
                WHERE direction = 'outgoing';
            """))
        except Exception:
            pass
        logger.info("✅ Database schema verified.")
