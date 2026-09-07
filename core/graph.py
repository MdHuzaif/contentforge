"""Interactive step-by-step graph for ContentForge AI."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from langgraph.graph import END, START, StateGraph

from app.config import logger
from backend.llm.router import FALLBACK_MESSAGE, LLMRouter
from core.prompts.subprompt_prompt import SUBPROMPT_GENERATION_SYSTEM_PROMPT, SUBPROMPT_SPLIT_SYSTEM_PROMPT
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
    scraped_articles = []
    
    for comp in competitors[:5]:  # Analyze top 5 competitors (increased from 3)
        url = comp.get("url", "")
        try:
            # Extract headings from the competitor page
            headings = comp.get("headings", {})
            content = comp.get("content", "")
            title = comp.get("title", "")
            
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
            
            # === NEW: Save raw content for Level 2 product extraction ===
            if content and len(content) > 200:  # Only save if substantial content
                scraped_articles.append({
                    "url": url,
                    "title": title or f"Competitor {len(scraped_articles) + 1}",
                    "content": content[:8000],  # Limit to 8000 chars per article
                    "h2_titles": headings.get("h2", [])[:10],
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
    gap_analysis = {}
    try:
        router = LLMRouter()
        prompt = f"""You are an expert SEO content strategist. Analyze these competitors for topic: "{topic}"

COMPETITOR DATA:
- Pages analyzed: {len(sources)}
- Scraped metrics: {metrics}
- Page URLs: {', '.join(sources[:5])}

OPTIMAL STRUCTURE FOUND:
{json.dumps(content_structure, indent=2)[:1500]}

ANALYZE AND RETURN JSON with EXACTLY these keys:

{{
    "competitor_ranking_strengths": [
        "Why these pages rank well in Google (list 3-5 specific reasons)",
        "Example: 'Comprehensive spec tables with 8+ data columns'",
        "Example: 'Real benchmark data from hands-on testing'",
        "Example: 'Expert quotes from industry professionals'",
        "Example: 'Detailed pros/cons for each product reviewed'"
    ],
    "competitor_weaknesses": [
        "What competitors miss or do poorly (3-5 items)",
        "Example: 'Generic introductions without pain-point hooks'",
        "Example: 'Missing real user feedback and reviews'"
    ],
    "content_gaps_to_fill": [
        "Topics/angles we should cover that competitors miss (3-5 items)"
    ],
    "must_match_benchmarks": [
        "Features we MUST match to compete (3-5 items)",
        "Example: 'Detailed spec comparison tables'",
        "Example: 'Minimum 6 product reviews per category'"
    ],
    "user_intent": "informational|commercial|transactional|mixed",
    "user_pain_points": [
        "Specific problems readers have when searching this topic (3 items)"
    ],
    "featured_snippet_opportunities": [
        "Structured content formats that could win Position 0 (2-3 items)",
        "Example: 'Definition paragraph for what is X870E chipset'",
        "Example: 'Numbered list of 7 buying criteria'"
    ],
    "engagement_hooks_needed": [
        "Opening questions or hooks to capture attention (3 items)"
    ]
}}

