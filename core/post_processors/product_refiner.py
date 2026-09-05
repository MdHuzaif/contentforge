"""Refine product sections with per-product shopping signals + LLM rewrite.
Preserves blog tone by providing context. H3 headings are never changed."""
from __future__ import annotations
import asyncio
from typing import List, Dict

from app.config import logger
from backend.llm.router import LLMRouter
from backend.tools.serp_scraper import get_top_results
from backend.tools.shopping_intelligence import (
    PRAISE_WORDS, COMPLAINT_WORDS, PRICE_RE
)
from core.post_processors.product_detector import detect_product_sections

# Minimum products needed to trigger refinement
MIN_PRODUCTS_FOR_REFINEMENT = 2
MAX_PRODUCTS_FOR_REFINEMENT = 10


async def gather_product_signals(product_name: str, topic: str = "") -> Dict:
    """Fetch shopping signals for a SINGLE product (3 parallel queries)."""
    # Mix of broad and specific queries for better coverage
    queries = [
        f"site:reddit.com {product_name} review experience",  # Broad Reddit
        f"{product_name} review pros cons",                   # Broad (no quotes)
        f"{product_name} problems issues complaints",         # Problem-focused
    ]
    
    snippets: List[str] = []
    
    async def fetch_one(q: str):
        try:
            results = await get_top_results(q, max_results=4)  # More results
            return [
                (r.get("snippet") or r.get("description") or r.get("title") or "").strip()
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Product query failed ({q}): {e}")
            return []
    
    results = await asyncio.gather(*[fetch_one(q) for q in queries])
    for snips in results:
        snippets.extend([s for s in snips if s and len(s) > 10])
    
    if not snippets:
        logger.warning(f"No snippets found for product: {product_name}")
        return {"product": product_name, "praise": [], "complaints": [], "found": False}
    
    text = " ".join(snippets).lower()
    logger.info(f"Product {product_name}: {len(snippets)} snippets, {len(text)} chars")
    
    # Extract sentiment (use top 6 for more coverage)
    praise = [w for w in PRAISE_WORDS if w in text][:6]
    complaints = [w for w in COMPLAINT_WORDS if w in text][:6]
    
    logger.info(f"Product {product_name}: praise={praise}, complaints={complaints}")
    
    return {
        "product": product_name,
        "praise": praise,
        "complaints": complaints,
        "snippet_count": len(snippets),
        "found": True,
    }


REFINE_SYSTEM_PROMPT = """You are an expert product review editor enhancing existing content with real user feedback.

ABSOLUTE TONE PRESERVATION RULES:
1. Match the EXACT narrative voice: if original uses "you" address, keep "you"; if "we", keep "we"; if third-person, keep third-person
2. Preserve sentence rhythm, paragraph structure, and formality level exactly
3. Keep ALL existing keywords, SEO terms, and technical terminology intact
4. Match the original's enthusiasm level (don't make casual content formal or vice versa)
5. User feedback must read as if the ORIGINAL AUTHOR wrote it — seamless integration
6. Use meta-phrases like "users report" or "owners mention" AT MOST ONCE in the entire section
7. NEVER start sentences with "According to" or "Users say" repeatedly
8. Preserve all headings, bullet points, and formatting exactly
9. Do NOT add specific dollar prices ($X, $X.XX) — use relative terms only
10. Output ONLY the enhanced section — no explanations, no preamble, no code fences"""


async def refine_single_section(
    section: Dict,
    signals: Dict,
    blog_context: str,
) -> str:
    """Refine a single product section using LLM with blog context for tone."""
    original_content = section["content"]
    original_heading = section["heading"]
    
    praise_str = ", ".join(signals.get("praise", [])[:3]) if signals.get("praise") else ""
    complaints_str = ", ".join(signals.get("complaints", [])[:2]) if signals.get("complaints") else ""

    feedback_lines = []
    if praise_str:
        feedback_lines.append(f"What real users praise: {praise_str}")
    if complaints_str:
        feedback_lines.append(f"Common concerns mentioned: {complaints_str}")

    if not feedback_lines:
        return f"### {original_heading}\n{original_content}"  # Nothing to integrate

    feedback_block = "\n".join(f"- {line}" for line in feedback_lines)

    # Build context sample (first 600 chars of blog for tone reference)
    context_sample = blog_context[:600] if blog_context else ""

    user_prompt = f"""BLOG TONE REFERENCE (match this writing style exactly):
\"\"\"
{context_sample}
\"\"\"

SECTION TO ENHANCE:
\"\"\"
### {original_heading}
{original_content}
\"\"\"

PRODUCT: {section.get('product_name', '')}

REAL USER FEEDBACK TO INTEGRATE:
{feedback_block}

TASK: Rewrite the section naturally weaving in the user feedback while preserving:
- The exact same tone, voice, and formality
- All original facts, specs, and information
- The same paragraph structure and flow
- The ### heading unchanged

Add only 2-3 sentences of user sentiment, woven naturally into existing paragraphs.
Output ONLY the enhanced section starting with the ### heading. No code fences."""

    try:
        router = LLMRouter(task_type="section_writing")
        refined = await router.generate_text(
            prompt=user_prompt,
            system_prompt=REFINE_SYSTEM_PROMPT,
            task_type="section_writing",
        )
        
        # Clean up response
        refined = refined.strip()
        refined = refined.replace("```markdown", "").replace("```", "").strip()
        
        # Validation: ensure H3 heading is preserved
        if not refined.startswith("###"):
            refined = f"### {original_heading}\n{refined}"
        
        # Validation: ensure no dollar prices slipped in
        if PRICE_RE.search(refined):
            logger.warning("Refined section for %s contained prices, using original",
                          section['product_name'])
            return f"### {original_heading}\n{original_content}"
        
        return refined
        
    except Exception as e:
        logger.warning("LLM refinement failed for %s: %s", section.get('product_name', ''), e)
        return f"### {original_heading}\n{original_content}"


async def refine_blog_products(blog_markdown: str, topic: str = "") -> Dict:
    """Main orchestrator: detect products, fetch signals, refine sections.
    
    Returns dict with: refined_blog, sections_refined, total_products, stats, skipped, reason
    """
    sections = detect_product_sections(blog_markdown)
    
    if len(sections) < MIN_PRODUCTS_FOR_REFINEMENT:
        return {
            "refined_blog": blog_markdown,
            "sections_refined": 0,
            "total_products": len(sections),
            "skipped": True,
            "reason": f"Only {len(sections)} product(s) found, need at least {MIN_PRODUCTS_FOR_REFINEMENT}",
            "stats": [],
        }
    
    if len(sections) > MAX_PRODUCTS_FOR_REFINEMENT:
        sections = sections[:MAX_PRODUCTS_FOR_REFINEMENT]
    
    # Fetch shopping signals for all products (parallel)
    signal_tasks = [gather_product_signals(s["product_name"], topic) for s in sections]
    all_signals = await asyncio.gather(*signal_tasks)
    
    # Refine each section (parallel LLM calls)
    refine_tasks = [
        refine_single_section(section, signals, blog_markdown)
        for section, signals in zip(sections, all_signals)
    ]
    refined_contents = await asyncio.gather(*refine_tasks)
    
    # Replace sections in blog (from END to START to preserve positions)
    refined_blog = blog_markdown
    stats = []
    
    sorted_pairs = sorted(
        zip(sections, refined_contents, all_signals),
        key=lambda x: x[0]["start"],
        reverse=True,
    )
    
    for section, refined_full, signals in sorted_pairs:
        section_start = section["start"]
        section_end = section["end"]
        
        # Extract content from refined (skip the heading line)
        if refined_full.startswith("###"):
            refined_content_only = refined_full.split('\n', 1)[1] if '\n' in refined_full else ""
        else:
            refined_content_only = refined_full
        
        # Replace only the content part (not the heading)
        heading_text = f"### {section['heading']}"
        new_section = heading_text + "\n\n" + refined_content_only.strip() + "\n"
        
        refined_blog = (
            refined_blog[:section_start]
            + new_section
            + refined_blog[section_end:]
        )
        
        was_refined = refined_content_only.strip() != section["content"].strip()
        stats.append({
            "product": section["product_name"],
            "heading": section["heading"],
            "praise_found": signals["praise"],
            "complaints_found": signals["complaints"],
            "was_refined": was_refined,
        })
    
    sections_refined = sum(1 for s in stats if s["was_refined"])
    
    logger.info("Blog refinement complete: %d/%d sections refined",
               sections_refined, len(sections))
    
    return {
        "refined_blog": refined_blog,
        "sections_refined": sections_refined,
        "total_products": len(sections),
        "skipped": False,
        "reason": "",
        "stats": stats,
    }


def format_refinement_report(result: Dict) -> str:
    """Format refinement results for UI display."""
    if result.get("skipped"):
        return f"### ⚠️ Refinement Skipped\n\n{result.get('reason', 'Unknown reason')}"
    
    lines = [
        f"### ✨ Refinement Complete!\n",
        f"**{result['sections_refined']} of {result['total_products']}** product sections "
        f"enhanced with real user signals.\n",
        "| Product | Praise Signals | Complaint Signals | Refined |",
        "|---------|---------------|-------------------|---------|",
    ]
    
    for stat in result["stats"]:
        praise = ", ".join(stat["praise_found"][:3]) or "—"
        complaints = ", ".join(stat["complaints_found"][:3]) or "—"
        refined_icon = "✅" if stat["was_refined"] else "⏭️"
        lines.append(
            f"| **{stat['product']}** | {praise} | {complaints} | {refined_icon} |"
        )
    
    lines.append("\n📖 **Check the Blog Comparison tab to see the refined version "
                "side by side with the original.**")
    
    return "\n".join(lines)
