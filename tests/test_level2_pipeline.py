"""Tests for Level 2 core pipeline and prompts."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.prompts import OUTLINE_GENERATION_PROMPT
from core.pipeline import run_level_2_pipeline


def test_prompt_formatting():
    formatted = OUTLINE_GENERATION_PROMPT.format(topic="Python Programming")
    assert "Python Programming" in formatted
    assert "SEO Keywords" in formatted
    assert "H1 Title" in formatted
    assert "Blog Outline" in formatted
    print("[OK] Prompt formatting test passed")


@patch("core.pipeline.LLMRouter")
def test_pipeline_execution(mock_router_class):
    mock_router = AsyncMock()
    mock_router.generate_text.return_value = "# Mock Outline Response"
    mock_router_class.return_value = mock_router

    res = asyncio.run(run_level_2_pipeline("Machine Learning"))
    assert res == "# Mock Outline Response"
    mock_router.generate_text.assert_awaited_once()
    print("[OK] Pipeline execution test passed")


def main():
    test_prompt_formatting()
    test_pipeline_execution()
    print("[OK] All Level 2 pipeline tests passed successfully!")


if __name__ == "__main__":
    main()
