"""Prompt definitions for ContentForge AI core pipelines."""
from __future__ import annotations

OUTLINE_GENERATION_PROMPT = """You are an expert SEO Content Strategist. Your task is to generate a comprehensive content outline for the given topic.

Topic: {topic}

Please provide:
a) 5 High-volume SEO Keywords related to the topic
b) A catchy, SEO-optimized H1 Title
c) A structured Blog Outline with clear H2 and H3 headings and brief description bullets for each section.

Format the response clearly in Markdown.
"""
