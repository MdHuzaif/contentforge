from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agents.competitor_agent import build_competitor_agent, run_competitor_analysis
from core.prompts.competitor_prompt import (
    COMPETITOR_ANALYSIS_SYSTEM_PROMPT,
    SHORTS_PATTERN_PROMPT,
)


def test_competitor_prompts_exist():
    assert COMPETITOR_ANALYSIS_SYSTEM_PROMPT is not None
    assert isinstance(COMPETITOR_ANALYSIS_SYSTEM_PROMPT, str)
    assert len(COMPETITOR_ANALYSIS_SYSTEM_PROMPT) > 500
    
    assert SHORTS_PATTERN_PROMPT is not None
    assert isinstance(SHORTS_PATTERN_PROMPT, str)
    assert len(SHORTS_PATTERN_PROMPT) > 100
    print("[OK] test_competitor_prompts_exist passed")


def test_build_competitor_agent():
    assert build_competitor_agent is not None
    mock_llm = AsyncMock()
    agent = build_competitor_agent(mock_llm)
    assert agent is not None
    print("[OK] test_build_competitor_agent passed")


async def test_run_competitor_analysis_mocked():
    with patch("core.agents.competitor_agent.get_top_results", new_callable=AsyncMock) as mock_get_top, \
         patch("core.agents.competitor_agent.fetch_and_analyze", new_callable=AsyncMock) as mock_fetch, \
         patch("core.agents.competitor_agent.LLMRouter") as mock_router_class:
        
        mock_get_top.return_value = [
            {"title": "Competitor 1", "url": "https://example.com/1", "snippet": "Snippet 1"},
            {"title": "Competitor 2", "url": "https://example.com/2", "snippet": "Snippet 2"},
        ]
        
        mock_fetch.side_effect = [
            {
                "url": "https://example.com/1",
                "word_count": 1200,
                "h1_count": 1,
                "h2_count": 4,
                "h3_count": 2,
                "headings": {"h1": ["Title"], "h2": ["H2.1"], "h3": ["H3.1"]},
                "image_count": 3,
                "total_links": 10,
                "external_links_count": 2,
                "meta": {"title": "Comp 1", "meta_description": "Desc 1", "has_meta_description": True, "has_schema": True, "has_canonical": True},
                "readability": 62.5,
                "avg_sentence_length": 15.0,
                "engagement_signals": {"has_lists": True, "has_table": False, "has_video_embed": True, "has_faq": False, "has_toc": True}
            },
            {
                "url": "https://example.com/2",
                "word_count": 1500,
                "h1_count": 1,
                "h2_count": 5,
                "h3_count": 3,
                "headings": {"h1": ["Title 2"], "h2": ["H2.2"], "h3": ["H3.2"]},
                "image_count": 5,
                "total_links": 15,
                "external_links_count": 3,
                "meta": {"title": "Comp 2", "meta_description": "", "has_meta_description": False, "has_schema": False, "has_canonical": True},
                "readability": 58.0,
                "avg_sentence_length": 18.0,
                "engagement_signals": {"has_lists": True, "has_table": True, "has_video_embed": False, "has_faq": True, "has_toc": False}
            }
        ]

        mock_router = AsyncMock()
        mock_router.generate_text.side_effect = [
            "# Competitor Gap Analysis\nMocked gap analysis output.",
            "# Shorts Patterns\nMocked shorts patterns output."
        ]
        mock_router_class.return_value = mock_router

        result = await run_competitor_analysis(topic="Artificial Intelligence in Content Creation")

        assert result["status"] == "completed"
        assert result["topic"] == "Artificial Intelligence in Content Creation"
        assert len(result["competitors"]) == 2
        assert "metrics" in result
        assert result["metrics"]["competitor_count"] == 2
        assert result["gap_analysis"] == "# Competitor Gap Analysis\nMocked gap analysis output."
        assert result["shorts_patterns"] == "# Shorts Patterns\nMocked shorts patterns output."
        assert len(result["sources"]) == 2
        print("[OK] test_run_competitor_analysis_mocked passed")


def main():
    test_competitor_prompts_exist()
    test_build_competitor_agent()
    asyncio.run(test_run_competitor_analysis_mocked())
    print("LEVEL 6 AGENT VERIFIED — All tests passed successfully.")


if __name__ == "__main__":
    main()
