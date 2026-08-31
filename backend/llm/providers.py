"""LLM Provider API callers for Gemini with 429-aware retry."""
from __future__ import annotations

import asyncio
import inspect
import re
from typing import Any

import httpx

from app.config import logger

GEMINI_429_WAIT_SECONDS = 60  # 1 minute
MAX_RETRIES = 3


async def _call_gemini(
    client: httpx.AsyncClient,
    prompt: str,
    system_prompt: str = "",
    api_key: str = "",
    model: str = "gemini-3.5-flash-lite",
) -> str:
    """Call Gemini API with 429-aware retry (5-min wait on rate limit)."""
    if not api_key:
        raise ValueError("Gemini API key is missing or empty.")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    # Build contents list
    contents = []
    if system_prompt:
        contents.append({"role": "user", "parts": [{"text": f"System: {system_prompt}"}]})
        contents.append({"role": "model", "parts": [{"text": "Understood."}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})
    
    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 8192,
            "topP": 0.95,
            "topK": 40,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }
    
    last_exception: Exception | None = None
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.info("Sending request to Gemini API (model=%s, attempt=%d/%d)...", model, attempt + 1, MAX_RETRIES)
            response = await client.post(url, headers=headers, json=payload)
            
            # 429 Rate Limit: Wait 5 minutes, then retry
            if response.status_code == 429:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        "Gemini API rate limited (429). Waiting %d seconds (1 minute) before retry "
                        "(attempt %d/%d)...",
                        GEMINI_429_WAIT_SECONDS, attempt + 1, MAX_RETRIES,
                    )
                    await asyncio.sleep(GEMINI_429_WAIT_SECONDS)
                    continue
                else:
                    raise httpx.HTTPStatusError(
                        f"Gemini API rate limited (429) after {MAX_RETRIES} retries",
                        request=response.request,
                        response=response,
                    )
            
            # 5xx Server errors: short retry (10s)
            if response.status_code >= 500 and attempt < MAX_RETRIES - 1:
                wait_time = 10 * (attempt + 1)
                logger.warning(
                    "Gemini API server error (%d). Retrying in %ds (attempt %d/%d)...",
                    response.status_code, wait_time, attempt + 1, MAX_RETRIES,
                )
                await asyncio.sleep(wait_time)
                continue
            
            response.raise_for_status()
            
            data = response.json()
            if inspect.isawaitable(data):
                data = await data
            
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("Gemini API response contained no candidates.")
            
            parts = candidates[0].get("content", {}).get("parts", [])
            text_parts = [p.get("text", "") for p in parts if "text" in p]
            text = "\n".join(text_parts)
            
            # Strip <think> tags (Qwen-style reasoning)
            if text:
                text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE).strip()
            
            if not text:
                raise ValueError("Gemini API returned empty text content.")
            
            return text.strip()
            
        except (httpx.HTTPStatusError, ValueError, httpx.RequestError) as e:
            last_exception = e
            # On non-429 errors, short backoff then retry
            if attempt < MAX_RETRIES - 1:
                wait_time = 10 * (attempt + 1)
                logger.warning(
                    "Gemini error (%s). Retrying in %ds (attempt %d/%d)...",
                    type(e).__name__, wait_time, attempt + 1, MAX_RETRIES,
                )
                await asyncio.sleep(wait_time)
                continue
    
    raise last_exception or RuntimeError("Gemini API call failed after all retries.")
