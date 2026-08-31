"""Comprehensive test suite for Level 9 Blog Writer Agent and blog writing node."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.prompts.blog_prompt import BLOG_WRITER_SYSTEM_PROMPT
from core.agents.blog_writer_agent import write_blog
from core.graph import blog_writing_node
from core.state import create_initial_state


def test_blog_prompt_exists():
    """Verify BLOG_WRITER_SYSTEM_PROMPT exists and contains key terms."""
    assert BLOG_WRITER_SYSTEM_PROMPT is not None
    assert isinstance(BLOG_WRITER_SYSTEM_PROMPT, str)
    assert len(BLOG_WRITER_SYSTEM_PROMPT) > 200
    assert "markdown" in BLOG_WRITER_SYSTEM_PROMPT.lower()
    assert "h1" in BLOG_WRITER_SYSTEM_PROMPT.lower()
    assert "seo" in BLOG_WRITER_SYSTEM_PROMPT.lower()
    assert "faq" in BLOG_WRITER_SYSTEM_PROMPT.lower()
    print("[OK] test_blog_prompt_exists passed")


def test_write_blog_callable():
    """Verify write_blog function is callable."""
    assert callable(write_blog)
    print("[OK] test_write_blog_callable passed")


def test_blog_writing_node_import():
    """Verify blog_writing_node can be imported from core.graph."""
    assert callable(blog_writing_node)
    print("[OK] test_blog_writing_node_import passed")


def test_blog_writing_node_mock():
    """Mock write_blog, run blog_writing_node with state, and verify generated_assets['blog'] update."""
    async def run_test():
        with patch("core.graph.write_blog", new_callable=AsyncMock) as mock_write:
            mock_write.return_value = "# Mock Blog Title\n\nMocked blog content for testing."
            state = create_initial_state("AI Productivity Tools")
            state["keyword_research"] = {
                "topic": "AI Productivity Tools",
                "keywords": ["ai productivity tools", "productivity apps"]
            }
            state["competitor_analysis"] = {
                "gap_analysis": "Competitors lack detailed FAQ."
            }
            state["pending_agent_output"] = {
                "outline": "# Outline\n## Intro\n## Body"
            }

            result_state = await blog_writing_node(state)

            assert "generated_assets" in result_state
            assert "blog" in result_state["generated_assets"]
            assert "Mock Blog Title" in result_state["generated_assets"]["blog"]
            assert result_state["current_step_index"] == state.get("current_step_index", 0) + 1
            assert result_state["operations_count"] == state.get("operations_count", 0) + 1
            mock_write.assert_awaited_once()
            print("[OK] test_blog_writing_node_mock passed")

    asyncio.run(run_test())


def main():
    test_blog_prompt_exists()
    test_write_blog_callable()
    test_blog_writing_node_import()
    test_blog_writing_node_mock()
    print("LEVEL 9 VERIFIED — All tests passed. Blog Writer Agent integrated successfully.")


if __name__ == "__main__":
    main()
