from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class ContentForgeState(TypedDict, total=False):
    """State schema for the interactive step-by-step ContentForge AI pipeline."""
    
    # === Metadata ===
    messages: List[Any]                    # LangGraph message history
    user_request: str                      # Original topic/keyword from user
    thread_id: str                         # Unique session ID for checkpointer
    
    # === Phase Tracking ===
    current_phase: str                     # "idle" | "data_gathering" | "prompt_generation" | "execution" | "complete"
    operations_count: int                  # Total LLM/tool operations performed
    
    # === Phase 1: Data Gathering ===
    keyword_research: Dict[str, Any]       # Output from keyword_research node
    competitor_analysis: Dict[str, Any]    # Output from competitor_analysis node
    content_structure: Dict[str, Any]      # NEW: Optimal content structure
    research_status: str                   # "pending" | "running" | "completed" | "failed"
    
    # === Phase 2: Sub-Prompt Generation ===
    sub_prompts: List[Dict[str, Any]]      # List of {id, title, prompt, word_target, status}
    total_sections: int                    # Total number of sections to generate
    prompt_generation_status: str          # "pending" | "running" | "completed"
    
    # === Phase 3: Iterative Section Execution ===
    current_section_index: int             # Which section is being executed now (0-based)
    generated_sections: List[Dict[str, Any]]  # List of {id, title, content, word_count, timestamp}
    section_contexts: List[str]            # Summaries/context of each completed section (for next section's prompt)
    
    # === Phase 4: Assembly ===
    assembled_blog: str                    # Final merged markdown blog
    assembly_status: str                   # "pending" | "assembling" | "complete"
    
    # Product Refinement System (post-processing)
    refined_blog: str
    refinement_report: str
    refinement_stats: List[Dict[str, Any]]
    
    # === Execution Config ===
    execution_mode: str                    # Always "interactive" in new architecture
    gemini_model: str                      # Which Gemini model to use (default: "gemini-3.5-flash-lite")


def create_initial_state(
    topic: str,
    thread_id: Optional[str] = None,
) -> ContentForgeState:
    """Create the initial state for a new interactive pipeline run."""
    import uuid
    
    return {
        # Metadata
        "messages": [],
        "user_request": topic.strip(),
        "thread_id": thread_id or str(uuid.uuid4()),
        
        # Phase tracking
        "current_phase": "idle",
        "operations_count": 0,
        
        # Phase 1
        "keyword_research": {},
        "competitor_analysis": {},
        "content_structure": {},
        "research_status": "pending",
        
        # Phase 2
        "sub_prompts": [],
        "total_sections": 0,
        "prompt_generation_status": "pending",
        
        # Phase 3
        "current_section_index": 0,
        "generated_sections": [],
        "section_contexts": [],
        
        # Phase 4
        "assembled_blog": "",
        "assembly_status": "pending",
        "refined_blog": "",
        "refinement_report": "",
        "refinement_stats": [],
        
        # Config
        "execution_mode": "interactive",
        "gemini_model": "gemini-3.5-flash-lite",
    }
