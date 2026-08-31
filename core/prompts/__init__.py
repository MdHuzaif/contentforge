"""Prompts package for ContentForge AI."""
from __future__ import annotations

from core.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT
from core.prompts.keyword_prompt import KEYWORD_RESEARCH_SYSTEM_PROMPT
from core.prompts.competitor_prompt import (
    COMPETITOR_ANALYSIS_SYSTEM_PROMPT,
    SHORTS_PATTERN_PROMPT,
)
from core.prompts.seo_prompt import SEO_SYSTEM_PROMPT
from core.prompts.planning_prompt import PLANNING_SYSTEM_PROMPT
from core.prompts.blog_prompt import BLOG_WRITER_SYSTEM_PROMPT

OUTLINE_GENERATION_PROMPT = """You are an expert SEO Content Strategist. Your task is to generate a comprehensive content outline for the given topic.

Topic: {topic}

Please provide:
a) 5 High-volume SEO Keywords related to the topic
b) A catchy, SEO-optimized H1 Title
c) A structured Blog Outline with clear H2 and H3 headings and brief description bullets for each section.

Format the response clearly in Markdown.
"""

__all__ = [
    "SUPERVISOR_SYSTEM_PROMPT",
    "KEYWORD_RESEARCH_SYSTEM_PROMPT",
    "OUTLINE_GENERATION_PROMPT",
    "PLANNING_SYSTEM_PROMPT",
    "COMPETITOR_ANALYSIS_SYSTEM_PROMPT",
    "SHORTS_PATTERN_PROMPT",
    "SEO_SYSTEM_PROMPT",
    "BLOG_WRITER_SYSTEM_PROMPT",
]
