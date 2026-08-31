"""Minimal real run of the interactive flow (5 Gemini calls, safe under 15/min)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.interactive import InteractiveSession


async def main():
    session = InteractiveSession()
    await session.initialize()

    # Phase 1 (2 Gemini calls)
    r1 = await session.start_research("best budget laptop 2026")
    print("Phase 1 done. thread:", r1["thread_id"], "| next:", r1["next"])
    assert r1["next"] == ("subprompt_generator",)

    # Phase 2 (1 Gemini call)
    r2 = await session.generate_prompts(r1["thread_id"])
    print("Phase 2 done. sections:", r2["total_sections"], "| next:", r2["next"])
    assert r2["total_sections"] >= 5
    assert r2["next"] == ("section_writer",)

    # Phase 3, ONE section (2 Gemini calls)
    r3 = await session.execute_next_section(r1["thread_id"])
    print("Phase 3 step done. index:", r3["current_section_index"], "| next:", r3["next"])
    assert r3["current_section_index"] == 1
    assert len(r3["generated_sections"]) == 1
    assert len(r3["section_contexts"]) == 1

    await session.close()
    print("[OK] Interactive flow verified!")


if __name__ == "__main__":
    asyncio.run(main())
