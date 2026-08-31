"""Level 2 LLM Router tests — Gemini-only with 429-aware retry."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.llm import LLMRouter, FALLBACK_MESSAGE
from backend.llm.providers import _call_gemini


# --- Test 1: Empty API key returns FALLBACK_MESSAGE ---
async def test_empty_api_key_returns_fallback():
    router = LLMRouter(gemini_api_key="")
    result = await router.generate_text("Hello")
    assert result == FALLBACK_MESSAGE
    print("[OK] test_empty_api_key_returns_fallback")


# --- Test 2: 429 triggers 5-min wait then retries ---
async def test_429_triggers_5min_wait():
    fake_response_429 = MagicMock()
    fake_response_429.status_code = 429
    fake_response_429.request = MagicMock()
    
    fake_response_200 = MagicMock()
    fake_response_200.status_code = 200
    fake_response_200.raise_for_status = MagicMock()
    fake_response_200.json = MagicMock(return_value={
        "candidates": [{"content": {"parts": [{"text": "success after retry"}]}}]
    })
    
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(side_effect=[fake_response_429, fake_response_200])
    
    with patch("backend.llm.providers.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await _call_gemini(fake_client, "prompt", "", "fake-key")
        mock_sleep.assert_called_with(60)  # 1 minute
    assert result == "success after retry"
    print("[OK] test_429_triggers_5min_wait")


# --- Test 3: 429 persists 3 times -> raises ---
async def test_429_persists_raises():
    import httpx
    fake_response_429 = MagicMock()
    fake_response_429.status_code = 429
    fake_response_429.request = MagicMock()
    
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(return_value=fake_response_429)
    
    with patch("backend.llm.providers.asyncio.sleep", new_callable=AsyncMock):
        try:
            await _call_gemini(fake_client, "prompt", "", "fake-key")
            assert False, "Should have raised"
        except httpx.HTTPStatusError as e:
            assert e.response.status_code == 429
    assert fake_client.post.await_count == 3  # MAX_RETRIES
    print("[OK] test_429_persists_raises")


# --- Test 4: Successful call ---
async def test_gemini_success():
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.raise_for_status = MagicMock()
    fake_response.json = MagicMock(return_value={
        "candidates": [{"content": {"parts": [{"text": "Hello world"}]}}]
    })
    
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(return_value=fake_response)
    
    result = await _call_gemini(fake_client, "prompt", "", "fake-key")
    assert result == "Hello world"
    print("[OK] test_gemini_success")


# --- Test 5: <think> strips reasoning ---
async def test_think_strip():
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.raise_for_status = MagicMock()
    fake_response.json = MagicMock(return_value={
        "candidates": [{"content": {"parts": [{"text": "<think>reasoning</think>\nReal answer"}]}}]
    })
    
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(return_value=fake_response)
    
    result = await _call_gemini(fake_client, "prompt", "", "fake-key")
    assert result == "Real answer"
    assert "<think>" not in result
    print("[OK] test_think_strip")


async def run_all():
    await test_empty_api_key_returns_fallback()
    await test_gemini_success()
    await test_think_strip()
    await test_429_triggers_5min_wait()
    await test_429_persists_raises()
    print("\nALL LEVEL 2 TESTS PASSED!")


if __name__ == "__main__":
    asyncio.run(run_all())
