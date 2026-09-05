"""Gemini-only LLM router with 429-aware retry."""
from __future__ import annotations

import asyncio
import re
from typing import Optional

import httpx

from app import config
from app.config import logger
from backend.llm.providers import _call_gemini

FALLBACK_MESSAGE = (
    "⚠️ ContentForge AI could not reach the Gemini API. "
    "Please check your GEMINI_API_KEY in the .env file."
)


class LLMRouter:
    """Gemini-only LLM router with 429-aware retry handled inside _call_gemini."""
    
    def __init__(self, gemini_api_key: Optional[str] = None, timeout: float = 120.0, task_type: str = "default", **kwargs):
        self.gemini_api_key = (
            gemini_api_key
            if gemini_api_key is not None
            else getattr(config, "GEMINI_API_KEY", "")
        )
        self.timeout = timeout
        self.task_type = task_type
    
    async def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "default",
        model: str = "gemini-3.5-flash-lite",
    ) -> str:
        if not self.gemini_api_key:
            logger.error("Gemini API key is not configured.")
            return FALLBACK_MESSAGE
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info("Routing prompt to Gemini (task=%s, model=%s)...", task_type, model)
                result = await _call_gemini(
                    client, prompt, system_prompt, self.gemini_api_key, model=model,
                )
                result = clean_llm_response(result)
                return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("Gemini 429 persisted after all retries. Propagating.")
                raise
            logger.error("Gemini HTTP error: %d %s", e.response.status_code, e)
            return FALLBACK_MESSAGE
        except (ValueError, httpx.RequestError) as e:
            logger.error("Gemini call failed: %s", e)
            return FALLBACK_MESSAGE


def clean_llm_response(text: str) -> str:
    """Strip <think> blocks and normalize whitespace."""
    if not text:
        return text
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE).strip()
    return text
