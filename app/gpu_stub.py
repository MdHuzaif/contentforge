"""Dummy GPU function to satisfy Hugging Face ZeroGPU requirements.

HF ZeroGPU hardware expects at least one @spaces.GPU decorated function.
Our app uses external APIs (Gemini, Cloudflare) and doesn't need GPU,
but without this decorator HF keeps restarting the Space.

This module provides a no-op GPU function that satisfies the check
without consuming GPU quota.
"""
from __future__ import annotations

import os
from app.config import logger

# Only import spaces on HF (avoids errors locally)
_on_hf = bool(os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID"))

if _on_hf:
    try:
        import spaces

        @spaces.GPU(duration=30)
        def gpu_heartbeat(dummy_input: str = "ping") -> str:
            """No-op GPU function to satisfy HF ZeroGPU check.
            
            Never actually called by the UI. Exists only to prevent
            'No @spaces.GPU function detected' restart loop.
            """
            return "pong"

        logger.info("✅ GPU heartbeat stub registered (HF ZeroGPU mode)")
    except ImportError:
        logger.warning("⚠️ spaces package not available, GPU stub skipped")
else:
    # Local dev - no decorator needed
    def gpu_heartbeat(dummy_input: str = "ping") -> str:
        return "pong"
