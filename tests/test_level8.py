"""Comprehensive test suite for Level 8 Content Planning Agent and SOP RAG system."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.sop_rag.sop_indexer import initialize_sop_index, index_sop_documents
from backend.sop_rag.sop_retriever import retrieve_sop_context
from core.prompts.planning_prompt import PLANNING_SYSTEM_PROMPT
from core.agents.planning_agent import generate_content_plan
from core.graph import planning_node
from core.state import create_initial_state


def test_planning_prompt_exists():
    """Verify PLANNING_SYSTEM_PROMPT exists and contains key terms."""
    assert PLANNING_SYSTEM_PROMPT is not None
    assert isinstance(PLANNING_SYSTEM_PROMPT, str)
    assert len(PLANNING_SYSTEM_PROMPT) > 200
    assert "outline" in PLANNING_SYSTEM_PROMPT.lower()
    assert "seo" in PLANNING_SYSTEM_PROMPT.lower()
    assert "sop" in PLANNING_SYSTEM_PROMPT.lower()
    print("[OK] test_planning_prompt_exists passed")


def test_sop_indexer_and_retriever():
    """Verify SOP Indexer and Retriever run without errors and retrieve context."""
    async def run_test():
        await initialize_sop_index()
        await index_sop_documents()
        context = await retrieve_sop_context("blog writing best practices SEO rules")
        assert context is not None
        assert isinstance(context, str)
        assert len(context) > 50
        assert "SOP" in context or "Guideline" in context or "SEO" in context
        print("[OK] test_sop_indexer_and_retriever passed")

    asyncio.run(run_test())


def test_planning_agent_fallback():
    """Verify planning agent generates plan (or fallback) successfully."""
    async def run_test():
        plan = await generate_content_plan("Artificial Intelligence Trends 2026", "SOP Context Guidelines: Follow SEO rules.")
        assert plan is not None
        assert isinstance(plan, str)
        assert len(plan) > 100
        assert "Artificial Intelligence Trends 2026" in plan or "Outline" in plan
        print("[OK] test_planning_agent_fallback passed")

    asyncio.run(run_test())


def test_planning_node():
    """Mock LLMRouter and SOP retriever, run planning_node, and verify pending_agent_output."""
    async def run_test():
        state = create_initial_state("Python Async Programming")

        with patch("core.agents.planning_agent.LLMRouter") as mock_router_class, \
             patch("core.graph.retrieve_sop_context", new_callable=AsyncMock) as mock_retrieve:

            mock_router = mock_router_class.return_value
            mock_router.generate_text = AsyncMock(return_value="# Content Plan: Python Async Programming\n- Audience: Devs\n- SEO: Async Python")
            mock_retrieve.return_value = "Mocked SOP guidelines for python async."

            result_state = await planning_node(state)

            assert "content_pipeline_steps" in result_state
            assert result_state["pending_agent_name"] == "planning_agent"
            assert "outline" in result_state["pending_agent_output"]
            outline = result_state["pending_agent_output"]["outline"]
            assert "Python Async Programming" in outline
            print("[OK] test_planning_node passed")

    asyncio.run(run_test())


def main():
    test_planning_prompt_exists()
    test_sop_indexer_and_retriever()
    test_planning_agent_fallback()
    test_planning_node()
    print("LEVEL 8 VERIFIED — All tests passed. Content Planning Agent & SOP RAG integrated successfully.")


if __name__ == "__main__":
    main()