Return ONLY valid JSON, no markdown, no explanation."""
        analysis_text = await router.generate_text(
            prompt, system_prompt="You are an expert SEO competitor analyst. Return only valid JSON.", task_type="competitor_analysis"
        )
        
        # Parse JSON
        if "```json" in analysis_text:
            analysis_text = analysis_text.split("```json")[1].split("```")[0]
        elif "```" in analysis_text:
            analysis_text = analysis_text.split("```")[1].split("```")[0]
            
        gap_analysis = json.loads(analysis_text.strip())
    except Exception as e:
        logger.warning("Competitor LLM analysis failed: %s. Using fallback.", e)
        gap_analysis = {}

    default_gap = {
        "competitor_ranking_strengths": ["Comprehensive coverage", "Clear structure", "Detailed spec comparisons"],
        "competitor_weaknesses": ["Generic content", "Missing real user feedback"],
        "content_gaps_to_fill": ["Real user feedback", "Hands-on testing data"],
        "must_match_benchmarks": ["Detailed specs", "Pros/cons lists", "Clear pricing tiering"],
        "user_intent": "commercial",
        "user_pain_points": ["Too many options", "Confusing specs", "Budget concerns"],
        "featured_snippet_opportunities": ["Definition paragraph", "Numbered list of buying criteria"],
        "engagement_hooks_needed": ["Opening question", "Pain point hook", "Expert claim"],
    }
    if not isinstance(gap_analysis, dict):
        gap_analysis = default_gap
    else:
        for k, v in default_gap.items():
            if k not in gap_analysis or not gap_analysis[k]:
                gap_analysis[k] = v

    # --- NEW: shopping/user signals enrichment (optional, never fatal) ---
    try:
        from backend.tools.shopping_intelligence import gather_shopping_signals
        signals = await gather_shopping_signals(topic)
        if signals:
            if isinstance(gap_analysis, dict):
                gap_analysis["shopping_signals"] = signals
            logger.info("Shopping signals appended (%d chars)", len(signals))
    except Exception as e:
        logger.warning("Shopping intelligence skipped: %s", e)

    return {
        "competitor_analysis": {
            "status": "completed",
            "topic": topic,
            "competitors": competitors,
            "metrics": metrics,
            "gap_analysis": analysis_text,
            "sources": sources,
            "scraped_articles": scraped_articles,  # === NEW: Raw content for Level 2 ===
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
    
    result = {
        **kw_result,
        **comp_result,
        "current_phase": "prompt_generation",
        "research_status": "completed",
    }
    
    # === LEVEL 1: Content Type Classification ===
    logger.info("🎯 Running content type classification...")
    from core.classifiers.content_type_classifier import classify_content_type
    
    try:
        classification = await classify_content_type(
            topic=state.get("topic", state.get("user_request", "")),
            keywords=result.get("keyword_research", {}).get("keywords", []),
            competitor_data=result.get("competitor_analysis", {}),
        )
        
        # Update state with classification
        result["content_type"] = classification["content_type"]
        result["content_type_confidence"] = classification["confidence"]
        result["content_type_reasoning"] = classification["reasoning"]
        result["product_count_estimate"] = classification["product_count_estimate"]
        
    except Exception as e:
        logger.warning(f"Content classification failed: {e}")
        # Keep defaults from create_initial_state
        
    # === LEVEL 2: Universal Product Selection (only for product_recommendation) ===
    if result.get("content_type") == "product_recommendation":
        logger.info("🛒 Running universal product selection engine...")
        from core.selectors.product_selector import extract_products_universal
        
        try:
            target_count = result.get("product_count_estimate", 10)
            topic = state.get("topic", state.get("user_request", ""))
            competitor_data = result.get("competitor_analysis", {})
            
            extraction_result = await extract_products_universal(
                topic=topic,
                competitor_data=competitor_data,
                target_count=target_count,
            )
            
            products = extraction_result.get("products", [])
            result["selected_products"] = products
            result["product_category"] = extraction_result.get("category_detected", "unknown")
            result["extraction_confidence"] = extraction_result.get("extraction_confidence", 0.0)
            result["extraction_notes"] = extraction_result.get("extraction_notes", "")
            
            logger.info(f"✅ Selected {len(products)} authentic products")
            for i, p in enumerate(products[:3], 1):
                logger.info(f"   {i}. {p['name']} ({p['tier']})")
            
        except Exception as e:
            logger.warning(f"Product selection failed: {e}")
            result["selected_products"] = []
            result["product_category"] = "unknown"
            result["extraction_confidence"] = 0.0
            result["extraction_notes"] = f"Selection failed: {e}"
    else:
        logger.info(f"ℹ️  Content type is '{result.get('content_type')}', skipping product selection")
        result["selected_products"] = []
        result["product_category"] = "not_applicable"
        
    return result


def _generate_product_subprompts(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate structured sub-prompts for product recommendation content.
    
    Creates:
    - H2: Introduction
    - H2: At a Glance comparison table
    - H2: Detailed reviews intro
    - H3: One detailed review per selected product
    - H2: Buying guide
    - H2: FAQ
    - H2: Conclusion
    """
    selected_products = state.get("selected_products", [])
    topic = state.get("topic", state.get("user_request", ""))
    keywords_data = state.get("keyword_research", {}).get("keywords", [])
    category = state.get("product_category", "product")
    
    # Extract top keywords
    primary_kw = ""
    secondary_kws = []
    if keywords_data:
        if isinstance(keywords_data[0], dict):
            primary_kw = keywords_data[0].get("keyword", topic)
            secondary_kws = [k.get("keyword", "") for k in keywords_data[1:9]]
        else:
            primary_kw = keywords_data[0] if keywords_data else topic
            secondary_kws = keywords_data[1:9]
    
    secondary_kw_text = ", ".join(secondary_kws) if secondary_kws else "related terms"
    product_count = len(selected_products)
    
    sub_prompts = []
    
    # === 1. H2: Introduction ===
    sub_prompts.append({
        "id": 0,
        "title": f"Introduction: Your Guide to the Best {category.title()} Options in 2026",
        "type": "h2_intro",
        "word_target": 600,
        "status": "pending",
        "primary_keyword": primary_kw,
        "secondary_keywords": secondary_kws,
        "prompt": f"""Write a compelling 500-700 word introduction for an article about '{topic}'.

STRUCTURE:
1. HOOK (100 words): Start with a surprising statistic, common pain point, or 
   provocative question about {category} shopping in 2026.
2. CONTEXT (150 words): Explain why choosing the right {category} matters now — 
   mention recent tech advances, market changes, or user needs.
3. WHAT READERS WILL LEARN (150 words): Preview the {product_count} products reviewed, 
   the testing methodology, and the tier breakdown (premium/mid-range/budget).
4. CREDIBILITY (100 words): Briefly mention how products were selected (competitor 
   analysis, real user signals, expert testing).
5. TRANSITION (100 words): Tease the "At a Glance" table and detailed reviews below.

SEO REQUIREMENTS:
- Naturally weave in primary keyword: '{primary_kw}'
- Include 2-3 secondary keywords: {secondary_kw_text}
- Use conversational expert tone ("we tested", "in our experience")
- End with a clear transition sentence

DO NOT include any product names in detail here — save those for the reviews below.
DO NOT include any buy buttons or pricing.""",
        "key_points": [
            "Hook with statistic or pain point",
            "Why this topic matters in 2026",
            f"Preview of {product_count} products reviewed",
            "Testing methodology credibility",
            "Transition to detailed reviews"
        ],
    })
    
    # === 2. H2: At a Glance Comparison Table ===
    sub_prompts.append({
        "id": 1,
        "title": "At a Glance: Quick Comparison of Top Picks",
        "type": "h2_intro",
        "word_target": 900,
        "status": "pending",
        "primary_keyword": primary_kw,
        "secondary_keywords": secondary_kws,
        "prompt": f"""Create a comprehensive comparison section for {product_count} {category} products.

REQUIRED MARKDOWN TABLE with these exact columns:
| Product | Brand | Tier | Best For | Key Feature | Rating |

Include one row for EACH of these products (in this order):
{chr(10).join(f"{i+1}. {p['name']} ({p.get('tier', 'mid_range')}) - {p.get('why_notable', '')}" for i, p in enumerate(selected_products))}

TABLE RULES:
- Rating column: Use X/10 format (e.g., 9.2/10)
- Tier column: Use "💎 Premium", "⭐ Mid-Range", or "💰 Budget"
- Best For: 3-5 words describing ideal user
- Key Feature: One standout feature per product
- DO NOT include a "Buy" or "Price" column (buttons added separately)

BELOW THE TABLE, write 200-300 words explaining:
- How to read and use this table effectively
- Quick recommendation by use case (e.g., "If you want X, choose Y")
- Transition to detailed reviews below

Use primary keyword '{primary_kw}' naturally 2-3 times.
Do NOT include any buy buttons or pricing information.""",
        "key_points": [
            f"Markdown table with {product_count} rows",
            "Columns: Product, Brand, Tier, Best For, Key Feature, Rating",
            "How to read the table (200-300 words)",
            "Quick recommendations by use case"
        ],
    })
    
    # === 3. H2: Detailed Product Reviews Intro ===
    sub_prompts.append({
        "id": 2,
        "title": "Detailed Product Reviews: Deep Dive into Our Top Picks",
        "type": "h2_intro",
        "word_target": 250,
        "status": "pending",
        "primary_keyword": primary_kw,
        "secondary_keywords": secondary_kws,
        "prompt": f"""Write a 200-300 word introduction to the detailed product reviews section.

EXPLAIN:
- How we tested these {product_count} products (mention: real-world testing, 
  competitor analysis, user feedback aggregation, specification comparison)
- What readers will find in each review below:
  * Product overview and positioning
  * Technical specifications
  * Performance analysis
  * Honest pros and cons
  * Verdict on who should buy
- Brief explanation of our tier system:
  * 💎 Premium: Flagship products with cutting-edge features
  * ⭐ Mid-Range: Best balance of features and value
  * 💰 Budget: Excellent performance at affordable prices

Use expert, authoritative tone. End with a transition like 
"Let's dive into each product, starting with our top premium pick..."

Use primary keyword '{primary_kw}' once. Do NOT include buy buttons.""",
        "key_points": [
            "Testing methodology explanation",
            "What each review covers",
            "Tier system explanation",
            "Transition to individual reviews"
        ],
    })
    
    # === 4. H3: One detailed review per product ===
    for i, product in enumerate(selected_products, start=3):
        product_name = product.get("name", f"Product {i-2}")
        brand = product.get("brand", product_name.split()[0])
        tier = product.get("tier", "mid_range")
        why_notable = product.get("why_notable", "")
        selling_points = product.get("selling_points", [])
        existing_pros = product.get("pros", [])
        existing_cons = product.get("cons", [])
        popularity = product.get("popularity_score", 5)
        
        tier_label = {"premium": "premium/flagship", "mid_range": "mid-range", "budget": "budget"}.get(tier, tier)
        tier_emoji = {"premium": "💎", "mid_range": "⭐", "budget": "💰"}.get(tier, "•")
        selling_points_text = ", ".join(selling_points) if selling_points else "highlight its standout features"
        
        sub_prompts.append({
            "id": i,
            "title": product_name,
            "type": "h3_detail",
            "product_name": product_name,
            "product_brand": brand,
            "product_tier": tier,
            "word_target": 600,
            "status": "pending",
            "primary_keyword": primary_kw,
            "secondary_keywords": secondary_kws,
            "prompt": f"""Write a detailed 500-700 word review of the {product_name} {category}.

This is a {tier_label} product (tier: {tier_emoji} {tier}) in our '{topic}' roundup.
Popularity score from competitor analysis: {popularity}/10.
Background: {why_notable}
Key Selling Points to Highlight: {selling_points_text}

CRITICAL HEADING RULE - READ CAREFULLY:
❌ DO NOT include "### {product_name}" or any heading with the product name
❌ DO NOT repeat the product name as a markdown heading anywhere
❌ DO NOT start your response with "### {product_name}" or "## {product_name}"
✅ We will add the heading separately - start DIRECTLY with the content
✅ Your FIRST line must be the hook question or opening paragraph

FOLLOW THIS EXACT STRUCTURE:

**1. Overview Paragraph** (100-150 words)
- Introduce the {product_name} and its position in the {brand} lineup
- Who this product is designed for
- What makes it stand out in the {tier_label} category

**2. Key Specifications** (use bullet list or mini-table)
- Include 6-8 most important specs relevant to {category}
- Format: "**Spec Name**: Value/Description"
- Focus on specs that matter to buyers in 2026

**3. Performance & Real-World Analysis** (150-200 words)
- How it performs in actual use cases
- Thermal/performance characteristics
- Build quality and user experience
- Compare briefly to similar products in the list

**4. Pros** (bullet list, 4-5 items)
{chr(10).join(f"- {pro}" for pro in existing_pros) if existing_pros else "- [Real pro based on analysis]"}
- Each pro must be specific and concrete

**5. Cons** (bullet list, 3-4 items)
{chr(10).join(f"- {con}" for con in existing_cons) if existing_cons else "- [Real con based on analysis]"}
- Be honest but fair

**6. Verdict: Who Should Buy** (100-150 words, 3-4 sentences)
- Clear recommendation statement
- Ideal user profile
- Who should skip this and consider alternatives from our list

CRITICAL RULES:
- DO NOT include any "Buy", "Check Price", "Shop Now", or Amazon-style buttons
- DO NOT mention specific prices (use "$$$" tier indicators only if needed)
- DO NOT include affiliate links or CTAs
- Use first-person expert voice ("we tested", "in our experience")
- Use primary keyword '{primary_kw}' naturally 1-2 times
- CRITICAL: DO NOT include "### {product_name}" or any heading with the product name.
- REMEMBER: NO product name heading - start directly with the paragraph/hook.
- DO NOT start your response with "###" or "##".""",
            "key_points": [
                f"Overview of {product_name}",
                "Detailed specifications",
                "Real-world performance analysis",
                f"4-5 honest pros{f' (including: {existing_pros[0]})' if existing_pros else ''}",
                f"3-4 honest cons{f' (including: {existing_cons[0]})' if existing_cons else ''}",
                "Verdict: who should buy"
            ],
        })
    
    # === 5. H2: Buying Guide ===
    next_id = len(sub_prompts)
    sub_prompts.append({
        "id": next_id,
        "title": f"Buying Guide: How to Choose the Right {category.title()}",
        "type": "h2_intro",
        "word_target": 1000,
        "status": "pending",
        "primary_keyword": primary_kw,
        "secondary_keywords": secondary_kws,
        "prompt": f"""Write a comprehensive 1000-word buying guide for {topic}.

Structure with H3 subheadings:

### Understanding Your Needs
- Questions buyers should ask themselves
- Use case scenarios (gaming, productivity, professional, casual)

### Key Features to Consider
- 4-5 critical features specific to {category}
- Explain each with practical examples
- Mention what specs actually matter vs marketing fluff

### Tier Breakdown: Premium vs Mid-Range vs Budget
- What you get at each tier
- When premium is worth it vs when budget suffices
- Reference products from our reviews as examples

### Common Mistakes to Avoid
- 3-4 pitfalls buyers encounter
- How to avoid getting misled by marketing

### Future-Proofing Your Purchase
- What to look for to ensure longevity
- Upgrade paths and compatibility considerations

Use educational, expert tone. Weave in primary keyword '{primary_kw}' 3-4 times.
Do NOT include buy buttons or pricing.""",
        "key_points": [
            "Understanding your needs",
            "Key features to consider",
            "Tier breakdown (premium/mid-range/budget)",
            "Common mistakes to avoid",
            "Future-proofing guidance"
        ],
    })
    
    # === 6. H2: FAQ ===
    next_id += 1
    sub_prompts.append({
        "id": next_id,
        "title": f"Frequently Asked Questions About {category.title()}",
        "type": "h2_intro",
        "word_target": 800,
        "status": "pending",
        "primary_keyword": primary_kw,
        "secondary_keywords": secondary_kws,
        "prompt": f"""Write 8-10 FAQ entries about {topic} using schema-friendly format.

Each FAQ entry MUST have:
- ### Question (as H3 heading)
- Detailed answer (80-120 words)

COVER THESE QUESTION TYPES:
1. "What is the best {category} for [specific use case]?" — reference products from our list
2. "How much should I spend on a {category}?" — tier guidance
3. "What specs matter most for {category} in 2026?"
4. "Is [popular product] worth it?" — reference one of our reviewed products
5. "What's the difference between [tier A] and [tier B]?"
6. "How long will a {category} last?"
7. "What should I avoid when buying a {category}?"
8. "Can I upgrade/expand later?"

FORMAT EXAMPLE:
### What is the best {category} for beginners?
For beginners, we recommend starting with a mid-range option like [Product X] from our list. 
It offers the best balance of features and value without overwhelming new users. You get 
[feature 1], [feature 2], and solid build quality. Avoid the cheapest options as they often 
compromise on [critical feature], which leads to frustration and early replacement.

Use conversational but expert tone. Naturally use primary keyword 2-3 times.
Do NOT include buy buttons or pricing.""",
        "key_points": [
            "8-10 FAQ entries",
            "Schema-friendly Q&A format",
            "References to reviewed products",
            "Practical, specific answers"
        ],
    })
    
    # === 7. H2: Conclusion ===
    next_id += 1
    sub_prompts.append({
        "id": next_id,
        "title": "Final Verdict: Which Should You Choose?",
        "type": "h2_intro",
        "word_target": 400,
        "status": "pending",
        "primary_keyword": primary_kw,
        "secondary_keywords": secondary_kws,
        "prompt": f"""Write a 400-word conclusion for our '{topic}' article.

STRUCTURE:
1. **Quick Recap** (100 words): Remind readers of the {product_count} products reviewed 
   and the three-tier approach.

2. **Top 3 Recommendations by Use Case** (200 words):
   - Best Overall / Premium Choice: [Reference top product from list]
   - Best Value / Mid-Range: [Reference mid-range product]
   - Best Budget Option: [Reference budget product]
   Each with 2-3 sentences explaining why.

3. **Final Recommendation** (100 words):
   - Decision framework for readers
   - Encouragement to match choice to their specific needs
   - Brief forward-looking statement about the {category} market in 2026+

Use confident, expert tone. Reference specific products from our reviews.
Use primary keyword '{primary_kw}' 1-2 times.
Do NOT include buy buttons or pricing.""",
        "key_points": [
            f"Quick recap of {product_count} products",
            "Top 3 recommendations by use case",
            "Final decision framework",
            "Forward-looking market statement"
        ],
    })
    
    logger.info(f"📝 Generated {len(sub_prompts)} product-focused sub-prompts ({product_count} products)")
    return sub_prompts


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
        
        # === AUTO-SPLIT LARGE SECTIONS (>1000 words) ===
        MAX_SECTION_WORDS = 1000
        final_prompts = []

        for prompt in sub_prompts:
            word_target = prompt.get("word_target", 600)
            
            if word_target <= MAX_SECTION_WORDS:
                # Small enough, keep as-is
                final_prompts.append(prompt)
            else:
                # LARGE section - split via LLM
                logger.info(f"Auto-splitting '{prompt.get('title')}' ({word_target} words) into H2+H3s")
                
                try:
                    split_prompt_text = SUBPROMPT_SPLIT_SYSTEM_PROMPT.format(
                        topic=state.get("topic", "general topic"),
                        section_title=prompt.get("title", "Section"),
                        word_target=word_target,
                        original_prompt=prompt.get("prompt", "Detailed section"),
                    )
                    
                    router = LLMRouter()
                    split_response = await router.generate_text(
                        prompt=split_prompt_text,
                        system_prompt="You are an expert content strategist. Return only valid JSON.",
                        task_type="subprompt_generation",
                    )
                    
                    # Parse JSON
                    if "```json" in split_response:
                        split_response = split_response.split("```json")[1].split("```")[0]
                    elif "```" in split_response:
                        split_response = split_response.split("```")[1].split("```")[0]
                    
                    split_data = json.loads(split_response.strip())
                    
                    if isinstance(split_data, list) and len(split_data) >= 2:
                        # Successfully split - add all sub-parts
                        for i, split_item in enumerate(split_data):
                            split_item["original_id"] = prompt.get("id")
                            split_item["is_split"] = True
                            split_item["split_type"] = split_item.get("type", "h3_detail")
                            split_item["status"] = "pending"
                            final_prompts.append(split_item)
                        logger.info(f"  ✓ Split into {len(split_data)} parts")
                    else:
                        logger.warning(f"  ✗ Split returned invalid data, keeping original")
                        final_prompts.append(prompt)
                        
                except Exception as e:
                    logger.warning(f"  ✗ Split failed for '{prompt.get('title')}': {e}")
                    final_prompts.append(prompt)

        # Renumber all prompts sequentially
        for i, p in enumerate(final_prompts):
            p["id"] = i
            if "status" not in p:
                p["status"] = "pending"

        # Replace original sub_prompts with split version
        sub_prompts = final_prompts

        logger.info(f"Final prompt count: {len(sub_prompts)} (after splitting)")
        
        # === LEVEL 3: Override with product-focused structure if applicable ===
        if (state.get("content_type") == "product_recommendation" 
            and state.get("selected_products") 
            and len(state.get("selected_products", [])) >= 3):
            
            logger.info("🎯 Using enhanced product-focused sub-prompt structure")
            product_sub_prompts = _generate_product_subprompts(state)
            
            # Override the LLM-generated sub-prompts
            sub_prompts = product_sub_prompts
            
            # Log summary
            h2_count = sum(1 for p in product_sub_prompts if p.get("type") == "h2_intro")
            h3_count = sum(1 for p in product_sub_prompts if p.get("type") == "h3_detail")
            total_words = sum(p.get("word_target", 0) for p in product_sub_prompts)
            
            logger.info(f"   Structure: {h2_count} H2 sections + {h3_count} H3 product reviews")
            logger.info(f"   Total word target: {total_words} words")
        else:
            logger.info(f"ℹ️  Using standard LLM sub-prompts (content_type: {state.get('content_type')})")

        return {
            "sub_prompts": sub_prompts,
            "total_sections": len(sub_prompts),
            "current_phase": "execution",
            "prompt_generation_status": "completed",
        }
    except Exception as e:
        logger.error(f"Subprompt generation failed: {e}")
        
        # Check if product recommendation override can be used here
        if (state.get("content_type") == "product_recommendation" 
            and state.get("selected_products") 
            and len(state.get("selected_products", [])) >= 3):
            try:
                logger.info("🎯 Using enhanced product-focused sub-prompt structure (fallback catch)")
                product_sub_prompts = _generate_product_subprompts(state)
                return {
                    "sub_prompts": product_sub_prompts,
                    "total_sections": len(product_sub_prompts),
                    "current_phase": "execution",
                    "prompt_generation_status": "completed",
                }
            except Exception as inner_e:
                logger.warning(f"Product subprompt generation failed in fallback: {inner_e}")

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

