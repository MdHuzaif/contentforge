"""Interactive step-by-step graph for ContentForge AI."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from langgraph.graph import END, START, StateGraph

from app.config import logger
from backend.llm.router import FALLBACK_MESSAGE, LLMRouter
from core.prompts.subprompt_prompt import SUBPROMPT_GENERATION_SYSTEM_PROMPT
from core.prompts.section_prompt import SECTION_WRITING_SYSTEM_PROMPT
from core.prompts.context_prompt import CONTEXT_SUMMARIZATION_SYSTEM_PROMPT
from core.prompts.blog_intro_prompt import BLOG_INTRO_SYSTEM_PROMPT
from datetime import datetime
from core.routing import (
    route_from_start,
    route_from_data_gathering,
    route_from_prompt_generation,
    route_from_execution,
)
from core.state import ContentForgeState
from backend.tools.serp_scraper import get_top_results
from backend.tools.content_analyzer import fetch_and_analyze_url
from backend.tools.seo_tools import extract_markdown_headings


async def keyword_research_node(state: ContentForgeState) -> Dict[str, Any]:
    """Keyword research node performing real keyword research using LLMRouter."""
    logger.info("Executing keyword_research_node")
    user_request = state.get("user_request", "General Topic")
    topic = state.get("topic", user_request)

    response_text = ""
    try:
        router = LLMRouter()
        prompt = (
            f"Perform comprehensive SEO keyword research for the following topic/request:\n"
            f"Topic: {topic}\n\n"
            f"Please provide primary keyword, secondary/related keywords, search intent analysis, and keyword difficulty. "
            f"Return the response in JSON format with a 'keywords' list of objects containing 'keyword', 'intent', and 'difficulty'."
        )
        response_text = await router.generate_text(
            prompt, system_prompt="You are an expert SEO keyword research assistant.", task_type="keyword_research"
        )
        response_text = response_text or ""
        response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL | re.IGNORECASE).strip()
        if not response_text or "No LLM API keys configured" in response_text or response_text == FALLBACK_MESSAGE:
            response_text = f"Keyword research analysis for {topic}: Primary keyword: {topic}, Secondary: SEO optimization, content strategy."
    except Exception as e:
        logger.warning("Keyword research LLM call failed: %s. Using fallback.", e)
        response_text = f"Fallback keyword research analysis for {topic}. Error: {e}"

    parsed_keywords = []
    try:
        clean_json = response_text
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0].strip()
        data = json.loads(clean_json)
        if isinstance(data, dict):
            raw_kw = data.get("keywords", [])
            if isinstance(raw_kw, list):
                for item in raw_kw:
                    if isinstance(item, dict) and "keyword" in item:
                        parsed_keywords.append(item)
                    elif isinstance(item, str):
                        parsed_keywords.append({"keyword": item, "intent": "Informational", "difficulty": "Medium"})
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "keyword" in item:
                    parsed_keywords.append(item)
                elif isinstance(item, str):
                    parsed_keywords.append({"keyword": item, "intent": "Informational", "difficulty": "Medium"})
    except Exception as e:
        logger.debug("Could not parse JSON keywords from keyword research response: %s", e)

    if not parsed_keywords:
        parsed_keywords = [
            {"keyword": topic, "intent": "Informational", "difficulty": "Medium"},
            {"keyword": f"{topic} best practices", "intent": "Informational", "difficulty": "Medium"},
            {"keyword": f"how to {topic}", "intent": "Informational", "difficulty": "Medium"},
            {"keyword": f"{topic} examples", "intent": "Informational", "difficulty": "Medium"}
        ]

    logger.info(f"Parsed {len(parsed_keywords)} keywords from keyword research")

    return {
        "keyword_research": {
            "status": "completed",
            "topic": topic,
            "analysis": response_text,
            "keywords": parsed_keywords,  # Must be a list of dicts
        },
        "operations_count": state.get("operations_count", 0) + 1,
    }


async def competitor_analysis_node(state: ContentForgeState) -> Dict[str, Any]:
    topic = state.get("user_request", "")
    logger.info("Starting competitor analysis for topic: '%s'", topic)
    competitors: list[dict] = []
    metrics: dict = {}
    sources: list[str] = []

    # --- 1) SCRAPE (wrapped so failure never breaks pipeline) ---
    try:
        results = await get_top_results(topic, max_results=6)   # use the EXISTING helper name found in STEP 1
        logger.info("DuckDuckGo returned %d results", len(results))
        for r in results:
            url = r.get("url") or r.get("href", "")
            if not url:
                continue
            try:
                info = await fetch_and_analyze_url(url)          # existing helper: returns word_count, h2_count, h3_count, readability, title
                if info:
                    info["url"] = url
                    competitors.append(info)
                    sources.append(url)
            except Exception as e:
                logger.warning("Failed to analyze %s: %s", url, e)

        if competitors:
            n = len(competitors)
            metrics = {
                "competitor_count": n,
                "avg_word_count": round(sum(c.get("word_count", 0) for c in competitors) / n, 1),
                "avg_h2_count": round(sum(c.get("h2_count", 0) for c in competitors) / n, 1),
                "avg_h3_count": round(sum(c.get("h3_count", 0) for c in competitors) / n, 1),
                "avg_readability": round(sum(c.get("readability", 0) for c in competitors) / n, 1),
            }
    except Exception as e:
        logger.warning("Competitor scraping failed: %s. Continuing with LLM-only analysis.", e)

    # --- NEW: Extract competitor content structures ---
    competitor_structures = []
    for comp in competitors[:3]:  # Analyze top 3 competitors only
        url = comp.get("url", "")
        try:
            # Extract headings from the competitor page
            headings = comp.get("headings", {})
            content = comp.get("content", "")
            if not headings and content:
                headings = extract_markdown_headings(content)  # Use existing helper
            if not headings:
                h2_cnt = comp.get("h2_count", 0)
                headings = {"h1": [], "h2": [f"Section {i+1}" for i in range(h2_cnt)], "h3": []}

            competitor_structures.append({
                "url": url,
                "h1_count": len(headings.get("h1", [])),
                "h2_count": len(headings.get("h2", [])),
                "h3_count": len(headings.get("h3", [])),
                "h2_titles": headings.get("h2", [])[:10],  # First 10 H2s
                "section_count": len(headings.get("h2", []))
            })
            logger.info(f"Extracted structure from {url}: {len(headings.get('h2', []))} H2s")
        except Exception as e:
            logger.warning(f"Failed to extract structure from {url}: {e}")
    
    # --- NEW: LLM analyzes optimal structure ---
    content_structure = {}
    if competitor_structures:
        try:
            router = LLMRouter()
            structure_prompt = f"""Analyze these competitor content structures and recommend the optimal structure for our blog:

