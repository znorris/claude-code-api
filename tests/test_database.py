import pytest
import tempfile
import os
import pytest_asyncio
from src.database import DatabaseManager, SessionService

@pytest_asyncio.fixture
async def db_manager():
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        db_path = tmp.name
    
    manager = DatabaseManager(db_path)
    await manager.init_db()
    yield manager
    
    os.unlink(db_path)

@pytest_asyncio.fixture
async def session_service(db_manager):
    return SessionService(db_manager)

@pytest.mark.asyncio
async def test_database_initialization(db_manager):
    async with db_manager.get_db() as db:
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in await cursor.fetchall()]
        assert "sessions" in tables
        assert "messages" in tables

@pytest.mark.asyncio
async def test_session_creation(session_service):
    session_id = await session_service.create_session()
    assert session_id is not None
    assert len(session_id) == 36  # UUID format

@pytest.mark.asyncio
async def test_session_exists(session_service):
    session_id = await session_service.create_session()
    assert await session_service.session_exists(session_id) is True
    assert await session_service.session_exists("nonexistent") is False

@pytest.mark.asyncio
async def test_message_operations(session_service):
    session_id = await session_service.create_session()
    
    await session_service.add_message(session_id, "user", "Hello")
    await session_service.add_message(session_id, "assistant", "Hi there!")
    
    messages = await session_service.get_session_messages(session_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hi there!"