"""Comprehensive test suite for Level 6 Competitor Analysis Agent and LangGraph integration."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.tools.serp_scraper import clean_html, get_top_results
from backend.tools.content_analyzer import analyze_html, aggregate_metrics
from core.agents.competitor_agent import build_competitor_agent
from core.prompts.competitor_prompt import (
    COMPETITOR_ANALYSIS_SYSTEM_PROMPT,
    SHORTS_PATTERN_PROMPT,
)
from core.graph import competitor_analysis_node
from core.state import create_initial_state


def test_serp_scraper_import_and_clean():
    assert get_top_results is not None
    assert clean_html is not None
    cleaned = clean_html("<p>Hi <b>there</b></p>")
    assert "Hi there" in cleaned
    print("[OK] test_serp_scraper_import_and_clean passed")


def test_content_analyzer_analyze_html():
    sample_html = """
    <html>
      <head>
        <title>Best Budget Smartphones 2026</title>
        <meta name="description" content="Discover the best budget smartphones in 2026 with detailed reviews."/>
      </head>
      <body>
        <h1>Best Budget Smartphones</h1>
        <h2>Top Picks</h2>
        <p>Choosing a budget smartphone in 2026 requires looking at battery life, camera quality, processor speed, and overall value for money. Many brands offer flagship killer features at a fraction of the cost.</p>
        <h2>Comparison Table</h2>
        <h3>Model A</h3>
        <h3>Model B</h3>
        <h3>Model C</h3>
        <ul>
          <li>Great battery</li>
          <li>OLED display</li>
        </ul>
        <table><tr><td>Phone</td><td>Price</td></tr></table>
        <img src="phone1.jpg" alt="Phone 1"/>
        <img src="phone2.jpg" alt="Phone 2"/>
      </body>
    </html>
    """
    analysis = analyze_html(sample_html, url="https://example.com/smartphones")
    assert analysis["word_count"] > 0
    assert analysis["h1_count"] == 1
    assert analysis["h2_count"] == 2
    assert analysis["h3_count"] == 3
    assert analysis["image_count"] == 2
    assert analysis["engagement_signals"]["has_lists"] is True
    assert analysis["meta"]["has_meta_description"] is True
    print("[OK] test_content_analyzer_analyze_html passed")


def test_aggregate_metrics():
    analyses = [
        {
            "word_count": 1200,
            "h2_count": 3,
            "h3_count": 2,
            "image_count": 4,
            "readability": 60.0,
            "meta": {"has_meta_description": True, "has_schema": True},
            "engagement_signals": {"has_lists": True, "has_table": False, "has_video_embed": True}
        },
        {
            "word_count": 1600,
            "h2_count": 5,
            "h3_count": 3,
            "image_count": 6,
            "readability": 55.0,
            "meta": {"has_meta_description": True, "has_schema": False},
            "engagement_signals": {"has_lists": True, "has_table": True, "has_video_embed": False}
        }
    ]
    agg = aggregate_metrics(analyses)
    assert agg["competitor_count"] == 2
    assert isinstance(agg["avg_word_count"], float)
    assert agg["avg_word_count"] == 1400.0
    print("[OK] test_aggregate_metrics passed")


def test_competitor_prompt_exists():
    assert COMPETITOR_ANALYSIS_SYSTEM_PROMPT is not None
    assert isinstance(COMPETITOR_ANALYSIS_SYSTEM_PROMPT, str)
    assert len(COMPETITOR_ANALYSIS_SYSTEM_PROMPT) > 500

    assert SHORTS_PATTERN_PROMPT is not None
    assert isinstance(SHORTS_PATTERN_PROMPT, str)
    assert len(SHORTS_PATTERN_PROMPT) > 100

    for term in ["gap", "competitor", "word count"]:
        assert term.lower() in COMPETITOR_ANALYSIS_SYSTEM_PROMPT.lower(), f"Prompt missing term: {term}"
    print("[OK] test_competitor_prompt_exists passed")


def test_build_competitor_agent_callable():
    assert build_competitor_agent is not None
    mock_llm = AsyncMock()
    agent = build_competitor_agent(mock_llm)
    assert agent is not None
    print("[OK] test_build_competitor_agent_callable passed")


async def test_competitor_analysis_node():
    with patch("core.graph.run_competitor_analysis", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {
            "status": "completed",
            "topic": "best budget smartphone 2026",
            "competitors": [],
            "metrics": {"competitor_count": 2, "avg_word_count": 1300.0},
            "gap_analysis": "Mocked gap analysis output.",
            "shorts_patterns": "Mocked shorts patterns output.",
            "sources": ["https://example.com"],
            "note": None,
        }

        state = create_initial_state(user_request="best budget smartphone 2026", thread_id="t_level6")
        result = await competitor_analysis_node(state)

        assert result["competitor_analysis"]["status"] == "completed"
        assert result["current_step_index"] == state.get("current_step_index", 0) + 1
        assert result["operations_count"] == state.get("operations_count", 0) + 1
        mock_run.assert_awaited_once()
    print("[OK] test_competitor_analysis_node passed")


def main():
    test_serp_scraper_import_and_clean()
    test_content_analyzer_analyze_html()
    test_aggregate_metrics()
    test_competitor_prompt_exists()
    test_build_competitor_agent_callable()
    asyncio.run(test_competitor_analysis_node())
    print("LEVEL 6 VERIFIED — All tests passed. Competitor Analysis Agent integrated successfully.")


if __name__ == "__main__":
    main()
