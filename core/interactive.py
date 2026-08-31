"""Interactive session layer: drives the 4-phase graph step-by-step with LangGraph interrupts."""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from app.config import logger
from backend.memory.sqlite_manager import create_async_checkpointer
from core.graph import build_content_graph
from core.state import create_initial_state

# Pause points: after each of these nodes, the graph waits for the next user action
INTERRUPT_AFTER = ["data_gathering", "subprompt_generator", "section_writer"]


class InteractiveSession:
    """Wraps the compiled graph so the UI can advance one phase per button click."""

    def __init__(self) -> None:
        self.graph = None
        self.checkpointer = None
        self.conn = None

    async def initialize(self) -> None:
        self.checkpointer, self.conn = await create_async_checkpointer()
        workflow = build_content_graph()
        self.graph = workflow.compile(
            checkpointer=self.checkpointer,
            interrupt_after=INTERRUPT_AFTER,
        )
        logger.info("InteractiveSession initialized (interrupt_after=%s)", INTERRUPT_AFTER)

    async def close(self) -> None:
        if self.conn is not None:
            await self.conn.close()

    def _config(self, thread_id: str) -> Dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    async def get_state(self, thread_id: str) -> Dict[str, Any]:
        """Return current state values and the next node(s) to run."""
        snapshot = await self.graph.aget_state(self._config(thread_id))
        return {
            "values": dict(snapshot.values or {}),
            "next": tuple(snapshot.next or ()),
        }

    async def _require_started(self, thread_id: str) -> Dict[str, Any]:
        snap = await self.get_state(thread_id)
        if not snap["values"]:
            raise ValueError("No session found. Run research first.")
        return snap

    async def start_research(self, topic: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """Phase 1: run data_gathering, then pause."""
        if self.graph is None:
            await self.initialize()
        thread_id = thread_id or str(uuid.uuid4())
        initial = create_initial_state(topic, thread_id=thread_id)
        await self.graph.ainvoke(initial, self._config(thread_id))
        
        # Verify state was actually saved
        snap = await self.get_state(thread_id)
        if not snap["values"]:
            logger.error(f"State was not saved to SQLite for thread {thread_id}!")
            raise ValueError("Failed to save research state. Please try again.")
        
        logger.info(f"Phase 1 complete for thread {thread_id}")
        return {
            "thread_id": thread_id,
            "keyword_research": snap["values"].get("keyword_research", {}),
            "competitor_analysis": snap["values"].get("competitor_analysis", {}),
            "next": snap["next"],
        }

    async def generate_prompts(self, thread_id: str) -> Dict[str, Any]:
        """Phase 2: run subprompt_generator, then pause."""
        await self._require_started(thread_id)
        await self.graph.ainvoke(None, self._config(thread_id))
        snap = await self.get_state(thread_id)
        values = snap["values"]
        logger.info("Phase 2 complete: %s sub-prompts", values.get("total_sections", 0))
        return {
            "sub_prompts": values.get("sub_prompts", []),
            "total_sections": values.get("total_sections", 0),
            "section_contexts": values.get("section_contexts", []),
            "next": snap["next"],
        }

    async def execute_next_section(self, thread_id: str) -> Dict[str, Any]:
        """Phase 3: run ONE section_writer iteration, then pause."""
        await self._require_started(thread_id)
        await self.graph.ainvoke(None, self._config(thread_id))
        snap = await self.get_state(thread_id)
        values = snap["values"]
        logger.info(
            "Section %s/%s complete",
            values.get("current_section_index", 0), values.get("total_sections", 0),
        )
        return {
            "current_section_index": values.get("current_section_index", 0),
            "total_sections": values.get("total_sections", 0),
            "generated_sections": values.get("generated_sections", []),
            "section_contexts": values.get("section_contexts", []),
            "next": snap["next"],
        }

    async def assemble_blog(self, thread_id: str) -> Dict[str, Any]:
        """Phase 4: run blog_assembler to END."""
        await self._require_started(thread_id)
        await self.graph.ainvoke(None, self._config(thread_id))
        snap = await self.get_state(thread_id)
        values = snap["values"]
        logger.info("Assembly complete for thread %s", thread_id)
        return {
            "assembled_blog": values.get("assembled_blog", ""),
            "assembly_status": values.get("assembly_status", ""),
            "next": snap["next"],
        }
