import aiosqlite
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

try:
    from .models.openai import ChatMessage
except ImportError:
    from models.openai import ChatMessage

DATABASE_PATH = "sessions.db"

class DatabaseManager:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
    
    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    claude_session_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)
            """)
            
            await db.commit()
    
    @asynccontextmanager
    async def get_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db

class SessionService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    async def create_session(self, expires_hours: int = 24) -> str:
        session_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(hours=expires_hours)
        
        async with self.db_manager.get_db() as db:
            await db.execute(
                "INSERT INTO sessions (id, expires_at) VALUES (?, ?)",
                (session_id, expires_at.isoformat())
            )
            await db.commit()
        
        return session_id
    
    async def get_session_messages(self, session_id: str) -> List[ChatMessage]:
        async with self.db_manager.get_db() as db:
            await db.execute(
                "UPDATE sessions SET last_accessed = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,)
            )
            
            cursor = await db.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp",
                (session_id,)
            )
            rows = await cursor.fetchall()
            await db.commit()
            
            return [ChatMessage(role=row["role"], content=row["content"]) for row in rows]
    
    async def add_message(self, session_id: str, role: str, content: str):
        async with self.db_manager.get_db() as db:
            await db.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content)
            )
            await db.commit()
    
    async def session_exists(self, session_id: str) -> bool:
        async with self.db_manager.get_db() as db:
            cursor = await db.execute(
                "SELECT 1 FROM sessions WHERE id = ? AND expires_at > CURRENT_TIMESTAMP",
                (session_id,)
            )
            row = await cursor.fetchone()
            return row is not None
    
    async def cleanup_expired_sessions(self) -> int:
        async with self.db_manager.get_db() as db:
            cursor = await db.execute(
                "DELETE FROM sessions WHERE expires_at <= CURRENT_TIMESTAMP"
            )
            await db.commit()
            return cursor.rowcount
    
    async def get_claude_session_id(self, session_id: str) -> Optional[str]:
        """Get Claude CLI session ID for our session."""
        async with self.db_manager.get_db() as db:
            cursor = await db.execute(
                "SELECT claude_session_id FROM sessions WHERE id = ?",
                (session_id,)
            )
            row = await cursor.fetchone()
            return row["claude_session_id"] if row else None
    
    async def set_claude_session_id(self, session_id: str, claude_session_id: str):
        """Store Claude CLI session ID for our session."""
        async with self.db_manager.get_db() as db:
            await db.execute(
                "UPDATE sessions SET claude_session_id = ? WHERE id = ?",
                (claude_session_id, session_id)
            )
            await db.commit()

db_manager = DatabaseManager()
session_service = SessionService(db_manager)