Topic: {topic}

Competitor Structures:
{json.dumps(competitor_structures, indent=2)}

Recommend the optimal content structure in JSON format:
{{
  "recommended_h2_count": 6,
  "section_flow": ["Introduction", "Problem/Context", "Main Solutions/Reviews", "Comparison", "Buying Guide/How-to", "FAQ", "Conclusion"],
  "avg_h3_per_section": 3,
  "content_pattern": "Problem → Solutions → Comparison → Action",
  "rationale": "Brief explanation of why this structure works"
}}

Output ONLY valid JSON, no markdown code blocks."""
            
            structure_response = await router.generate_text(
                structure_prompt,
                system_prompt="You are an expert content strategist who analyzes blog structures.",
                task_type="competitor_analysis"
            )
            
            # Parse JSON
            if structure_response:
                structure_clean = structure_response.replace("```json", "").replace("```", "").strip()
                try:
                    content_structure = json.loads(structure_clean)
                    logger.info(f"Optimal structure: {content_structure.get('recommended_h2_count')} sections")
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse structure JSON: {e}")
        except Exception as e:
            logger.warning(f"Structure analysis failed: {e}. Using default structure.")
    
    # Default structure if analysis failed
    if not content_structure:
        content_structure = {
            "recommended_h2_count": 6,
            "section_flow": ["Introduction", "Background", "Main Content", "Comparison", "Practical Tips", "Conclusion"],
            "avg_h3_per_section": 3,
            "content_pattern": "Standard blog structure",
            "rationale": "Default structure"
        }

    # --- EXISTING: LLM gap analysis (now includes structure) ---
    try:
        router = LLMRouter()
        prompt = f"""Topic: {topic}

Scraped competitor metrics: {metrics}
Competitor pages: {sources}
Optimal content structure: {json.dumps(content_structure)}

