from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
from uuid import uuid4
import aiosqlite
from loguru import logger


class SessionManager:
    """Manages chat sessions and messages."""
    
    def __init__(self, db_path: str = "tj_agent_memory.db") -> None:
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
    
    async def initialize(self) -> None:
        """Initialize the database connection."""
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._create_session_tables()
        logger.info("Session manager initialized")
    
    async def _create_session_tables(self) -> None:
        """Create sessions and messages tables."""
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                tool_calls TEXT,
                tool_results TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        
        await self._conn.commit()
    
    async def create_session(self, agent_id: str, title: Optional[str] = None) -> str:
        """Create a new session."""
        session_id = str(uuid4())
        title = title or "新会话"
        
        await self._conn.execute(
            "INSERT INTO sessions (id, agent_id, title) VALUES (?, ?, ?)",
            (session_id, agent_id, title)
        )
        await self._conn.commit()
        
        logger.debug(f"Created session: {session_id}")
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """Get session by ID."""
        cursor = await self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            return None
        
        return {
            "id": row["id"],
            "agent_id": row["agent_id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    
    async def list_sessions(self, agent_id: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
        """List all sessions, optionally filtered by agent_id."""
        if agent_id:
            cursor = await self._conn.execute(
                """SELECT * FROM sessions WHERE agent_id = ? 
                   ORDER BY updated_at DESC LIMIT ?""",
                (agent_id, limit)
            )
        else:
            cursor = await self._conn.execute(
                """SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?""",
                (limit,)
            )
        
        rows = await cursor.fetchall()
        
        return [
            {
                "id": row["id"],
                "agent_id": row["agent_id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
            for row in rows
        ]
    
    async def update_session_title(self, session_id: str, title: str) -> bool:
        """Update session title."""
        await self._conn.execute(
            "UPDATE sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, session_id)
        )
        await self._conn.commit()
        return True
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: Optional[list[dict[str, Any]]] = None,
        tool_results: Optional[list[dict[str, Any]]] = None
    ) -> str:
        """Add a message to a session."""
        message_id = str(uuid4())
        
        await self._conn.execute(
            """INSERT INTO messages (id, session_id, role, content, tool_calls, tool_results)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                message_id,
                session_id,
                role,
                content,
                json.dumps(tool_calls) if tool_calls else None,
                json.dumps(tool_results) if tool_results else None
            )
        )
        
        await self._conn.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,)
        )
        
        await self._conn.commit()
        return message_id
    
    async def get_messages(self, session_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get all messages for a session."""
        cursor = await self._conn.execute(
            """SELECT * FROM messages WHERE session_id = ? 
               ORDER BY created_at ASC LIMIT ?""",
            (session_id, limit)
        )
        
        rows = await cursor.fetchall()
        
        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "role": row["role"],
                "content": row["content"],
                "tool_calls": json.loads(row["tool_calls"]) if row["tool_calls"] else None,
                "tool_results": json.loads(row["tool_results"]) if row["tool_results"] else None,
                "created_at": row["created_at"]
            }
            for row in rows
        ]
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages."""
        await self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await self._conn.commit()
        return True
    
    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()


class MemoryStore:
    """
    SQLite FTS5-based memory store for traditional full-text search.
    Stores conversation history and facts for retrieval.
    """
    
    def __init__(self, db_path: str = "tj_agent_memory.db") -> None:
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self.session_manager = SessionManager(db_path)
    
    async def initialize(self) -> None:
        """Initialize the database and create tables."""
        logger.info(f"Initializing memory store: {self.db_path}")
        
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        
        await self._create_tables()
        await self.session_manager.initialize()
        
        logger.info("Memory store initialized")
    
    async def _create_tables(self) -> None:
        """Create FTS5 virtual tables."""
        await self._conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory USING fts5(
                id UNINDEXED,
                session_id,
                category,
                content,
                metadata,
                timestamp
            )
        """)
        
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_meta (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self._conn.commit()
    
    async def add(
        self,
        id: str,
        session_id: str,
        category: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None
    ) -> bool:
        """Add a memory entry."""
        try:
            await self._conn.execute(
                """INSERT INTO memory (id, session_id, category, content, metadata, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (id, session_id, category, content, json.dumps(metadata or {}), datetime.utcnow().isoformat())
            )
            await self._conn.commit()
            return True
        except Exception as e:
            logger.exception(f"Failed to add memory: {id}")
            return False
    
    async def search(
        self,
        query: str,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 5
    ) -> list[dict[str, Any]]:
        """Search memories using FTS5."""
        try:
            sql = """
                SELECT id, session_id, category, content, metadata, timestamp,
                       bm25(memory) as rank
                FROM memory
                WHERE memory MATCH ?
            """
            params: list[Any] = [query]
            
            if session_id:
                sql += " AND session_id = ?"
                params.append(session_id)
            
            if category:
                sql += " AND category = ?"
                params.append(category)
            
            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)
            
            cursor = await self._conn.execute(sql, params)
            rows = await cursor.fetchall()
            
            return [
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "category": row["category"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "timestamp": row["timestamp"],
                    "rank": row["rank"]
                }
                for row in rows
            ]
        except Exception as e:
            logger.exception(f"Search failed: {query}")
            return []
    
    async def get_session_history(
        self,
        session_id: str,
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """Get conversation history for a session."""
        return await self.session_manager.get_messages(session_id, limit)
    
    async def close(self) -> None:
        """Close the database connection."""
        await self.session_manager.close()
        if self._conn:
            await self._conn.close()
            logger.info("Memory store closed")


class MemoryManager:
    """Singleton manager for memory store."""
    
    _instance: Optional[MemoryStore] = None
    
    @classmethod
    async def get_instance(cls, db_path: str = "tj_agent_memory.db") -> MemoryStore:
        if cls._instance is None:
            cls._instance = MemoryStore(db_path)
            await cls._instance.initialize()
        return cls._instance
    
    @classmethod
    async def get_session_manager(cls) -> SessionManager:
        """Get the session manager."""
        store = await cls.get_instance()
        return store.session_manager
    
    @classmethod
    async def close(cls) -> None:
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
