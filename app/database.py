from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    from sqlalchemy import text

    from app.models import Song, Persona, Setting, Job  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight column migrations (create_all won't alter existing tables)
        existing = (await conn.execute(text("PRAGMA table_info(songs)"))).scalars().all()
        if "engine" not in existing:
            await conn.execute(text(
                "ALTER TABLE songs ADD COLUMN engine VARCHAR(32) DEFAULT 'acestep' NOT NULL"
            ))


async def get_db():
    async with async_session() as session:
        yield session
