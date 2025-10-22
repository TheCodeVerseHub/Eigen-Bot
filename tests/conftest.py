import asyncio
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


@pytest_asyncio.fixture()
async def session():
    """Provide an AsyncSession connected to an in-memory SQLite database for tests."""
    # Use SQLite in-memory async engine for tests
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        # Create all tables from models' metadata
        from models import Base
        await conn.run_sync(Base.metadata.create_all)

    # Use an async context manager to yield an AsyncSession instance
    # pyright/mypy may not recognize the runtime AsyncSession context manager returned
    # by sessionmaker, so we use async with and ignore type-checker warnings here.
    async with async_session() as sess:  # type: ignore
        yield sess

    await engine.dispose()
