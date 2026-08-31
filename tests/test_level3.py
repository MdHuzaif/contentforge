"""Level 3 test suite for the new interactive 4-phase graph."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.graph import build_content_graph, create_app
from core.state import ContentForgeState, create_initial_state
from core.routing import (
    route_from_start,
    route_from_data_gathering,
    route_from_prompt_generation,
    route_from_execution,
)


def test_state_creation():
    state = create_initial_state("test topic")
    assert state["user_request"] == "test topic"
    assert state["current_phase"] == "idle"
    print("[OK] test_state_creation passed")


def test_graph_structure():
    graph = build_content_graph()
    nodes = list(graph.nodes.keys())
    
    expected_nodes = [
        "data_gathering",
        "subprompt_generator",
        "section_writer",
        "blog_assembler",
    ]
    
    for node in expected_nodes:
        assert node in nodes, f"Missing node: {node}"
    
    print(f"[OK] test_graph_structure passed with {len(nodes)} nodes")


def test_routing_functions():
    state = create_initial_state("test")
    
    # Test route_from_start
    assert route_from_start(state) == "data_gathering"
    
    # Test route_from_data_gathering
    state["research_status"] = "completed"
    assert route_from_data_gathering(state) == "subprompt_generator"
    
    # Test route_from_prompt_generation
    state["prompt_generation_status"] = "completed"
    assert route_from_prompt_generation(state) == "section_writer"
    
    # Test route_from_execution (loop)
    state["current_section_index"] = 0
    state["total_sections"] = 5
    assert route_from_execution(state) == "section_writer"
    
    # Test route_from_execution (done)
    state["current_section_index"] = 5
    assert route_from_execution(state) == "blog_assembler"
    
    print("[OK] test_routing_functions passed")


async def test_graph_execution():
    graph, checkpointer, conn = await create_app()
    
    initial_state = create_initial_state("test topic", thread_id="test_level3")
    config = {"configurable": {"thread_id": "test_level3"}}
    
    events_count = 0
    async for event in graph.astream(initial_state, config=config):
        events_count += 1
        if events_count > 20:  # Safety limit
            break
    
    assert events_count > 0, "Graph execution produced no events"
    print(f"[OK] test_graph_execution passed with {events_count} events")
    
    await conn.close()


def main():
    test_state_creation()
    test_graph_structure()
    test_routing_functions()
    asyncio.run(test_graph_execution())
    print("\nALL LEVEL 3 TESTS PASSED!")


if __name__ == "__main__":
    main()
