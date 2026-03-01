from __future__ import annotations

import json
import asyncio
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
import aiosqlite
from loguru import logger


class MemoryStore:
    """
    SQLite FTS5-based memory store for traditional full-text search.
    Stores conversation history and facts for retrieval.
    """
    
    def __init__(self, db_path: str = "tj_agent_memory.db") -> None:
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
    
    async def initialize(self) -> None:
        """Initialize the database and create tables."""
        logger.info(f"Initializing memory store: {self.db_path}")
        
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        
        await self._create_tables()
        
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
        """
        Add a memory entry.
        
        Args:
            id: Unique identifier
            session_id: Session this memory belongs to
            category: Category (e.g., 'conversation', 'fact', 'skill')
            content: Text content to index
            metadata: Additional metadata (stored as JSON)
        
        Returns:
            True if successful
        """
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
        """
        Search memories using FTS5.
        
        Args:
            query: Search query (keywords)
            session_id: Optional filter by session
            category: Optional filter by category
            limit: Maximum results
        
        Returns:
            List of matching memories
        """
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
        try:
            cursor = await self._conn.execute(
                """SELECT id, session_id, category, content, metadata, timestamp
                   FROM memory
                   WHERE session_id = ? AND category = 'conversation'
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (session_id, limit)
            )
            rows = await cursor.fetchall()
            
            return [
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "category": row["category"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "timestamp": row["timestamp"]
                }
                for row in rows
            ]
        except Exception as e:
            logger.exception(f"Failed to get session history: {session_id}")
            return []
    
    async def close(self) -> None:
        """Close the database connection."""
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
    async def close(cls) -> None:
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
