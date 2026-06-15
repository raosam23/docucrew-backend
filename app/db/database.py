from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlmodel import SQLModel

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"ssl": "require"}
)

async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
)

async def init_db():
    """Initialize the database."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_session():
    """Get a database session."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
