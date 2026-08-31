"""Verification script for TokenTracker and LLMRouter integration."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    from backend.llm.router import LLMRouter
    from backend.utils.token_tracker import get_token_tracker

    tracker = get_token_tracker()
    await tracker.initialize()
    await tracker.reset_monthly()

    router = LLMRouter(groq_api_key="mock_key", task_type="seo_analysis")
    with patch("backend.llm.router._call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = "SEO analysis result text with keywords."
        res = await router.generate_text("Analyze SEO for AI content")
        assert res == "SEO analysis result text with keywords."
        mock_groq.assert_awaited_once()

    usage = await tracker.get_monthly_usage()
    assert usage > 0
    print("Token usage recorded via router:", usage)

    summary = await tracker.get_usage_summary()
    assert summary["by_provider"]["groq"] > 0
    print("Usage summary:", summary)

    await tracker.reset_monthly()
    print("[OK] TokenTracker & LLMRouter integration verified successfully!")


if __name__ == "__main__":
    asyncio.run(main())