Provide a comprehensive SEO competitor analysis and content gap blueprint."""
        analysis_text = await router.generate_text(
            prompt, system_prompt="You are an expert SEO competitor analyst.", task_type="competitor_analysis"
        )
    except Exception as e:
        logger.warning("Competitor LLM analysis failed: %s. Using fallback.", e)
        analysis_text = f"Fallback competitor analysis for {topic}."

    return {
        "competitor_analysis": {
            "status": "completed",
            "topic": topic,
            "competitors": competitors,
            "metrics": metrics,
            "gap_analysis": analysis_text,
            "sources": sources,
        },
        "content_structure": content_structure,  # NEW: Save structure to state
        "operations_count": state.get("operations_count", 0) + 1,
    }


async def data_gathering_node(state: ContentForgeState) -> Dict[str, Any]:
    """Phase 1: Run keyword research and competitor analysis."""
    logger.info("Executing data_gathering_node (Phase 1)")
    
    # Run keyword research
    kw_result = await keyword_research_node(state)
    
    # Temporarily update state with keyword research for competitor analysis
    temp_state = {**state, **kw_result}
    
    # Run competitor analysis
    comp_result = await competitor_analysis_node(temp_state)
    
    # Merge results and update phase
    return {
        **kw_result,
        **comp_result,
        "current_phase": "prompt_generation",
        "research_status": "completed",
    }


async def subprompt_generator_node(state: ContentForgeState) -> Dict[str, Any]:
    """Phase 2: Generate section sub-prompts based on research and optimal structure."""
    logger.info("Executing subprompt_generator_node (Phase 2)")
    
    topic = state.get("user_request", "General Topic")
    keyword_data = state.get("keyword_research", {})
    competitor_data = state.get("competitor_analysis", {})
    content_structure = state.get("content_structure", {})  # NEW: Get structure
    
    # --- NEW: Calculate dynamic word count target ---
    metrics = competitor_data.get("metrics", {})
    competitor_avg_wc = metrics.get("avg_word_count", 0)
    
    if competitor_avg_wc and competitor_avg_wc > 0:
        # Target: 10-50% more than competitor average
        target_min = int(competitor_avg_wc * 1.1)
        target_max = int(competitor_avg_wc * 1.5)
        # Ensure minimum 3000, maximum 4000
        target_min = max(target_min, 3000)
        target_max = max(target_max, 4000)
        target_range = f"{target_min}-{target_max}"
        logger.info(f"Dynamic word target: {target_range} (based on competitor avg {competitor_avg_wc})")
    else:
        # Fallback: 3000-4000 words if no competitor data
        target_range = "3000-4000"
        logger.info("No competitor data, using fallback target: 3000-4000 words")
    
    # Build enhanced context with dynamic target
    research_context = f"""
TOPIC: {topic}

KEYWORD RESEARCH SUMMARY:
{json.dumps(keyword_data, indent=2, default=str)}

COMPETITOR ANALYSIS SUMMARY:
{json.dumps(competitor_data, indent=2, default=str)}

OPTIMAL CONTENT STRUCTURE (MUST FOLLOW):
{json.dumps(content_structure, indent=2, default=str)}

TARGET WORD COUNT (CRITICAL):
Total blog should be {target_range} words.
Each section should be 500-2000 words. YOU decide the ideal count per section based on content depth.

Based on this research, generate approximately {content_structure.get('recommended_h2_count', 6)} section sub-prompts 
(aim for this number, but you may add 1-2 more sections if the topic requires deeper coverage, 
or combine sections if the topic is simpler) 
following the recommended section flow: {', '.join(content_structure.get('section_flow', []))}.

