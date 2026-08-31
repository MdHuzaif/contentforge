"""Competitor Analysis Agent implementation using LangGraph prebuilt ReAct agent and tool runner."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from langgraph.prebuilt import create_react_agent

from app.config import logger
from backend.llm.router import LLMRouter
from backend.tools.content_analyzer import aggregate_metrics, fetch_and_analyze
from backend.tools.serp_scraper import get_top_results
from core.prompts.competitor_prompt import (
    COMPETITOR_ANALYSIS_SYSTEM_PROMPT,
    SHORTS_PATTERN_PROMPT,
)


def build_competitor_agent(llm: Any = None, *, pre_model_hook: Optional[Any] = None) -> Any:
    """Builds and returns the competitor analysis ReAct agent."""
    if llm is None:
        llm = LLMRouter()

    agent = create_react_agent(
        model=llm,
        tools=[],
        name="competitor_agent",
        prompt=COMPETITOR_ANALYSIS_SYSTEM_PROMPT,
        pre_model_hook=pre_model_hook,
    )
    return agent


async def run_competitor_analysis(
    topic: str, keyword_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute live SERP scraping, competitor content analysis, LLM gap analysis, and shorts pattern detection."""
    try:
        logger.info("Starting competitor analysis for topic: '%s'", topic)

        # Step a: Get top SERP results
        results = await get_top_results(topic, max_results=10)

        # Step b: Take top 5 URLs and fetch/analyze in parallel
        top_urls = [r.get("url") for r in results if r.get("url")][:5]

        analyses: List[Dict[str, Any]] = []
        if top_urls:
            tasks = [fetch_and_analyze(url) for url in top_urls]
            fetched_results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in fetched_results:
                if isinstance(res, dict) and res:
                    analyses.append(res)

        # Step c: Aggregate metrics
        metrics = aggregate_metrics(analyses)

        sources = [a.get("url") for a in analyses if a.get("url")]

        competitor_summaries_text = ""
        for idx, comp in enumerate(analyses, 1):
            meta = comp.get("meta", {})
            eng = comp.get("engagement_signals", {})
            competitor_summaries_text += (
                f"\nCompetitor {idx}:\n"
                f"- URL: {comp.get('url')}\n"
                f"- Title: {meta.get('title')}\n"
                f"- Word Count: {comp.get('word_count')}\n"
                f"- Readability: {comp.get('readability')}\n"
                f"- H2 Count: {comp.get('h2_count')}, H3 Count: {comp.get('h3_count')}\n"
                f"- Meta Description Present: {meta.get('has_meta_description')}\n"
                f"- Schema Present: {meta.get('has_schema')}\n"
                f"- Engagement Signals: Lists={eng.get('has_lists')}, Table={eng.get('has_table')}, "
                f"Video={eng.get('has_video_embed')}, FAQ={eng.get('has_faq')}, TOC={eng.get('has_toc')}\n"
            )

        note = None
        if not results:
            note = "live SERP data unavailable - analysis based on model knowledge"
            logger.warning("Live SERP data unavailable for topic '%s'; falling back to model knowledge.", topic)

        analysis_prompt = (
            f"Topic: {topic}\n"
            f"Keyword Intelligence: {keyword_data or 'None provided'}\n"
            f"Aggregated Competitor Metrics: {metrics}\n"
            f"Per-Competitor Summaries:\n{competitor_summaries_text}\n\n"
            "Please perform a comprehensive SEO competitor analysis and gap strategy following your instructions."
        )

        llm_router = LLMRouter()

        # Step d: Generate gap analysis
        gap_analysis = await llm_router.generate_text(
            prompt=analysis_prompt,
            system_prompt=COMPETITOR_ANALYSIS_SYSTEM_PROMPT,
        )

        # Step f: Generate shorts patterns
        shorts_prompt = f"Topic: {topic}\n\nAnalyze viral short-form video patterns for this topic."
        shorts_patterns = await llm_router.generate_text(
            prompt=shorts_prompt,
            system_prompt=SHORTS_PATTERN_PROMPT,
        )

        return {
            "status": "completed",
            "topic": topic,
            "competitors": analyses,
            "metrics": metrics,
            "gap_analysis": gap_analysis,
            "shorts_patterns": shorts_patterns,
            "sources": sources,
            "note": note,
        }

    except Exception as e:
        logger.error("Error in run_competitor_analysis for topic '%s': %s", topic, e)
        fallback_gap = f"# Competitor Analysis for {topic}\n\nAnalysis degraded due to error: {e}"
        return {
            "status": "completed",
            "topic": topic,
            "competitors": [],
            "metrics": {},
            "gap_analysis": fallback_gap,
            "shorts_patterns": "",
            "sources": [],
            "note": f"competitor analysis degraded: {e}",
        }
