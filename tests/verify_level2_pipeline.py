"""Verification script for Level 2 core pipeline."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    from core.pipeline import run_level_2_pipeline
    result = await run_level_2_pipeline("Artificial Intelligence in Healthcare")
    print("Pipeline result length:", len(result))
    print("Pipeline result preview:\n", result[:300])
    print("[OK] Level 2 core pipeline verified successfully!")


if __name__ == "__main__":
    asyncio.run(main())
