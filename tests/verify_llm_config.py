"""Verification script for config/llm_config.py."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    from config.llm_config import (
        PROVIDERS,
        TASK_ROUTING,
        TOKEN_BUDGET,
        get_task_config,
        get_model_for_task,
        get_fallback_chain,
    )
    
    assert "gemini" in PROVIDERS
    assert "groq" not in PROVIDERS
    assert "openrouter" not in PROVIDERS
    assert "blog_writing" in TASK_ROUTING
    assert get_fallback_chain() == ["gemini"]
    assert get_task_config("blog_writing")["provider"] == "gemini"
    assert "gemini" in TOKEN_BUDGET
    
    print("[OK] config/llm_config.py verified — Gemini-only!")


if __name__ == "__main__":
    main()