Each section should have approximately {content_structure.get('avg_h3_per_section', 3)} subsections (H3s).
"""
    
    try:
        router = LLMRouter()
        response = await router.generate_text(
            prompt=research_context,
            system_prompt=SUBPROMPT_GENERATION_SYSTEM_PROMPT,
            task_type="subprompt_generation",
        )
        
        # Parse JSON response
        if response.startswith("```json"):
            response = response[7:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()
        
        data = json.loads(response)
        sub_prompts = data.get("sections", [])
        
        for prompt in sub_prompts:
            prompt["status"] = "pending"
        
        logger.info(f"Generated {len(sub_prompts)} sub-prompts following optimal structure")
        
        return {
            "sub_prompts": sub_prompts,
            "total_sections": len(sub_prompts),
            "current_phase": "execution",
            "prompt_generation_status": "completed",
        }
    except Exception as e:
        logger.error(f"Subprompt generation failed: {e}")
        # Fallback with structure-based prompts
        fallback_prompts = []
        for i, section_name in enumerate(content_structure.get("section_flow", ["Introduction", "Main Content", "Conclusion"])[:6]):
            fallback_prompts.append({
                "id": i,
                "title": section_name,
                "prompt": f"Write a comprehensive section about {section_name} for {topic}",
                "word_target": 600,
                "key_points": [f"Cover {section_name} thoroughly"],
                "status": "pending"
            })
        
        return {
            "sub_prompts": fallback_prompts,
            "total_sections": len(fallback_prompts),
            "current_phase": "execution",
            "prompt_generation_status": "completed",
        }


async def section_writer_node(state: ContentForgeState) -> Dict[str, Any]:
    """Phase 3: Write one section with accumulated context and update context for next section."""
    logger.info("Executing section_writer_node (Phase 3)")
    
    current_idx = state.get("current_section_index", 0)
    total = state.get("total_sections", 0)
    sub_prompts = state.get("sub_prompts", [])
    section_contexts = state.get("section_contexts", [])
    topic = state.get("user_request", "General Topic")
    
    if current_idx >= total:
        logger.warning("All sections already written, moving to assembly")
        return {
            "current_phase": "assembly",
        }
    
    current_prompt = sub_prompts[current_idx]
    
    # Build accumulated context from previous sections
    if section_contexts:
        accumulated_context = "\n\n--- Previous Sections Summary ---\n"
        for i, ctx in enumerate(section_contexts):
            accumulated_context += f"\nSection {i+1} Summary:\n{ctx}\n"
    else:
        accumulated_context = "\n(This is the first section, no previous context yet)\n"
    
    # --- Extract SEO research data from state ---
    keyword_data = state.get("keyword_research", {}) or {}
    competitor_data = state.get("competitor_analysis", {}) or {}

    keywords_list = keyword_data.get("keywords", []) or []
    primary_keyword = topic
    secondary_keywords: list[str] = []
    for kw in keywords_list:
        if isinstance(kw, dict):
            k = str(kw.get("keyword", "")).replace("`", "").strip()
        else:
            k = str(kw).replace("`", "").strip()
        if not k or k.endswith(":"):
            continue
        if primary_keyword == topic:
            primary_keyword = k
        elif k.lower() != primary_keyword.lower() and len(secondary_keywords) < 8:
            secondary_keywords.append(k)

    gap_analysis = str(competitor_data.get("gap_analysis", "") or "")
    gap_summary = gap_analysis[:1500] if gap_analysis else "No gap analysis available."
    metrics = competitor_data.get("metrics", {}) or {}
    competitor_benchmarks = (
        ", ".join(f"{k}: {v}" for k, v in metrics.items())
        if metrics else "No competitor metrics available."
    )

    logger.info(
        "Section %d/%d using primary keyword: '%s' + %d secondary keywords",
        current_idx + 1, total, primary_keyword, len(secondary_keywords),
    )

    # Smart exact-keyword placement across the whole article (anti-stuffing)
    if current_idx == 0:
        placement_hint = ("This is the INTRODUCTION: include the exact primary keyword ONCE "
                          "within the first 100 words.")
    elif current_idx == total - 1:
        placement_hint = ("This is the CONCLUSION: you may include the exact primary keyword "
                          "ONCE, naturally.")
    else:
        placement_hint = ("This is a MIDDLE section: prefer semantic variations; use the exact "
                          "primary keyword only if it fits 100% naturally (max once).")

    section_prompt_text = f"""
TOPIC: {topic}

=== SEO RESEARCH DATA (weave in naturally; never mention this block to the reader) ===
PRIMARY KEYWORD: {primary_keyword}
SECONDARY KEYWORDS: {', '.join(secondary_keywords) or 'None'}
GAP ANALYSIS INSIGHTS: {gap_summary}
COMPETITOR BENCHMARKS: {competitor_benchmarks}

CURRENT SECTION DETAILS:
- Section Number: {current_idx + 1} of {total}
- Title: {current_prompt.get('title', 'Untitled Section')}
- Target Word Count: {current_prompt.get('word_target', 600)} words
- Key Points to Cover: {', '.join(current_prompt.get('key_points', []))}
- Detailed Instructions: {current_prompt.get('prompt', 'Write this section')}

{accumulated_context}

⚠️ MANDATORY ENGAGEMENT CHECKLIST FOR THIS SECTION:
Before finishing this section, verify you have included:
- [ ] A strong hook (question/stat) in the first 2 sentences?
- [ ] At least one "In my testing..." or similar first-person experience phrase? (Or "From my experience explaining this concept..." if educational/definitional)
- [ ] At least one Markdown table OR bulleted/numbered list?
- [ ] At least one `> **💡 Quick Tip:** ...` blockquote callout?
If any of these are missing, the section will be rejected. Ensure they are naturally integrated.

