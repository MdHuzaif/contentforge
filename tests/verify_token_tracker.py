"""Verification script for backend/utils/token_tracker.py."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    from backend.utils.token_tracker import get_token_tracker, estimate_tokens

    tracker = get_token_tracker()
    await tracker.initialize()
    await tracker.reset_monthly()

    await tracker.log_usage(
        task_id="task_123",
        provider="groq",
        model="llama-3.3-70b-versatile",
        prompt_tokens=150,
        completion_tokens=350,
    )

    usage = await tracker.get_monthly_usage()
    assert usage == 500
    print("Current monthly usage:", usage)

    summary = await tracker.get_usage_summary()
    assert summary["total_tokens"] == 500
    assert summary["by_provider"]["groq"] == 500
    print("Usage summary:", summary)

    under_budget = await tracker.check_budget(limit=1000)
    assert under_budget is True
    print("Under budget check passed:", under_budget)

    est = await estimate_tokens("Hello world from ContentForge AI!")
    assert est > 0
    print("Estimated tokens:", est)

    await tracker.reset_monthly()
    print("[OK] backend/utils/token_tracker.py verified successfully!")


if __name__ == "__main__":
    asyncio.run(main())
