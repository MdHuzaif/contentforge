from __future__ import annotations

import sys
from pathlib import Path
import asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import AsyncMock
from core.agents.seo_agent import build_seo_agent, run_seo_analysis


def test_build_seo_agent():
    mock_llm = AsyncMock()
    agent = build_seo_agent(mock_llm)
    assert agent is not None


def test_run_seo_analysis_strategy_mode():
    async def run():
        res = await run_seo_analysis(
            topic="Best AI Tools",
            primary_keyword="best ai tools",
            competitor_metrics={"avg_word_count": 1200, "avg_h2_count": 4, "avg_readability": 65.0},
        )
        assert res["status"] == "completed"
        assert res["topic"] == "Best AI Tools"
        assert res["primary_keyword"] == "best ai tools"
        assert res["seo_score"] is None
        assert "strategy" in res
        assert res["strategy"]["target_word_count"] == 1320
        assert "llm_recommendations" in res

    asyncio.run(run())


def test_run_seo_analysis_draft_mode():
    async def run():
        content = """
# Best AI Tools Guide
Here is the best ai tools guide for everyone.
## Understanding Best AI Tools
- Feature one
- Feature two

| Tool | Rating |
|---|---|
| Tool A | 5/5 |

[Source](https://example.com)

## FAQ Section
What are the best ai tools?
        """
        title = "Top 10 Best AI Tools for 2026 Ultimate Guide"
        meta_desc = "Discover the best ai tools to boost your productivity. Read our comprehensive review of top platforms with features, pricing, and comparisons for 2026."
        
        res = await run_seo_analysis(
            topic="Best AI Tools",
            primary_keyword="best ai tools",
            content_text=content,
            title=title,
            meta_description=meta_desc,
            related_keywords=["ai writing", "productivity apps"],
            competitor_metrics={"avg_word_count": 1500, "avg_h2_count": 3, "avg_readability": 68.0},
        )
        assert res["status"] == "completed"
        assert res["seo_score"] is not None
        assert isinstance(res["seo_score"], int)
        assert "checks" in res
        assert "improvements" in res
        assert "internal_link_suggestions" in res
        assert "strategy" in res
        assert "llm_recommendations" in res

    asyncio.run(run())


def main():
    test_build_seo_agent()
    test_run_seo_analysis_strategy_mode()
    test_run_seo_analysis_draft_mode()
    print("LEVEL 7 AGENT VERIFIED — All tests passed successfully.")


if __name__ == "__main__":
    main()
