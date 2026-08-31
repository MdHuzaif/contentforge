"""Verification script for backend/memory/sqlite_manager.py."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    from backend.memory.sqlite_manager import (
        AsyncSQLiteManager,
        create_async_checkpointer,
        generate_new_thread_id,
        load_thread_ids,
        save_thread_ids,
    )

    tid = generate_new_thread_id()
    print("Generated thread ID:", tid)

    manager = AsyncSQLiteManager()
    await manager.initialize_tables()
    await manager.save_conversation(
        thread_id=tid,
        title="Test Conversation",
        execution_mode="autonomous",
        pipeline_status="running",
        metadata={"topic": "AI"},
    )

    conv = await manager.load_conversation(tid)
    assert conv is not None
    assert conv["title"] == "Test Conversation"
    print("Loaded conversation:", conv)

    convs = await manager.list_conversations()
    assert len(convs) > 0
    print(f"Total conversations listed: {len(convs)}")

    checkpointer, conn = await create_async_checkpointer()
    assert checkpointer is not None
    print("Checkpointer created successfully:", type(checkpointer))

    if conn:
        await conn.close()

    deleted = await manager.delete_conversation(tid)
    assert deleted is True
    await manager.close()

    print("[OK] backend/memory/sqlite_manager.py verified successfully!")


if __name__ == "__main__":
    asyncio.run(main())
