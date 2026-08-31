"""LLM provider configurations, task-based routing, and token budget rules for ContentForge AI."""
from __future__ import annotations

from typing import Any, Dict, List

PROVIDERS = {
    "gemini": {
        "models": {
            "default": "gemini-3.5-flash-lite",
            "pro": "gemini-3.5-flash-lite",
        }
    }
}  # only Gemini now

TASK_ROUTING: Dict[str, Any] = {
    "blog_writing": {
        "description": "Long-form blog content generation",
        "preferred_providers": ["gemini"],
        "fallback_chain": ["gemini"],
        "model_preference": "default",
        "max_tokens": 8000,
        "temperature": 0.7,
    },
    "section_writing": {
        "description": "Individual blog section generation with context",
        "preferred_providers": ["gemini"],
        "fallback_chain": ["gemini"],
        "model_preference": "default",
        "max_tokens": 8000,
        "temperature": 0.7,
    },
    "default": "gemini",
    "keyword_research": "gemini",
    "competitor_analysis": "gemini",
    "subprompt_generation": "gemini",
    "context_summarization": "gemini",
    "report": "gemini",
    "outline_generation": "gemini",
    "seo_analysis": "gemini",
    "classification": "gemini",
    "summarization": "gemini",
}

# Default Gemini model per task (can be overridden via state["gemini_model"])
TASK_MODELS = {
    "default": "gemini-3.5-flash-lite",
    "subprompt_generation": "gemini-3.5-flash-lite",
    "section_writing": "gemini-3.5-flash-lite",
    "blog_writing": "gemini-3.5-flash-lite",
    "context_summarization": "gemini-3.5-flash-lite",
}

TOKEN_BUDGET = {
    "gemini": {
        "per_request": 65536,        # Increased from 8192 to 65536 (64K tokens)
        "daily_limit": 1500,         # Keep as is (Gemini free tier limit)
        "max_input_tokens": 1048576, # Gemini's actual max input
        "max_output_tokens": 8192,   # Gemini's default max output
    },
    "monthly_limit": 500000,
    "per_task_limit": 100000,        # Increased from 50000 to 100000
    "per_request_limit": 65536,      # Match per_request
    "warning_threshold": 0.8,
}


def get_task_config(task_type: str) -> dict:
    cfg = TASK_ROUTING.get(task_type, TASK_ROUTING["default"])
    if isinstance(cfg, dict):
        return {
            "provider": cfg.get("preferred_providers", ["gemini"])[0],
            "model": TASK_MODELS.get(task_type, TASK_MODELS["default"]),
            "max_tokens": cfg.get("max_tokens", 8000),
            "temperature": cfg.get("temperature", 0.7),
        }
    return {
        "provider": "gemini",
        "model": TASK_MODELS.get(task_type, TASK_MODELS["default"]),
        "max_tokens": 8000,
        "temperature": 0.7,
    }


def get_model_for_task(task_type: str, provider: str = "gemini") -> str:
    return TASK_MODELS.get(task_type, TASK_MODELS["default"])


def get_fallback_chain(task_type: str = "default") -> list[str]:
    """DEPRECATED: fallback chain no longer exists. Returns single-element list for compat."""
    return ["gemini"]
