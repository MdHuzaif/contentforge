"""SQLite-based thread and persistence manager following the Repuragent pattern."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

import aiosqlite

from app.config import SHORTTERM_MEMORY_DIR, SQLITE_DB_PATH, logger

THREAD_IDS_FILE = SHORTTERM_MEMORY_DIR / "thread_ids.json"


def load_thread_ids() -> List[Dict[str, Any]]:
    """Load thread IDs and metadata from thread_ids.json."""
    if not THREAD_IDS_FILE.exists():
        return []
    try:
        content = THREAD_IDS_FILE.read_text(encoding="utf-8")
        data = json.loads(content)
        if isinstance(data, list):
            return data
    except Exception as e:
        logger.error("Error reading thread IDs file: %s", e)
    return []


def save_thread_ids(thread_ids: List[Dict[str, Any]]) -> None:
    """Save thread IDs and metadata to thread_ids.json."""
    try:
        SHORTTERM_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        THREAD_IDS_FILE.write_text(
            json.dumps(thread_ids, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:
        logger.error("Error saving thread IDs file: %s", e)


def generate_new_thread_id() -> str:
    """Generate a new UUID4 thread identifier."""
    return str(uuid.uuid4())


def add_thread_id(thread_id: str, title: Optional[str] = None) -> None:
    """Add a new thread ID with created_at timestamp to thread_ids.json."""
    threads = load_thread_ids()
    # Check if already exists
    if any(t.get("thread_id") == thread_id for t in threads):
        return

    title = title or f"Thread {thread_id[:8]}"
    now = datetime.utcnow().isoformat()
    threads.insert(
        0,
        {
            "thread_id": thread_id,
            "title": title,
            "created_at": now,
        },
    )
    save_thread_ids(threads)


def remove_thread_id(thread_id: str) -> None:
    """Remove a thread ID from thread_ids.json."""
    threads = load_thread_ids()
    threads = [t for t in threads if t.get("thread_id") != thread_id]
    save_thread_ids(threads)


def update_thread_title(thread_id: str, new_title: str) -> None:
    """Update the title of an existing thread in thread_ids.json."""
    threads = load_thread_ids()
    updated = False
    for t in threads:
        if t.get("thread_id") == thread_id:
            t["title"] = new_title
            updated = True
            break
    if updated:
        save_thread_ids(threads)


class AsyncSQLiteManager:
    """Manages SQLite database connections and conversation persistence asynchronously."""

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        self.db_path = Path(db_path) if db_path else SQLITE_DB_PATH
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self) -> aiosqlite.Connection:
        """Create aiosqlite connection with WAL mode and busy_timeout."""
        if self.conn is not None:
            return self.conn

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(str(self.db_path))
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self.conn.execute("PRAGMA busy_timeout=5000;")
        await self.conn.commit()
        return self.conn

    async def close(self) -> None:
        """Close active database connection."""
        if self.conn is not None:
            await self.conn.close()
            self.conn = None

    async def initialize_tables(self) -> None:
        """Initialize database tables for conversations, checkpoints, and writes."""
        conn = await self.connect()
        try:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    thread_id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    execution_mode TEXT,
                    pipeline_status TEXT,
                    metadata TEXT
                )
                """
            )
            await conn.commit()
            logger.info("Database tables initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize database tables: %s", e)
            raise

    async def save_conversation(
        self,
        thread_id: str,
        title: str,
        execution_mode: str,
        pipeline_status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Save or update conversation record in SQLite."""
        conn = await self.connect()
        now = datetime.utcnow().isoformat()
        meta_json = json.dumps(metadata or {})

        try:
            async with conn.execute(
                """
                SELECT created_at FROM conversations WHERE thread_id = ?
                """,
                (thread_id,),
            ) as cursor:
                row = await cursor.fetchone()

            created_at = row[0] if row else now

            await conn.execute(
                """
                INSERT OR REPLACE INTO conversations
                (thread_id, title, created_at, updated_at, execution_mode, pipeline_status, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (thread_id, title, created_at, now, execution_mode, pipeline_status, meta_json),
            )
            await conn.commit()

            # Ensure tracked in thread_ids.json
            add_thread_id(thread_id, title)
        except Exception as e:
            logger.error("Error saving conversation %s: %s", thread_id, e)
            raise

    async def load_conversation(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Load conversation details by thread_id."""
        conn = await self.connect()
        try:
            async with conn.execute(
                """
                SELECT thread_id, title, created_at, updated_at, execution_mode, pipeline_status, metadata
                FROM conversations WHERE thread_id = ?
                """,
                (thread_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return {
                    "thread_id": row[0],
                    "title": row[1],
                    "created_at": row[2],
                    "updated_at": row[3],
                    "execution_mode": row[4],
                    "pipeline_status": row[5],
                    "metadata": json.loads(row[6]) if row[6] else {},
                }
        except Exception as e:
            logger.error("Error loading conversation %s: %s", thread_id, e)
            return None

    async def list_conversations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent conversations ordered by updated_at DESC."""
        conn = await self.connect()
        try:
            async with conn.execute(
                """
                SELECT thread_id, title, created_at, updated_at, execution_mode, pipeline_status, metadata
                FROM conversations ORDER BY updated_at DESC LIMIT ?
                """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                results = []
                for row in rows:
                    results.append(
                        {
                            "thread_id": row[0],
                            "title": row[1],
                            "created_at": row[2],
                            "updated_at": row[3],
                            "execution_mode": row[4],
                            "pipeline_status": row[5],
                            "metadata": json.loads(row[6]) if row[6] else {},
                        }
                    )
                return results
        except Exception as e:
            logger.error("Error listing conversations: %s", e)
            return []

    async def delete_conversation(self, thread_id: str) -> bool:
        """Delete conversation from SQLite tables and thread_ids.json."""
        conn = await self.connect()
        try:
            await conn.execute("DELETE FROM conversations WHERE thread_id = ?", (thread_id,))
            # Also check if langgraph checkpoint tables exist and delete if present
            for tbl in ["checkpoints", "writes", "checkpoint_blobs", "checkpoint_writes"]:
                try:
                    await conn.execute(f"DELETE FROM {tbl} WHERE thread_id = ?", (thread_id,))
                except Exception:
                    pass
            await conn.commit()
            remove_thread_id(thread_id)
            logger.info("Deleted conversation %s successfully.", thread_id)
            return True
        except Exception as e:
            logger.error("Error deleting conversation %s: %s", thread_id, e)
            return False


async def create_async_checkpointer() -> Tuple[Any, Optional[aiosqlite.Connection]]:
    """Create AsyncSqliteSaver checkpointer, falling back to MemorySaver on error."""
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        conn = await aiosqlite.connect(str(SQLITE_DB_PATH))
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA busy_timeout=5000;")
        checkpointer = AsyncSqliteSaver(conn)
        await checkpointer.setup()
        logger.info("AsyncSqliteSaver checkpointer initialized successfully.")
        return checkpointer, conn
    except Exception as e:
        logger.warning(
            "Could not initialize AsyncSqliteSaver (%s). Falling back to MemorySaver.", e
        )
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver(), None