def _sanitize_section_content(content: str, product_name: str = "") -> str:
    """Remove duplicate product name headings from LLM-generated content.
    
    Fixes bug where LLM includes product name as H3 heading at the start of
    content, which then duplicates with the H2 heading added by blog assembler.
    """
    if not content or not product_name:
        return content
    
    import re
    
    # Pattern 1: Content starts with ### ProductName or ## ProductName
    product_pattern = rf'^[#]+\s*{re.escape(product_name)}\s*\n+'
    content = re.sub(product_pattern, '', content.strip(), flags=re.IGNORECASE)
    
    # Pattern 2: Product name heading appears anywhere in the content
    mid_content_pattern = rf'\n[#]+\s*{re.escape(product_name)}\s*\n'
    content = re.sub(mid_content_pattern, '\n', content, flags=re.IGNORECASE)
    
    # Pattern 3: Product name heading with trailing newline at very start
    content = re.sub(rf'^(?:#+\s*)?{re.escape(product_name)}\s*\n', '', content, flags=re.IGNORECASE)
    
    # Clean up multiple consecutive newlines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content.strip()

async def section_writer_node(state: ContentForgeState) -> Dict[str, Any]:
    """Phase 3: Write one section with accumulated context and update context for next section."""
    logger.info("Executing section_writer_node (Phase 3)")
    
    current_idx = state.get("current_section_index", 0)
    total = state.get("total_sections", 0)
    sub_prompts = state.get("sub_prompts", [])
    section_contexts = state.get("section_contexts", [])
    topic = state.get("user_request", "General Topic")
    detected_products = list(state.get("detected_products", []))
    
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

    # Extract enhanced data from competitor_analysis (which contains gap analysis)
    comp_data = state.get("competitor_analysis", {})
    gap_data = comp_data.get("gap_analysis", {})

    if isinstance(gap_data, dict):
        ranking_strengths = gap_data.get("competitor_ranking_strengths", [])
        user_intent = gap_data.get("user_intent", "commercial")
        user_pain_points = gap_data.get("user_pain_points", [])
        snippet_opportunities = gap_data.get("featured_snippet_opportunities", [])
        engagement_hooks = gap_data.get("engagement_hooks_needed", [])
        must_match = gap_data.get("must_match_benchmarks", [])
        gaps_list = gap_data.get("content_gaps_to_fill", [])
        gap_summary = "\n".join(f"- {g}" for g in gaps_list) if gaps_list else "No gap analysis available."
    else:
        ranking_strengths = ["Comprehensive coverage", "Clear structure"]
        user_intent = "commercial"
        user_pain_points = ["Too many options", "Confusing specs", "Budget concerns"]
        snippet_opportunities = ["Definition paragraph", "Numbered list"]
        engagement_hooks = ["Opening question", "Pain point hook", "Expert claim"]
        must_match = ["Detailed specs", "Pros/cons lists"]
        gap_summary = str(gap_data) if gap_data else "No gap analysis available."

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

    current_section_details = f"""- Section Number: {current_idx + 1} of {total}
- Title: {current_prompt.get('title', 'Untitled Section')}
- Target Word Count: {current_prompt.get('word_target', 600)} words
- Key Points to Cover: {', '.join(current_prompt.get('key_points', []))}
- Detailed Instructions: {current_prompt.get('prompt', 'Write this section')}

{accumulated_context}"""

    section_prompt_text = f"""TOPIC: {topic}

=== SEO & COMPETITIVE INTELLIGENCE ===
USER INTENT: {user_intent} (match this intent in tone and depth)
PRIMARY KEYWORD: {primary_keyword}
SECONDARY KEYWORDS: {', '.join(secondary_keywords) or 'None'}

USER PAIN POINTS TO ADDRESS (weave naturally):
{chr(10).join(f"- {p}" for p in user_pain_points[:3])}

COMPETITOR RANKING STRENGTHS (match or exceed these):
{chr(10).join(f"- {s}" for s in ranking_strengths[:4])}

MUST-MATCH BENCHMARKS:
{chr(10).join(f"- {b}" for b in must_match[:3])}

FEATURED SNIPPET OPPORTUNITY (if this section fits, use it):
{chr(10).join(f"- {o}" for o in snippet_opportunities[:2])}

CONTENT GAPS TO FILL:
{gap_summary}

COMPETITOR BENCHMARKS:
{competitor_benchmarks}

ENGAGEMENT HOOKS AVAILABLE:
{chr(10).join(f"- {h}" for h in engagement_hooks[:2])}

CURRENT SECTION DETAILS:
{current_section_details}

CRITICAL RANKING REQUIREMENTS:
1. Match competitor strengths listed above (don't fall below their quality)
2. Address at least ONE user pain point naturally
3. Use engagement hooks in opening/closing paragraphs
4. If a featured snippet opportunity fits this section, structure content to capture it:
   - For definitions: write a 40-60 word definitive answer early
   - For lists: use numbered/bulleted lists with 5-7 items
   - For tables: use markdown tables with 5+ columns when comparing
5. Include E-E-A-T signals: specific numbers, testing methodology, hands-on experience language
6. Primary keyword AT MOST ONCE (first 100 words or heading); use semantic variations elsewhere
7. Match competitor word depth and structure
8. Address at least one gap identified in GAP ANALYSIS
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
        
        # === NEW: Remove duplicate product name headings ===
        product_name_for_sanitize = ""
        if current_idx < len(sub_prompts):
            current_sub_prompt = sub_prompts[current_idx]
            if current_sub_prompt.get("type") == "h3_detail":
                product_name_for_sanitize = current_sub_prompt.get("product_name", "")
        
        if product_name_for_sanitize:
            section_content = _sanitize_section_content(section_content, product_name_for_sanitize)
        
        # === POST-PROCESSING: Clean heading numbers ===
        from core.post_processors.heading_cleaner import clean_section_content
        cleaned_content = clean_section_content(section_content)

        if cleaned_content != section_content:
            logger.info(f"Section {current_idx + 1}: Cleaned heading number prefixes")
            section_content = cleaned_content
        
        # === MINIMUM QUALITY GATE ===
        MIN_SECTION_WORDS = 100
        word_count = len(section_content.split())
        
        if word_count < MIN_SECTION_WORDS:
            logger.warning(
                f"⚠️ Section {current_idx + 1}/{total} FAILED: only {word_count} words generated "
                f"(minimum required: {MIN_SECTION_WORDS}). HOLDING at this section for retry."
            )
            generated_sections = state.get("generated_sections", [])
            if len(generated_sections) > current_idx:
                generated_sections[current_idx]["content"] = ""
            else:
                generated_sections.append({
                    "id": current_idx,
                    "title": current_prompt.get("title", f"Section {current_idx + 1}"),
                    "content": "",
                    "word_count": 0,
                    "timestamp": datetime.now().isoformat(),
                    "status": "failed",
                })
            return {
                **state,
                "current_section_index": current_idx,  # HOLD - don't advance
                "generated_sections": generated_sections,
                "last_error": f"Section {current_idx + 1} generated only {word_count} words (min {MIN_SECTION_WORDS}). Click Execute again to retry.",
            }

        logger.info(f"Section {current_idx + 1} generated: {word_count} words ✓")
        
        # Now summarize this section for future context
        logger.info(f"Summarizing section {current_idx + 1} for context")
        context_summary = await router.generate_text(
            prompt=f"Summarize this blog section for context:\n\n{section_content}",
            system_prompt=CONTEXT_SUMMARIZATION_SYSTEM_PROMPT,
            task_type="context_summarization",
        )
        
        # Update state
        generated_sections = state.get("generated_sections", [])
        
        if len(generated_sections) > current_idx:
            generated_sections[current_idx] = {
                "id": current_idx,
                "title": current_prompt.get("title", f"Section {current_idx + 1}"),
                "content": section_content,
                "word_count": word_count,
                "timestamp": datetime.now().isoformat(),
                "status": "completed",
            }
        else:
            generated_sections.append({
                "id": current_idx,
                "title": current_prompt.get("title", f"Section {current_idx + 1}"),
                "content": section_content,
                "word_count": word_count,
                "timestamp": datetime.now().isoformat(),
                "status": "completed",
            })
        
        # === AUTO-REFINEMENT: Section-level product detection ===
        try:
            from core.post_processors.product_detector import (
                PRODUCT_PATTERN,
                _extract_product_name,
                RETAILERS
            )
            from core.post_processors.product_refiner import (
                gather_product_signals,
                refine_single_section
            )
            
            # Safe access to state variables
            sub_prompts_list = state.get("sub_prompts", [])
            section_topic = state.get("topic", "") or state.get("user_request", "")
            
            if current_idx < len(sub_prompts_list) and current_idx < len(generated_sections):
                section_title = sub_prompts_list[current_idx].get("title", "")
                section_content = generated_sections[current_idx].get("content", "")
                
                if section_content and len(section_content) > 100:
                    # === LEVEL 4: Enhanced product detection using Level 3 metadata ===
                    current_sub = sub_prompts_list[current_idx] if current_idx < len(sub_prompts_list) else {}
                    section_type = current_sub.get("type", "h2") if isinstance(current_sub, dict) else "h2"

                    # Priority 1: Use product_name from sub-prompt metadata (Level 3)
                    product_name = ""
                    product_metadata = {}

                    if section_type == "h3_detail" and isinstance(current_sub, dict):
                        product_name = current_sub.get("product_name", "")
                        product_metadata = {
                            "brand": current_sub.get("product_brand", ""),
                            "tier": current_sub.get("product_tier", ""),
                            "why_notable": current_sub.get("why_notable", ""),
                            "selling_points": current_sub.get("selling_points", []),
                            "existing_pros": current_sub.get("pros", []),
                            "existing_cons": current_sub.get("cons", []),
                            "popularity": current_sub.get("popularity_score", 5),
                        }
                        logger.info(f"Section {current_idx + 1}: Using Level 3 product metadata for '{product_name}'")

                    # Priority 2: Fallback to heading extraction (for non-Level-3 content)
                    if not product_name:
                        product_name = _extract_product_name(section_title)
                        if product_name:
                            logger.info(f"Section {current_idx + 1}: Product detected from heading '{product_name}'")
                    
                    # Step 3: If product found, auto-refine with enhanced metadata
                    if product_name:
                        logger.info(f"Section {current_idx + 1}: Product detected '{product_name}', auto-refining...")
                        
                        # Save product name in generated section
                        generated_sections[current_idx]["product_name"] = product_name

                        # Track detected product for affiliate linking UI
                        existing_names = {p["name"] for p in detected_products}
                        if product_name not in existing_names:
                            detected_products.append({
                                "name": product_name,
                                "section_index": current_idx,
                                "heading": section_title,
                                "detected_at": datetime.now().isoformat(),
                            })
                            logger.info(f"📦 Detected product for affiliate: '{product_name}'")
                        
                        try:
                            signals = await gather_product_signals(product_name, section_topic)
                            
                            if signals.get("found", False):
                                # Enrich signals with Level 3 metadata if available
                                if product_metadata:
                                    signals["level3_metadata"] = product_metadata
                                    logger.info(f"   Using Level 3 metadata: tier={product_metadata.get('tier')}, popularity={product_metadata.get('popularity')}")
                                
                                section_dict = {
                                    "heading": section_title,
                                    "product_name": product_name,
                                    "content": section_content,
                                    "start": 0,
                                    "end": len(section_content),
                                    "word_count": len(section_content.split())
                                }
                                
                                # Build context from previous sections
                                blog_context_parts = []
                                for prev_idx in range(current_idx):
                                    prev_item = generated_sections[prev_idx]
                                    prev_content = prev_item.get("content", "") if isinstance(prev_item, dict) else str(prev_item)
                                    if prev_content:
                                        blog_context_parts.append(prev_content[:400])
                                blog_context = "\n\n".join(blog_context_parts)
                                
                                refined = await refine_single_section(section_dict, signals, blog_context)
                                
                                if refined and refined != section_dict["content"]:
                                    # === NEW: Sanitize refined content too ===
                                    if product_name:
                                        refined = _sanitize_section_content(refined, product_name)
                                    
                                    # Check for prices (Amazon policy)
                                    if not re.search(r'\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?', refined):
                                        generated_sections[current_idx]["content"] = refined
                                        generated_sections[current_idx]["refined"] = True
                                        generated_sections[current_idx]["product_name"] = product_name
                                        generated_sections[current_idx]["shopping_signals"] = {
                                            "praise": signals.get("praise", []),
                                            "complaints": signals.get("complaints", []),
                                            "snippets_count": len(signals.get("snippets", [])),
                                            "sources": list(set(signals.get("sources", [])))[:5]
                                        }
                                        logger.info(f"✅ Section {current_idx + 1} refined with {len(signals.get('snippets', []))} shopping signals")
                                    else:
                                        logger.warning(f"⚠️ Section {current_idx + 1}: Refined content contained prices, using original")
                                else:
                                    logger.info(f"Section {current_idx + 1}: Refinement unchanged")
                            else:
                                logger.info(f"Section {current_idx + 1}: No shopping signals found")
                                
                        except Exception as refine_err:
                            logger.warning(f"Section {current_idx + 1}: Auto-refinement failed: {refine_err}")
                            
                    # === ENHANCED DETECTION: Also check for products in markdown tables ===
                    # This helps detect products mentioned in "At a Glance" comparison tables
                    section_content = generated_sections[-1]["content"] if generated_sections else ""
                    
                    # Look for product names in table rows
                    table_product_pattern = r'\|\s*([A-Z][A-Za-z0-9\s\-]+(?:ROG|AORUS|Strix|Tomahawk|Crosshair|TUF|Gaming|WiFi|MAX|Elite|Hero)[^\|]*)\s*\|'
                    table_matches = re.findall(table_product_pattern, section_content)
                    
                    existing_names = {p["name"] for p in detected_products}
                    
                    # Get known product names from state (Level 2 selection) for validation
                    selected_products = state.get("selected_products", [])
                    known_product_names = {p.get("name", "").lower() for p in selected_products if p.get("name")}
                    known_product_keywords = set()
                    for p in selected_products:
                        name = p.get("name", "")
                        # Extract brand + model keywords
                        parts = name.split()
                        if len(parts) >= 2:
                            known_product_keywords.add(parts[0].lower())  # Brand
                            known_product_keywords.add(parts[-1].lower())  # Model suffix
                            known_product_keywords.add(name.lower())  # Full name
                    
                    for match in table_matches:
                        detected_name = match.strip()
                        
                        # Skip if too short or already detected
                        if len(detected_name) < 10 or detected_name in existing_names:
                            continue
                        
                        # === VALIDATION: Filter out false positives ===
                        # Only accept if it matches a known product OR looks like a real product name
                        detected_lower = detected_name.lower()
                        
                        # Check 1: Direct match with known products
                        is_known_product = any(
                            detected_lower in known.lower() or known.lower() in detected_lower
                            for known in known_product_names
                            if known
                        )
                        
                        # Check 2: Contains brand + model pattern (e.g., "ASUS ROG", "MSI MPG")
                        has_brand_model = bool(re.match(
                            r'^(ASUS|MSI|Gigabyte|ASRock|Biostar|NZXT|EVGA|Intel|AMD)\s+\w+',
                            detected_name,
                            re.IGNORECASE
                        ))
                        
                        # Check 3: Exclude common false positive patterns
                        false_positive_keywords = [
                            'components', 'features', 'technology', 'design', 'cooling',
                            'memory', 'storage', 'performance', 'power', 'quality',
                            'military-grade', 'premium', 'advanced', 'enhanced'
                        ]
                        has_false_positive = any(
                            fp in detected_lower for fp in false_positive_keywords
                        )
                        
                        # Only add if it passes validation
                        if (is_known_product or has_brand_model) and not has_false_positive:
                            detected_products.append({
                                "name": detected_name,
                                "section_index": current_idx,
                                "heading": section_title,
                                "detected_at": datetime.now().isoformat(),
                                "source": "table"
                            })
                            logger.info(f"📦 Detected product from table: '{detected_name}'")
                        else:
                            logger.debug(f"⏭️  Skipped false positive from table: '{detected_name}'")
                            
        except ImportError as imp_err:
            logger.warning(f"Auto-refinement imports failed (skipping): {imp_err}")
        except Exception as e:
            logger.warning(f"Section {current_idx + 1}: Auto-refinement skipped due to error: {e}")

        # Rate limit protection: wait before next section
        if current_idx < total - 1:
            logger.info(f"Section {current_idx + 1} complete. Waiting 5s to avoid API rate limits...")
            import asyncio
            await asyncio.sleep(5)
        
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
            "detected_products": detected_products,
            "last_error": "",  # Clear error on success
            "operations_count": state.get("operations_count", 0) + 2,  # 2 LLM calls
        }
        
    except Exception as e:
        logger.error(f"Section {current_idx + 1} generation failed: {e}")
        logger.warning(f"HOLDING at section {current_idx + 1} — click Execute to retry")
        return {
            **state,
            "current_section_index": current_idx,  # HOLD
            "last_error": f"Section {current_idx + 1} failed: {e}. Click Execute again to retry.",
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
        blog_parts.append(f"## {title}\n\n")
        
        # Add section content (ensure it doesn't have duplicate H2)
        if content.startswith("## "):
            content = content.split("\n", 1)[-1].lstrip()
        
        blog_parts.append(f"{content}\n\n")
        
        # Add separator (except for last section)
        if i < len(sections):
            blog_parts.append("---\n\n")
    
    # Join everything
    assembled_blog = "".join(blog_parts)
    
    # === POST-PROCESSING: Clean ALL heading numbers in assembled blog ===
    from core.post_processors.heading_cleaner import clean_heading_numbers
    assembled_blog = clean_heading_numbers(assembled_blog)
    logger.info("Blog assembler: All heading number prefixes cleaned")
    
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
