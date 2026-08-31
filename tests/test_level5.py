"""Level 5 structural tests for the Interactive Session Layer."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.interactive import InteractiveSession, INTERRUPT_AFTER


def test_interrupt_points():
    assert INTERRUPT_AFTER == ["data_gathering", "subprompt_generator", "section_writer"]
    print("[OK] test_interrupt_points passed")


async def test_session_init_and_empty_state():
    session = InteractiveSession()
    await session.initialize()
    assert session.graph is not None

    snap = await session.get_state("unused_thread_level5")
    assert not snap["values"], "Fresh thread should have empty state"
    assert snap["next"] == ()

    await session.close()
    print("[OK] test_session_init_and_empty_state passed")


async def test_guard_raises_on_missing_session():
    session = InteractiveSession()
    await session.initialize()
    try:
        await session.generate_prompts("nonexistent_thread")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    await session.close()
    print("[OK] test_guard_raises_on_missing_session passed")


def main():
    test_interrupt_points()
    asyncio.run(test_session_init_and_empty_state())
    asyncio.run(test_guard_raises_on_missing_session())
    print("\nALL LEVEL 5 TESTS PASSED!")


if __name__ == "__main__":
    main()
