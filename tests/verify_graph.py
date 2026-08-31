"""Verification script for the new interactive graph."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    from core.graph import build_content_graph, create_app
    
    graph = build_content_graph()
    nodes = list(graph.nodes.keys())
    
    print("Graph nodes:", nodes)
    assert "data_gathering" in nodes
    assert "subprompt_generator" in nodes
    assert "section_writer" in nodes
    assert "blog_assembler" in nodes
    
    # Test create_app
    compiled, checkpointer, conn = await create_app()
    assert compiled is not None
    await conn.close()
    
    print("[OK] Level 3 interactive graph verified!")


if __name__ == "__main__":
    asyncio.run(main())
