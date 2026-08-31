"""Blog Writer Agent implementation using LLMRouter, keyword research, competitor analysis, and content plan."""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.config import logger
from backend.llm.router import FALLBACK_MESSAGE, LLMRouter
from core.prompts.blog_prompt import BLOG_WRITER_SYSTEM_PROMPT


async def write_blog(
    topic: str,
    keyword_data: Dict[str, Any],
    competitor_data: Dict[str, Any],
    plan: Optional[str] = None,
) -> str:
    """Generates a comprehensive, SEO-optimized markdown blog post using research and plan inputs."""
    logger.info(f"Writing blog post for topic: '{topic}'")

    keywords = keyword_data.get("keywords") or []
    kw_strings = []
    for kw in keywords:
        if isinstance(kw, dict):
            kw_strings.append(kw.get("keyword", kw.get("name", str(kw))))
        else:
            kw_strings.append(str(kw))

    primary_keyword = kw_strings[0] if kw_strings else topic
    secondary_keywords = kw_strings[1:] if len(kw_strings) > 1 else ["seo optimization", "content strategy"]

    gap_analysis = competitor_data.get("gap_analysis") or competitor_data.get("note") or "None specified"
    competitors = competitor_data.get("competitors") or []
    competitor_summary = f"Analyzed {len(competitors)} competitors." if competitors else "No competitor data provided."

    prompt_parts = [
        f"Topic / User Request: {topic}",
        f"Primary Keyword: {primary_keyword}",
        f"Secondary Keywords: {', '.join(secondary_keywords)}",
        f"Competitor Insights & Gap Analysis: {gap_analysis} ({competitor_summary})",
    ]

    if plan:
        prompt_parts.append(f"\nApproved Content Plan & Outline:\n{plan}")

    user_prompt = "\n\n".join(prompt_parts) + "\n\nWrite the complete, publication-ready blog post in pure Markdown according to all system guidelines."

    try:
        router = LLMRouter(task_type="blog_writing")
        response = await router.generate_text(
            prompt=user_prompt,
            system_prompt=BLOG_WRITER_SYSTEM_PROMPT,
            task_type="blog_writing",
        )

        if not response or "No LLM API keys" in response or response == FALLBACK_MESSAGE:
            logger.warning("LLM router returned fallback or no keys for blog writing. Using enhanced fallback template.")
            return _get_fallback_blog(primary_keyword, topic)

        return response
    except Exception as e:
        logger.warning(f"Error generating blog post: {e}. Using enhanced fallback template.")
        return _get_fallback_blog(primary_keyword, topic)


def _get_fallback_blog(primary_keyword: str, topic: str) -> str:
    """Returns a well-structured fallback markdown blog post when LLM generation is unavailable."""
    return f"""# {primary_keyword}: The Definitive Guide to {topic} (2026)

{topic} is transforming how professionals approach modern strategy, and mastering {primary_keyword} is essential for success. In this guide, we explore the core fundamentals, proven best practices, and expert insights to help you achieve measurable results.

## Understanding {primary_keyword}

The landscape of {topic} requires a structured approach. Without a clear understanding of {primary_keyword}, teams often waste valuable resources and miss critical growth opportunities.

### Core Principles

- Align strategy with clear objectives.
- Leverage data-driven insights for decision making.
- Maintain consistent execution across all channels.

## Strategic Comparison

When evaluating approaches for {topic}, consider the following trade-offs:

| Approach | Best For | Implementation Speed | Cost Efficiency |
|---|---|---|---|
| Strategy A | Beginners | Fast | High |
| Strategy B | Enterprises | Moderate | Medium |
| Strategy C | Power Users | Slow | Low |

## Best Practices for Success

Implementing {primary_keyword} effectively involves careful planning and continuous optimization. Ensure your workflows incorporate feedback loops and rigorous testing.

## Frequently Asked Questions

### What is {primary_keyword}?
{primary_keyword} is a targeted framework designed to optimize performance and drive sustainable results in {topic}.

### How do I get started?
Begin by auditing your current workflow, defining clear key performance indicators (KPIs), and applying industry best practices.
"""