--- YOUR TASK ---
Write Section {current_idx + 1} following the instructions above. Remember to:
- Use the EXACT primary keyword AT MOST ONCE in this section (first 100 words or a heading); for all other mentions use natural semantic variations (synonyms, rephrasings, partial matches). Include 1-2 SECONDARY KEYWORDS only where they fit naturally.
- {placement_hint}
- Address at least one gap or weakness identified in GAP ANALYSIS INSIGHTS to beat competitors
- Match or exceed the COMPETITOR BENCHMARKS (depth, structure, readability)
- Maintain flow from previous sections (use the context provided)
- Hit the target word count (500-2000 words as specified in the prompt)
- Include all key points naturally
- Use engaging, professional tone
"""
    
    # Call Gemini to generate the section
    try:
        router = LLMRouter()
        
        logger.info(f"Generating section {current_idx + 1}/{total}: {current_prompt.get('title')}")
        section_content = await router.generate_text(
            prompt=section_prompt_text,
            system_prompt=SECTION_WRITING_SYSTEM_PROMPT,
            task_type="section_writing",
        )
        
        # Count words (rough estimate)
        word_count = len(section_content.split())
        logger.info(f"Section {current_idx + 1} generated: {word_count} words")
        
        # Now summarize this section for future context
        logger.info(f"Summarizing section {current_idx + 1} for context")
        context_summary = await router.generate_text(
            prompt=f"Summarize this blog section for context:\n\n{section_content}",
            system_prompt=CONTEXT_SUMMARIZATION_SYSTEM_PROMPT,
            task_type="context_summarization",
        )
        
        # Update state
        generated_sections = state.get("generated_sections", [])
        generated_sections.append({
            "id": current_idx,
            "title": current_prompt.get("title", f"Section {current_idx + 1}"),
            "content": section_content,
            "word_count": word_count,
            "timestamp": datetime.now().isoformat(),
            "status": "completed",
        })
        
        new_contexts = section_contexts + [context_summary]
        next_idx = current_idx + 1
        
        # Determine next phase
        if next_idx >= total:
            new_phase = "assembly"
            logger.info("All sections complete, moving to assembly phase")
        else:
            new_phase = "execution"
            logger.info(f"Moving to section {next_idx + 1}/{total}")
        
        return {
            "current_section_index": next_idx,
            "generated_sections": generated_sections,
            "section_contexts": new_contexts,
            "current_phase": new_phase,
            "operations_count": state.get("operations_count", 0) + 2,  # 2 LLM calls
        }
        
    except Exception as e:
        logger.error(f"Section {current_idx + 1} generation failed: {e}")
        
        # Fallback: generate placeholder content
        fallback_content = f"""## {current_prompt.get('title', f'Section {current_idx + 1}')}

This is placeholder content for section {current_idx + 1} of {total}.

### Key Points:
{chr(10).join(['- ' + point for point in current_prompt.get('key_points', ['Point 1', 'Point 2'])])}

### Main Content:
The actual content generation encountered an issue. This placeholder ensures the blog structure remains intact.

*Detailed content would cover: {current_prompt.get('prompt', 'Section topic')}*

### Summary:
This section would normally provide comprehensive coverage of the topic with examples, statistics, and actionable insights.
"""
        
        fallback_summary = f"Section {current_idx + 1} covered {current_prompt.get('title', 'topic')} with placeholder content due to generation error."
        
        generated_sections = state.get("generated_sections", [])
        generated_sections.append({
            "id": current_idx,
            "title": current_prompt.get("title", f"Section {current_idx + 1}"),
            "content": fallback_content,
            "word_count": 150,
            "timestamp": datetime.now().isoformat(),
            "status": "failed",
        })
        
        new_contexts = section_contexts + [fallback_summary]
        next_idx = current_idx + 1
        
        if next_idx >= total:
            new_phase = "assembly"
        else:
            new_phase = "execution"
        
        return {
            "current_section_index": next_idx,
            "generated_sections": generated_sections,
            "section_contexts": new_contexts,
            "current_phase": new_phase,
            "operations_count": state.get("operations_count", 0) + 1,
        }


async def blog_assembler_node(state: ContentForgeState) -> Dict[str, Any]:
    """Phase 4: Assemble all sections into a professional, publish-ready blog post."""
    logger.info("Executing blog_assembler_node (Phase 4)")
    
    sections = state.get("generated_sections", [])
    topic = state.get("user_request", "General Topic")
    
    if not sections:
        logger.warning("No sections to assemble, returning empty blog")
        return {
            "assembled_blog": f"# {topic}\n\n*No content generated.*",
            "current_phase": "complete",
            "assembly_status": "failed",
        }
    
    # Calculate statistics
    total_words = sum(s.get("word_count", 0) for s in sections)
    reading_time_minutes = max(1, round(total_words / 250))  # ~250 words per minute
    generation_date = datetime.now().strftime("%B %d, %Y")
    section_count = len(sections)
    
    logger.info(f"Assembling blog: {section_count} sections, {total_words} words, ~{reading_time_minutes} min read")
    
    # Generate intro paragraph using LLM
    intro_paragraph = ""
    try:
        router = LLMRouter()
        section_titles = [s.get("title", f"Section {i+1}") for i, s in enumerate(sections)]
        intro_prompt = f"""TOPIC: {topic}

