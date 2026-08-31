"""Core execution pipeline for Level 2 ContentForge AI."""
from __future__ import annotations

from app.config import logger
from backend.llm.router import LLMRouter
from core.prompts import OUTLINE_GENERATION_PROMPT


async def run_level_2_pipeline(topic: str) -> str:
    """Run the Level 2 content generation pipeline for a given topic."""
    logger.info("Starting Level 2 pipeline for topic: %s", topic)
    try:
        router = LLMRouter()
        prompt = OUTLINE_GENERATION_PROMPT.format(topic=topic)
        system_prompt = (
            "You are an expert SEO Content Strategist and professional technical writer."
        )

        response = await router.generate_text(prompt=prompt, system_prompt=system_prompt)
        logger.info("Level 2 pipeline completed successfully for topic: %s", topic)
        return response
    except Exception as e:
        logger.error("Error executing Level 2 pipeline for topic '%s': %s", topic, e)
        return f"⚠️ Error executing Level 2 pipeline: {e}"
