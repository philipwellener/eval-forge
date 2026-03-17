import asyncio
import os
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Use SQLite for tests (no Postgres dependency)
TEST_DB_URL = "sqlite+aiosqlite:///test.db"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    from api.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    # Clean up test db file
    if os.path.exists("test.db"):
        os.remove("test.db")


@pytest.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
def mock_queue():
    queue = AsyncMock()
    queue.ping = AsyncMock(return_value=True)
    queue.publish = AsyncMock()
    queue.stream_length = AsyncMock(return_value=0)
    queue.connect = AsyncMock()
    queue.close = AsyncMock()
    return queue


@pytest.fixture
async def client(db_engine, mock_queue):
    from api.database import get_db
    from api.main import app

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # Mock the queue
    import api.services.queue as queue_module

    original_queue = queue_module.job_queue
    queue_module.job_queue = mock_queue

    # Also patch the imported reference in routes
    import api.routes.evaluations as eval_routes
    import api.routes.health as health_routes

    eval_routes.job_queue = mock_queue
    health_routes.job_queue = mock_queue

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    queue_module.job_queue = original_queue
