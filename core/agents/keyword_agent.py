"""Keyword Research Agent implementation using LangGraph prebuilt ReAct agent."""
from __future__ import annotations

from typing import Any, Optional

from langgraph.prebuilt import create_react_agent

from backend.llm.router import LLMRouter
from core.prompts.keyword_prompt import KEYWORD_RESEARCH_SYSTEM_PROMPT


def build_keyword_agent(llm: Any = None, *, pre_model_hook: Optional[Any] = None) -> Any:
    """Builds and returns the keyword research ReAct agent."""
    if llm is None:
        llm = LLMRouter()

    agent = create_react_agent(
        model=llm,
        tools=[],
        name="keyword_agent",
        prompt=KEYWORD_RESEARCH_SYSTEM_PROMPT,
        pre_model_hook=pre_model_hook,
    )
    return agent
