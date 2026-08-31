"""Routing functions for the interactive 4-phase graph."""
from __future__ import annotations

from typing import Literal

from app.config import logger
from core.state import ContentForgeState


def route_from_start(state: ContentForgeState) -> Literal["data_gathering", "end"]:
    """Route from START based on current_phase."""
    phase = state.get("current_phase", "idle")
    
    if phase == "idle":
        logger.info("Routing from START to data_gathering (Phase 1).")
        return "data_gathering"
    
    logger.info("Routing from START to end (already started or complete).")
    return "end"


def route_from_data_gathering(state: ContentForgeState) -> Literal["subprompt_generator", "end"]:
    """Route from data_gathering to prompt_generation."""
    research_status = state.get("research_status", "pending")
    
    if research_status == "completed":
        logger.info("Routing from data_gathering to subprompt_generator (Phase 2).")
        return "subprompt_generator"
    
    logger.warning("Data gathering incomplete, routing to end.")
    return "end"


def route_from_prompt_generation(state: ContentForgeState) -> Literal["section_writer", "end"]:
    """Route from prompt_generation to execution."""
    prompt_status = state.get("prompt_generation_status", "pending")
    
    if prompt_status == "completed":
        logger.info("Routing from prompt_generation to section_writer (Phase 3).")
        return "section_writer"
    
    logger.warning("Prompt generation incomplete, routing to end.")
    return "end"


def route_from_execution(state: ContentForgeState) -> Literal["section_writer", "blog_assembler", "end"]:
    """Route from section_writer based on progress."""
    current_idx = state.get("current_section_index", 0)
    total = state.get("total_sections", 0)
    
    if current_idx < total:
        # More sections to write, loop back
        logger.info(f"Routing from section_writer back to section_writer (section {current_idx + 1}/{total}).")
        return "section_writer"
    
    # All sections done, go to assembly
    logger.info("All sections complete, routing to blog_assembler (Phase 4).")
    return "blog_assembler"
