from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def ensure_db_compat() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                ALTER TABLE user_profile
                ADD COLUMN IF NOT EXISTS procoins INT NOT NULL DEFAULT 50 CHECK (procoins >= 0)
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE user_profile
                ADD COLUMN IF NOT EXISTS achievements_json JSONB NOT NULL DEFAULT '{
                    "completed_courses": 0,
                    "unlocked": []
                }'::JSONB
                """
            )
        )
