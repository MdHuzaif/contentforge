"""Subprompt generator agent for ContentForge AI."""
from __future__ import annotations

from typing import Any, Dict, List
from core.graph import _generate_product_subprompts


async def build_product_subprompts(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build product recommendation sub-prompts including deep dive data."""
    return _generate_product_subprompts(state)
