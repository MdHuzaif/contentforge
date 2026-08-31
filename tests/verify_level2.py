"""Level 2 Verification Script."""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    from backend.llm import LLMRouter
    
    router = LLMRouter(gemini_api_key="")
    res = await router.generate_text("Hello from Level 2 test")
    assert "GEMINI_API_KEY" in res or "Gemini API" in res
    print("[OK] Level 2 Gemini-only router verified!")


if __name__ == "__main__":
    asyncio.run(main())
