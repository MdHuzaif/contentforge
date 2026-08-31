"""Token usage tracker and budgeting utility for ContentForge AI."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from app.config import SQLITE_DB_PATH, logger


class TokenTracker:
    """Tracks token usage across LLM providers and enforces monthly budgets."""

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        self.db_path = Path(db_path) if db_path else SQLITE_DB_PATH
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize SQLite tables for token usage and monthly budgets."""
        if self._initialized:
            return
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiosqlite.connect(str(self.db_path)) as db:
                await db.execute("PRAGMA journal_mode=WAL;")
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS token_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT,
                        provider TEXT,
                        model TEXT,
                        prompt_tokens INTEGER,
                        completion_tokens INTEGER,
                        total_tokens INTEGER,
                        timestamp REAL
                    )
                    """
                )
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS monthly_budget (
                        month TEXT PRIMARY KEY,
                        used_tokens INTEGER DEFAULT 0
                    )
                    """
                )
                await db.commit()
            self._initialized = True
            logger.info("TokenTracker tables initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize TokenTracker tables: %s", e)
            raise

    async def log_usage(
        self,
        task_id: Optional[str],
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Log token usage for an LLM call and update monthly budget totals."""
        total_tokens = prompt_tokens + completion_tokens
        timestamp = time.time()
        month = time.strftime("%Y-%m", time.localtime(timestamp))

        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                await db.execute(
                    """
                    INSERT INTO token_usage
                    (task_id, provider, model, prompt_tokens, completion_tokens, total_tokens, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id or "default",
                        provider,
                        model,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                        timestamp,
                    ),
                )
                await db.execute(
                    """
                    INSERT INTO monthly_budget (month, used_tokens)
                    VALUES (?, ?)
                    ON CONFLICT(month) DO UPDATE SET used_tokens = used_tokens + ?
                    """,
                    (month, total_tokens, total_tokens),
                )
                await db.commit()
            logger.info(
                "Logged %d tokens (%d prompt, %d completion) for provider '%s' (task: %s)",
                total_tokens,
                prompt_tokens,
                completion_tokens,
                provider,
                task_id,
            )
        except Exception as e:
            logger.error("Error logging token usage: %s", e)

    async def get_monthly_usage(self) -> int:
        """Return total tokens used in the current month."""
        month = time.strftime("%Y-%m")
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                async with db.execute(
                    "SELECT used_tokens FROM monthly_budget WHERE month = ?", (month,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return int(row[0])
            return 0
        except Exception as e:
            logger.error("Error retrieving monthly usage: %s", e)
            return 0

    async def check_budget(self, limit: int = 500000) -> bool:
        """Return True if current monthly usage is below the token limit."""
        usage = await self.get_monthly_usage()
        return usage < limit

    async def get_usage_summary(self) -> Dict[str, Any]:
        """Return summary of monthly usage, provider breakdown, and remaining budget."""
        month = time.strftime("%Y-%m")
        total_tokens = await self.get_monthly_usage()
        default_limit = 500000
        by_provider: Dict[str, int] = {}

        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                async with db.execute(
                    """
                    SELECT provider, SUM(total_tokens)
                    FROM token_usage
                    WHERE strftime('%Y-%m', datetime(timestamp, 'unixepoch')) = ?
                    GROUP BY provider
                    """,
                    (month,),
                ) as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        by_provider[row[0]] = int(row[1])
        except Exception as e:
            logger.error("Error generating usage summary: %s", e)

        remaining = max(0, default_limit - total_tokens)
        return {
            "month": month,
            "total_tokens": total_tokens,
            "by_provider": by_provider,
            "remaining_budget": remaining,
            "limit": default_limit,
        }

    async def reset_monthly(self) -> None:
        """Reset records for the current month (primarily for testing)."""
        month = time.strftime("%Y-%m")
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                await db.execute("DELETE FROM monthly_budget WHERE month = ?", (month,))
                await db.execute(
                    """
                    DELETE FROM token_usage
                    WHERE strftime('%Y-%m', datetime(timestamp, 'unixepoch')) = ?
                    """,
                    (month,),
                )
                await db.commit()
            logger.info("Reset usage records for month %s", month)
        except Exception as e:
            logger.error("Error resetting monthly usage: %s", e)


_tracker_instance: Optional[TokenTracker] = None


def get_token_tracker() -> TokenTracker:
    """Return the singleton instance of TokenTracker."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = TokenTracker()
    return _tracker_instance


async def estimate_tokens(text: str) -> int:
    """Estimate token count based on character length (~4 characters per token)."""
    if not text:
        return 1
    return max(1, len(text) // 4)