SECTION TITLES IN ORDER:
{chr(10).join([f'{i+1}. {title}' for i, title in enumerate(section_titles)])}

Write an engaging introduction paragraph (150-250 words) that hooks the reader and previews what they will learn.
"""
        
        intro_paragraph = await router.generate_text(
            prompt=intro_prompt,
            system_prompt=BLOG_INTRO_SYSTEM_PROMPT,
            task_type="blog_writing",
        )
        logger.info(f"Generated intro paragraph: {len(intro_paragraph.split())} words")
    except Exception as e:
        logger.warning(f"Intro generation failed: {e}. Using fallback.")
        intro_paragraph = f"In this comprehensive guide, we explore {topic} in depth. This article covers {section_count} key aspects, providing you with actionable insights and practical knowledge to master this subject."
    
    # Build the blog post
    blog_parts = []
    
    # 1. H1 Title
    blog_parts.append(f"# {topic.title()}\n\n")
    
    # 2. Introduction paragraph
    blog_parts.append(f"{intro_paragraph}\n\n")
    
    # 3. All sections with proper formatting
    for i, section in enumerate(sections, start=1):
        title = section.get("title", f"Section {i}")
        content = section.get("content", "")
        
        # Add section header with H2
        blog_parts.append(f"## {i}. {title}\n\n")
        
        # Add section content (ensure it doesn't have duplicate H2)
        if content.startswith("## "):
            content = content.split("\n", 1)[-1].lstrip()
        
        blog_parts.append(f"{content}\n\n")
        
        # Add separator (except for last section)
        if i < len(sections):
            blog_parts.append("---\n\n")
    
    # Join everything
    assembled_blog = "".join(blog_parts)
    
    logger.info(f"Blog assembly complete: {len(assembled_blog)} characters")
    
    return {
        "assembled_blog": assembled_blog,
        "current_phase": "complete",
        "assembly_status": "complete",
        "operations_count": state.get("operations_count", 0) + 1,
    }


def build_content_graph() -> StateGraph:
    """Build the interactive 4-phase content generation graph."""
    workflow = StateGraph(ContentForgeState)
    
    # Add nodes
    workflow.add_node("data_gathering", data_gathering_node)
    workflow.add_node("subprompt_generator", subprompt_generator_node)
    workflow.add_node("section_writer", section_writer_node)
    workflow.add_node("blog_assembler", blog_assembler_node)
    
    # Add edges
    workflow.add_conditional_edges(
        START,
        route_from_start,
        {
            "data_gathering": "data_gathering",
            "end": END,
        },
    )
    
    workflow.add_conditional_edges(
        "data_gathering",
        route_from_data_gathering,
        {
            "subprompt_generator": "subprompt_generator",
            "end": END,
        },
    )
    
    workflow.add_conditional_edges(
        "subprompt_generator",
        route_from_prompt_generation,
        {
            "section_writer": "section_writer",
            "end": END,
        },
    )
    
    workflow.add_conditional_edges(
        "section_writer",
        route_from_execution,
        {
            "section_writer": "section_writer",  # Loop back for next section
            "blog_assembler": "blog_assembler",
            "end": END,
        },
    )
    
    workflow.add_edge("blog_assembler", END)
    
    return workflow


async def create_app():
    """Create and compile the graph with checkpointer."""
    from backend.memory.sqlite_manager import create_async_checkpointer
    
    checkpointer, conn = await create_async_checkpointer()
    graph = build_content_graph()
    compiled = graph.compile(checkpointer=checkpointer)
    
    logger.info("ContentForge AI interactive graph built and compiled successfully.")
    return compiled, checkpointer, conn
