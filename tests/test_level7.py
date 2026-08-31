"""Comprehensive test suite for Level 7 SEO Analysis Agent and LangGraph integration."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.tools.seo_tools import (
    extract_markdown_headings,
    keyword_density,
    analyze_title,
    compute_seo_report,
)
from core.prompts.seo_prompt import SEO_SYSTEM_PROMPT
from core.agents.seo_agent import build_seo_agent, run_seo_analysis
from core.graph import seo_analysis_node
from core.state import create_initial_state


def test_extract_markdown_headings():
    content = """
# Main H1 Title
## H2 Subheading One
### H3 Section A
### H3 Section B
## H2 Subheading Two
    """
    headings = extract_markdown_headings(content)
    assert len(headings["h1"]) == 1
    assert len(headings["h2"]) == 2
    assert len(headings["h3"]) == 2
    assert headings["h1"] == ["Main H1 Title"]
    print("[OK] test_extract_markdown_headings passed")


def test_keyword_density():
    # Construct text where keyword appears 3 times among ~60 words -> density around 5% (high) or let's tune for optimal (0.5 <= density <= 2.5)
    # e.g. 200 words, keyword appears 3 times -> 3 * 3 / 200 * 100 = 4.5%.
    # If 300 words, keyword ("best ai tools" = 3 words) appears 2 times: 2 * 3 / 300 * 100 = 2.0% -> optimal!
    text = "best ai tools " + "word " * 145 + "best ai tools " + "word " * 145
    res = keyword_density(text, "best ai tools")
    assert res["occurrences"] == 2
    assert res["status"] == "optimal"

    res_empty = keyword_density("", "")
    assert res_empty["score"] == 0
    print("[OK] test_keyword_density passed")


def test_analyze_title():
    title = "Best AI Tools 2026: Top 10 Guide"
    res = analyze_title(title, "best ai tools")
    assert res["has_keyword"] is True
    assert res["has_number"] is True
    assert res["score"] >= 10
    print("[OK] test_analyze_title passed")


def test_compute_seo_report():
    draft = """
# Best AI Tools for Productivity
Here is a comprehensive guide to the best ai tools available in 2026.
## Top Recommendations
- Tool Alpha for writing
- Tool Beta for coding

| Tool | Rating | Price |
|---|---|---|
| Alpha | 4.8 | Free |
| Beta | 4.9 | $10 |

[Learn more](https://example.com)

## Frequently Asked Questions
What are the best ai tools?
    """
    title = "Top 10 Best AI Tools 2026 Ultimate Guide"
    meta = "Discover the best ai tools to boost your productivity. Read our comprehensive review of top platforms with features, pricing, and comparisons."
    report = compute_seo_report(
        content=draft,
        title=title,
        meta_description=meta,
        primary_keyword="best ai tools",
        related_keywords=["ai writing", "productivity apps"],
        competitor_metrics={"avg_word_count": 1500},
    )
    assert 0 <= report["seo_score"] <= 100
    assert isinstance(report["improvements"], list)
    assert isinstance(report["internal_link_suggestions"], list)
    print("[OK] test_compute_seo_report passed")


def test_seo_prompt_exists():
    assert SEO_SYSTEM_PROMPT is not None
    assert isinstance(SEO_SYSTEM_PROMPT, str)
    assert len(SEO_SYSTEM_PROMPT) > 300
    assert "PRIORITY FIXES" in SEO_SYSTEM_PROMPT
    assert "KEYWORD PLACEMENT" in SEO_SYSTEM_PROMPT
    print("[OK] test_seo_prompt_exists passed")


def test_build_seo_agent_callable():
    assert build_seo_agent is not None
    mock_llm = AsyncMock()
    agent = build_seo_agent(mock_llm)
    assert agent is not None
    print("[OK] test_build_seo_agent_callable passed")


def test_run_seo_analysis_strategy_mode():
    async def run():
        with patch("core.agents.seo_agent.LLMRouter") as mock_router_class:
            mock_router = AsyncMock()
            mock_router.generate_text.return_value = "Mock SEO recommendations"
            mock_router_class.return_value = mock_router

            result = await run_seo_analysis(
                topic="AI tools",
                primary_keyword="best ai tools",
                content_text="",
                competitor_metrics={"avg_word_count": 1500},
            )
            assert result["status"] == "completed"
            assert "strategy" in result
            assert "target_word_count" in result["strategy"]
            assert result["llm_recommendations"] == "Mock SEO recommendations"
    asyncio.run(run())
    print("[OK] test_run_seo_analysis_strategy_mode passed")


async def test_seo_analysis_node_exec():
    with patch("core.graph.run_seo_analysis", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {
            "status": "completed",
            "seo_score": 78,
            "improvements": [],
            "llm_recommendations": "x",
        }
        state = create_initial_state(user_request="best ai tools", thread_id="t_level7")
        state["keyword_research"] = {"topic": "best ai tools", "keywords": ["best ai tools", "ai tools"]}
        result = await seo_analysis_node(state)

        assert result["seo_scores"]["seo_score"] == 78
        assert result["current_step_index"] == state.get("current_step_index", 0) + 1
        assert result["operations_count"] == state.get("operations_count", 0) + 1
        mock_run.assert_awaited_once()
    print("[OK] test_seo_analysis_node passed")


def main():
    test_extract_markdown_headings()
    test_keyword_density()
    test_analyze_title()
    test_compute_seo_report()
    test_seo_prompt_exists()
    test_build_seo_agent_callable()
    test_run_seo_analysis_strategy_mode()
    asyncio.run(test_seo_analysis_node_exec())
    print("LEVEL 7 VERIFIED — All tests passed. SEO Analysis Agent integrated successfully.")


if __name__ == "__main__":
    main()
