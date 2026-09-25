"""Universal product selector: Uses LLM to extract authentic products 
from competitor analysis for ANY product category (laptops, watches, 
dental tech, farm equipment, cameras, etc.)."""
from __future__ import annotations
import re
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.config import logger


# Known OLD chip/model markers (2024 or earlier)
_OLD_MARKERS = [
    r"\bm3\b", r"\bm2\b", r"\bm1\b",          # Apple M3 and older
    r"\(2024\)", r"\(2023\)", r"\(2022\)",      # Explicit old years
    r"\bgen\s*1[0-2]\b",                        # ThinkPad Gen 10-12
    r"\bintel\s*core\s*(i[3579]-1[0-3])\b",     # Intel 10th-13th gen
    r"\bryzen\s*[579]\s*[567]\d{3}\b",          # Ryzen 5000/7000 (older)
    r"\brtx\s*[34]0\d{2}\b",                    # RTX 30/40 series
]
# Known NEW chip/model markers (2025-2026)
_NEW_MARKERS = [
    r"\bm4\b", r"\bm5\b",                        # Apple M4/M5
    r"\(2025\)", r"\(2026\)",
    r"\bgen\s*1[3-9]\b",                         # ThinkPad Gen 13+
    r"\bintel\s*core\s*ultra\b",                 # Intel Core Ultra (new)
    r"\bryzen\s*ai\b", r"\bryzen\s*9\s*9\d{3}\b", # Ryzen AI / 9000 series
    r"\brtx\s*50\d{2}\b",                        # RTX 50 series
]


def detect_product_freshness(product_name: str, current_year: int = None) -> Dict:
    """Detect if a product is outdated based on name markers.
    Returns {is_outdated, detected_year, confidence}."""
    if current_year is None:
        current_year = datetime.now().year
    name_lower = product_name.lower()

    is_old = any(re.search(p, name_lower) for p in _OLD_MARKERS)
    is_new = any(re.search(p, name_lower) for p in _NEW_MARKERS)

    # Try to find explicit year
    year_match = re.search(r"\(?(20\d{2})\)?", product_name)
    detected_year = int(year_match.group(1)) if year_match else None

    if is_old and not is_new:
        return {"is_outdated": True, "detected_year": detected_year or (current_year - 2),
                "confidence": "high"}
    if is_new and not is_old:
        return {"is_outdated": False, "detected_year": detected_year or current_year,
                "confidence": "high"}
    if detected_year:
        outdated = (current_year - detected_year) > 1
        return {"is_outdated": outdated, "detected_year": detected_year,
                "confidence": "high"}
    # No marker found -> unknown, do NOT reject
    return {"is_outdated": False, "detected_year": None, "confidence": "unknown"}


def filter_outdated_products(products: List[Dict], current_year: int = None):
    """Safety-net filter using LLM release_year (primary) + markers (fallback).
    
    Now lenient: only removes products that are CLEARLY outdated WITH a 
    newer version available. Old products without updates are KEPT.
    """
    if current_year is None:
        current_year = datetime.now().year
    
    kept, removed = [], []
    
    for p in products:
        name = p.get("name", "")
        llm_year = p.get("release_year")
        has_update = bool(p.get("updated_version_name"))
        
        # If LLM gave year AND product has newer version AND very old
        if llm_year and isinstance(llm_year, int) and has_update:
            age = current_year - llm_year
            if age > 2:  # More than 2 years old WITH update available
                removed.append(p)
                logger.warning(
                    f"Outdated with update ({llm_year}, {age}y): {name} -> REMOVED"
                )
                continue
        
        # Fallback to marker detection if no release_year or no update info
        freshness = detect_product_freshness(name, current_year)
        p["product_year"] = p.get("release_year") or freshness.get("detected_year")
        p["freshness_confidence"] = freshness.get("confidence")
        
        if freshness["is_outdated"] and has_update:
            removed.append(p)
            logger.warning(
                f"Outdated with update (marker): {name} -> REMOVED"
            )
            continue
            
        # Keep product (either recent, or old but no update)
        kept.append(p)
    
    return kept, removed


EXTRACTION_PROMPT_TEMPLATE = """You are an expert product analyst and competitive researcher.

I have analyzed competitor articles for the topic: "{topic}"

Below is the combined content scraped from {competitor_count} top competitor articles. 
Your task is to extract ALL SPECIFIC PRODUCTS that are genuinely recommended or 
reviewed by these competitors.

=== COMPETITOR CONTENT ===
{competitor_content}

=== OPTIMAL STRUCTURE (H2/H3 headings from competitors) ===
{structure_content}

=== EXTRACTION RULES ===

1. Extract ONLY SPECIFIC products with brand + model name
   - GOOD: "Dell XPS 15 9530", "Apple Watch Ultra 2", "John Deere 5075E Tractor"
   - BAD: "laptop", "smartwatch", "a good tractor", "Dell" (brand only)

2. Include products from ALL price tiers if available:
   - Premium/Flagship (highest-end, most expensive)
   - Mid-range/Value (balanced performance and price)
   - Budget/Entry-level (affordable options)

3. For EACH product, extract:
   - Full product name (brand + model + variant if applicable)
   - Brand name (alone)
   - Tier category (premium / mid_range / budget)
   - release_year: The year it was launched (integer like 2026, or null if unknown)
   - release_month: The month it was launched (like "March", or null if unknown)
   - updated_version_name: If a newer version exists, name it (e.g., "MacBook Air M5 (2026)"), or null if none
   - why_notable: Brief reason based on competitor mentions (1 sentence)
   - popularity_score: How many competitors mentioned it (1-10)
   - selling_points: 3-5 bullet points from competitor reviews
   - pros: From competitor reviews
   - cons: From competitor reviews

4. Be AUTHENTIC — only include products that competitors ACTUALLY mentioned 
   with specific details. Do NOT invent products.

5. TARGET: Extract ALL specific products mentioned in the competitor content.
   - There may be anywhere from 5 to 30 products — extract what's actually there
   - Do NOT invent products to reach a target number
   - Do NOT add products not mentioned in the content
   - Quality over quantity: better to extract 8 real products than 20 with fake ones
   - Minimum: Extract at least 5 products if available
   - Maximum: No limit — extract every specific product mentioned

6. RELEASE DATE EXTRACTION: For EACH product, determine release_year and release_month accurately. Do not confuse review date with release date.

7. UPDATED VERSION DETECTION: For EACH product, check if a newer version exists. Set updated_version_name or null.

8. DO NOT FILTER: Extract ALL products mentioned, regardless of age. Do not reject old products. Selection happens in a separate step.

=== OUTPUT FORMAT ===

Return ONLY valid JSON in this EXACT structure (no markdown, no explanation):

{{
  "products": [
    {{
      "name": "Full Brand Model Name",
      "brand": "Brand Name",
      "tier": "premium",
      "release_year": 2026,
      "release_month": "March",
      "updated_version_name": null,
      "why_notable": "Brief reason based on competitor mentions",
      "popularity_score": 8,
      "selling_points": ["Point 1", "Point 2", "Point 3"],
      "pros": ["Pro 1", "Pro 2", "Pro 3"],
      "cons": ["Con 1", "Con 2"],
      "source_competitors": ["competitor1.com", "competitor2.com"]
    }}
  ],
  "category_detected": "e.g., laptop / smartwatch / dental equipment",
  "total_products_found": 10,
  "extraction_confidence": 0.95,
  "extraction_notes": "Brief note about extraction quality"
}}

Return ONLY the JSON object. No text before or after. No markdown fences."""


def _extract_structure_headings_only(competitor_data: Dict[str, Any]) -> str:
    """Extract just headings from competitor data."""
    parts = []
    structure = competitor_data.get("optimal_structure", [])
    if not structure:
        structure = competitor_data.get("extracted_headings", [])
    for section in structure[:30]:
        title = section.get("title", "")
        if title:
            parts.append(title)
    return "\n".join(parts)


async def extract_products_universal(
    topic: str,
    competitor_data: Dict[str, Any],
    target_count: int = 10,
) -> Dict[str, Any]:
    """
    Use LLM to extract authentic products with 3-stage fallback.
    
    Stage 1: Extract from competitor scraped content
    Stage 2: Extract from optimal_structure headings  
    Stage 3: LLM auto-generates based on topic (final fallback)
    
    Always aims for target_count products. If fewer found, suggests popular alternatives.
    """
    try:
        from backend.llm.router import LLMRouter
        
        competitor_count = competitor_data.get("competitor_count", 0)
        products = []
        extraction_method = "none"
        result = {}
        
        # === STAGE 1: Try competitor scraped content ===
        logger.info("🔍 Stage 1a: Trying competitor scraped content (extracting all)...")
        
        # === DEBUG: Log competitor_data structure ===
        logger.info(f"🔍 DEBUG: competitor_data keys = {list(competitor_data.keys())}")
        
        _articles = competitor_data.get("scraped_articles") or competitor_data.get("competitors") or []
        logger.info(f"🔍 DEBUG: articles count = {len(_articles)}")
        
        if _articles:
            first = _articles[0]
            logger.info(f"🔍 DEBUG: first article keys = {list(first.keys())}")
            logger.info(f"🔍 DEBUG: first article content length = {len(first.get('content', ''))}")
            logger.info(f"🔍 DEBUG: first article has tables = {bool(first.get('tables'))}")
            logger.info(f"🔍 DEBUG: first article h2_titles = {first.get('h2_titles', first.get('h2_headings', []))[:3]}")
            logger.info(f"🔍 DEBUG: first article h3_titles = {first.get('h3_titles', first.get('h3_headings', []))[:3]}")
        
        competitor_content = _build_competitor_content(competitor_data)
        structure_content = _build_structure_content(competitor_data)
        
        logger.info(f"🔍 DEBUG: competitor_content length = {len(competitor_content)}")
        logger.info(f"🔍 DEBUG: structure_content length = {len(structure_content)}")
        
        if competitor_content or structure_content:
            MAX_COMBINED = 12000  # Leave room for prompt + JSON response
            total_size = len(competitor_content) + len(structure_content)

            if total_size > MAX_COMBINED:
                # Proportionally truncate
                ratio = MAX_COMBINED / total_size
                new_comp_len = int(len(competitor_content) * ratio)
                new_struct_len = int(len(structure_content) * ratio)
                
                logger.info(f"🔍 Truncating combined content: {total_size} -> {MAX_COMBINED} chars")
                competitor_content = competitor_content[:new_comp_len] + "\n... (truncated)"
                structure_content = structure_content[:new_struct_len] + "\n... (truncated)"
            
            current_year = datetime.now().year
            prompt = EXTRACTION_PROMPT_TEMPLATE.format(
                topic=topic,
                competitor_count=competitor_count,
                competitor_content=competitor_content,
                structure_content=structure_content,
                # target_count removed - extraction is now dynamic
            )
            
            logger.info(f"🤖 Stage 1a: Sending extraction request")
            router = LLMRouter(task_type="competitor_analysis")
            response = await router.generate_text(
                prompt=prompt,
                system_prompt="Return ONLY valid JSON, no other text.",
            )
            
            result = _parse_llm_response(response)
            products = _validate_and_enrich(result.get("products", []), target_count * 2)

            # If Stage 1a failed (no products), retry with simpler prompt
            if not products:
                logger.warning("⚠️ Stage 1a returned 0 products, retrying with simpler prompt...")
                
                simple_prompt = f"""Extract product names from this content about "{topic}":

{competitor_content[:5000]}

Return ONLY JSON: {{"products": [{{"name": "Product Name", "brand": "Brand", "tier": "premium"}}]}}
Extract up to {target_count * 2} products."""
                
                router = LLMRouter(task_type="competitor_analysis")
                retry_response = await router.generate_text(
                    prompt=simple_prompt,
                    system_prompt="Return ONLY valid JSON.",
                )
                
                retry_result = _parse_llm_response(retry_response)
                products = _validate_and_enrich(retry_result.get("products", []), target_count * 2)
                
                if products:
                    logger.info(f"✅ Stage 1a retry succeeded: {len(products)} products")
                    result = retry_result
            
            if products:
                extraction_method = "competitor_content"
                logger.info(f"✅ Stage 1a: Extracted {len(products)} candidate products")
                
                # === Stage 1b: Intelligent Selection (only if we have more than target) ===
                if len(products) > target_count:
                    logger.info(f"🧠 Stage 1b: Intelligent selection ({len(products)} -> {target_count})")
                    selection_result = await intelligent_product_selection(
                        products=products,
                        target_count=target_count,
                        current_year=current_year,
                    )
                    products = selection_result.get("selected_products", products[:target_count])
                    rejected = selection_result.get("rejected_products", [])
                    
                    if rejected:
                        logger.info(
                            f"🗑️ Stage 1b rejected {len(rejected)} products: "
                            f"{[r.get('name', '') for r in rejected]}"
                        )
                else:
                    # We have fewer than target — keep all, let Stage 3 top-up
                    logger.info(f"Stage 1b skipped (only {len(products)} products, target {target_count})")
                
                # === Stage 1c: Tier Balance ===
                all_products = _validate_and_enrich(result.get("products", []), target_count * 2)
                products = balance_tiers(products, all_products, target_count)
                
                # Apply safety-net filter
                products, removed = filter_outdated_products(products, current_year)
                if removed:
                    logger.info(
                        f"🗑️ Safety-net filter removed {len(removed)} products: "
                        f"{[p['name'] for p in removed]}"
                    )
        
        # === STAGE 2: Try structure headings only (if Stage 1 failed or < target) ===
        if len(products) < target_count:
            logger.info(f"🔍 Stage 2: Trying structure headings (have {len(products)}, need {target_count})...")
            structure_headings = _extract_structure_headings_only(competitor_data)
            
            if structure_headings:
                stage2_prompt = f"""Extract product names from these headings about "{topic}":

{structure_headings}

If fewer than {target_count} found, suggest popular alternatives to reach {target_count}.

Return ONLY JSON with "products" array, "category_detected", "extraction_confidence" (0.7), "extraction_notes".
Each product needs: name, brand, tier, why_notable, popularity_score, selling_points, pros, cons, source_competitors"""
                
                logger.info(f"🤖 Stage 2: Sending structure extraction")
                router = LLMRouter(task_type="competitor_analysis")
                response = await router.generate_text(
                    prompt=stage2_prompt,
                    system_prompt="Return ONLY valid JSON.",
                )
                
                stage2_result = _parse_llm_response(response)
                stage2_products = _validate_and_enrich(stage2_result.get("products", []), target_count)
                
                # Merge with existing (avoid duplicates)
                existing_names = {p["name"].lower() for p in products}
                for p in stage2_products:
                    if p["name"].lower() not in existing_names:
                        products.append(p)
                        existing_names.add(p["name"].lower())
                
                if not result:
                    result = stage2_result
                
                if products:
                    extraction_method = "structure_headings"
                    logger.info(f"✅ Stage 2: Now have {len(products)} products total")
        
        # === STAGE 3: LLM auto-generate (final fallback) ===
        if len(products) < target_count:
            logger.info(f"🔍 Stage 3: Auto-generating to reach {target_count} products...")
            
            # Build context from existing products
            existing_summary = ""
            if products:
                names = [p["name"] for p in products[:5]]
                existing_summary = f"\n\nAlready found: {', '.join(names)}"
            
            stage3_prompt = f"""You are a product research expert. Generate a list of 
{target_count} popular, authentic products for the topic: "{topic}"{existing_summary}

=== REQUIREMENTS ===
1. Generate {target_count} REAL products (no duplicates with existing)
2. Mix tiers: {target_count//3} premium, {target_count//3} mid_range, {target_count//3} budget
3. Use REAL brand names and REAL model names
4. Products must be relevant to 2026 market
5. If existing products provided, DO NOT repeat them

Return ONLY JSON:
{{
  "products": [
    {{
      "name": "Brand Model",
      "brand": "Brand",
      "tier": "premium",
      "why_notable": "Popular for this use case",
      "popularity_score": 7,
      "selling_points": ["Feature 1", "Feature 2"],
      "pros": ["Pro 1"],
      "cons": ["Con 1"],
      "source_competitors": [],
      "source_type": "auto_suggested"
    }}
  ],
  "category_detected": "category",
  "total_products_found": {target_count},
  "extraction_confidence": 0.6,
  "extraction_notes": "Auto-generated to reach target"
}}"""
            
            logger.info(f"🤖 Stage 3: Sending auto-generation request")
            router = LLMRouter(task_type="competitor_analysis")
            response = await router.generate_text(
                prompt=stage3_prompt,
                system_prompt="Return ONLY valid JSON with real product names.",
            )
            
            stage3_result = _parse_llm_response(response)
            stage3_products = _validate_and_enrich(stage3_result.get("products", []), target_count)
            
            # Merge with existing
            existing_names = {p["name"].lower() for p in products}
            added = 0
            for p in stage3_products:
                if p["name"].lower() not in existing_names and len(products) < target_count:
                    p["source_type"] = "auto_suggested"
                    products.append(p)
                    existing_names.add(p["name"].lower())
                    added += 1
            
            if not result:
                result = stage3_result
            
            if added > 0:
                extraction_method = "auto_generated" if not products[:-added] else "hybrid"
                logger.info(f"✅ Stage 3: Added {added} products, total now {len(products)}")
        
        # === Final Result ===
        # Ensure we have result dict even if all stages failed
        if not result:
            result = {
                "category_detected": "unknown",
                "extraction_confidence": 0.0,
                "extraction_notes": "All stages failed",
            }
        
        # === FRESHNESS FILTER & TOP-UP ===
        products, removed = filter_outdated_products(products)
        if removed:
            logger.info(f"🗑️ Freshness filter removed {len(removed)} outdated products: "
                        f"{[p['name'] for p in removed]}")
        
        if len(products) < target_count:
            logger.info(f"🔄 Product count dropped to {len(products)} (< target {target_count}) after freshness filtering. Running top-up auto-generation...")
            try:
                existing_summary = f"\n\nAlready found: {', '.join(p['name'] for p in products[:5])}" if products else ""
                current_yr = datetime.now().year
                topup_prompt = f"""You are a product research expert. Generate a list of 
{target_count - len(products)} popular, authentic products released in {current_yr} or {current_yr-1} for the topic: "{topic}"{existing_summary}

=== REQUIREMENTS ===
1. Generate REAL products released in {current_yr} or {current_yr-1} (no duplicates with existing)
2. Use REAL brand names and REAL model names (e.g. M4, Core Ultra, Gen 13, 2026/2025 models)
3. DO NOT include 2024 or earlier products (no M3, Gen 12, 2024 models)

Return ONLY JSON:
{{
  "products": [
    {{
      "name": "Brand Model",
      "brand": "Brand",
      "tier": "premium",
      "why_notable": "Popular for this use case",
      "popularity_score": 7,
      "selling_points": ["Feature 1", "Feature 2"],
      "pros": ["Pro 1"],
      "cons": ["Con 1"],
      "source_competitors": [],
      "source_type": "auto_suggested"
    }}
  ],
  "category_detected": "category",
  "total_products_found": {target_count},
  "extraction_confidence": 0.6,
  "extraction_notes": "Top-up after freshness filtering"
}}"""
                router = LLMRouter(task_type="competitor_analysis")
                topup_response = await router.generate_text(
                    prompt=topup_prompt,
                    system_prompt="Return ONLY valid JSON with real current product names.",
                )
                topup_result = _parse_llm_response(topup_response)
                topup_products = _validate_and_enrich(topup_result.get("products", []), target_count - len(products))
                
                existing_names = {p["name"].lower() for p in products}
                for p in topup_products:
                    if p["name"].lower() not in existing_names and len(products) < target_count:
                        p["source_type"] = "auto_suggested"
                        products.append(p)
                        existing_names.add(p["name"].lower())
                logger.info(f"✅ Top-up added products, total now {len(products)}")
            except Exception as e:
                logger.warning(f"Top-up generation failed: {e}")

        # Sort by popularity and limit to target_count
        products.sort(key=lambda x: x.get("popularity_score", 0), reverse=True)
        products = products[:target_count]
        
        output = {
            "products": products,
            "category_detected": result.get("category_detected", "unknown"),
            "extraction_confidence": float(result.get("extraction_confidence", 0.5)),
            "extraction_notes": result.get("extraction_notes", ""),
            "source_competitor_count": competitor_count,
            "extraction_method": extraction_method,
        }
        
        logger.info(f"🛒 Final: {len(products)} products via {extraction_method}")
        for i, p in enumerate(products[:5], 1):
            source = p.get("source_type", "unknown")
            logger.info(f"   {i}. {p['name']} ({p['tier']}, {source})")
        
        return output
        
    except Exception as e:
        logger.error(f"Product extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "products": [],
            "category_detected": "unknown",
            "extraction_confidence": 0.0,
            "extraction_notes": f"Failed: {e}",
            "extraction_method": "failed",
        }


def _html_to_markdown(html: str) -> str:
    """Convert HTML to structured markdown (like Firecrawl but free).
    
    Preserves:
    - Headings (h1-h6 → # to ######)
    - Lists (ul/ol → - or 1.)
    - Bold/italic (strong/em → **/* )
    - Links (a → [text](url))
    - Tables (table → markdown table)
    - Blockquotes (blockquote → >)
    """
    try:
        from bs4 import BeautifulSoup, Tag, NavigableString
    except ImportError:
        return html
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove unwanted elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()
    
    # Find main content area
    main = (
        soup.find("main") or 
        soup.find("article") or 
        soup.find("div", class_="content") or
        soup.find("div", class_="article-body") or
        soup.find("div", id="content") or
        soup.body
    )
    
    if not main:
        main = soup
    
    markdown_lines = []
    
    def element_to_md(element) -> str:
        if isinstance(element, NavigableString):
            return str(element)
        if not isinstance(element, Tag):
            return ""
        
        tag_name = element.name
        
        if tag_name in ['strong', 'b']:
            inner = "".join(element_to_md(c) for c in element.children).strip()
            return f" **{inner}** " if inner else ""
        if tag_name in ['em', 'i']:
            inner = "".join(element_to_md(c) for c in element.children).strip()
            return f" *{inner}* " if inner else ""
        if tag_name == 'a':
            inner = "".join(element_to_md(c) for c in element.children).strip()
            href = element.get('href', '')
            return f" [{inner}]({href}) " if inner and href else inner
        
        return "".join(element_to_md(c) for c in element.children)

    def process_element(element):
        if isinstance(element, NavigableString):
            t = element.strip()
            if t:
                markdown_lines.append(t)
            return
        if not isinstance(element, Tag):
            return
        
        tag_name = element.name
        
        # Headings
        if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(tag_name[1])
            text = element_to_md(element).strip()
            if text:
                markdown_lines.append(f"\n{'#' * level} {text}\n")
            return
        
        # Paragraphs
        if tag_name == 'p':
            text = element_to_md(element)
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                markdown_lines.append(f"{text}\n")
            return
        
        # Lists
        if tag_name in ['ul', 'ol']:
            for i, li in enumerate(element.find_all('li', recursive=False)):
                text = element_to_md(li)
                text = re.sub(r'\s+', ' ', text).strip()
                if text:
                    prefix = "-" if tag_name == 'ul' else f"{i+1}."
                    markdown_lines.append(f"{prefix} {text}")
            markdown_lines.append("")
            return
        
        # Tables
        if tag_name == 'table':
            rows = element.find_all('tr')
            if rows:
                # Header row
                header_cells = rows[0].find_all(['th', 'td'])
                header = " | ".join(element_to_md(cell).strip() for cell in header_cells)
                markdown_lines.append(f"| {header} |")
                markdown_lines.append("|" + "---|" * len(header_cells))
                
                # Data rows
                for row in rows[1:]:
                    cells = row.find_all(['th', 'td'])
                    row_text = " | ".join(element_to_md(cell).strip() for cell in cells)
                    markdown_lines.append(f"| {row_text} |")
                markdown_lines.append("")
            return
        
        # Blockquotes
        if tag_name == 'blockquote':
            text = element_to_md(element).strip()
            if text:
                for line in text.split('\n'):
                    markdown_lines.append(f"> {line.strip()}")
                markdown_lines.append("")
            return
        
        # Recursively process children
        for child in element.children:
            process_element(child)
    
    # Start processing
    process_element(main)
    
    # Clean up excessive newlines
    result = '\n'.join(markdown_lines)
    result = '\n'.join(line for line in result.split('\n') if line.strip() or line == '')
    
    return result


def _extract_h2_h3(article: Dict[str, Any]) -> tuple[List[str], List[str]]:
    """Extract H2 and H3 headings from article data.
    
    Handles multiple data formats:
    - List of strings: ["Heading 1", "Heading 2"]
    - List of dicts: [{"text": "Heading", "level": 2}, ...]
    - Dict format: {"h2": [...], "h3": [...]}
    - Empty/None: returns ([], [])
    """
    h2s = []
    h3s = []
    
    # First, check for direct h2_titles/h2_headings/h3_titles/h3_headings fields (preferred)
    raw_h2s = article.get("h2_titles") or article.get("h2_headings") or []
    h2s = raw_h2s[:15] if isinstance(raw_h2s, list) else []
    
    raw_h3s = article.get("h3_titles") or article.get("h3_headings") or []
    h3s = raw_h3s[:20] if isinstance(raw_h3s, list) else []
    
    # If we already have headings, return them
    if h2s or h3s:
        return h2s, h3s
    
    # Fallback: extract from "headings" field
    headings = article.get("headings")
    
    # Handle None or empty
    if not headings:
        return [], []
    
    # Handle dict format: {"h2": [...], "h3": [...]}
    if isinstance(headings, dict):
        h2s = headings.get("h2", [])[:15] if isinstance(headings.get("h2"), list) else []
        h3s = headings.get("h3", [])[:20] if isinstance(headings.get("h3"), list) else []
        return h2s, h3s
    
    # Handle list format
    if isinstance(headings, list):
        if not headings:  # Empty list
            return [], []
        
        # Check first element type (safely)
        first = headings[0] if headings else None
        
        # List of strings
        if isinstance(first, str):
            # Treat all as H2 (no level info)
            h2s = headings[:15]
            return h2s, []
        
        # List of dicts with "level" field
        if isinstance(first, dict):
            for h in headings:
                if not isinstance(h, dict):
                    continue
                text = h.get("text", h.get("title", ""))
                level = h.get("level", 2)
                
                if not text:
                    continue
                
                if level == 2:
                    if len(h2s) < 15:
                        h2s.append(text)
                elif level == 3:
                    if len(h3s) < 20:
                        h3s.append(text)
            return h2s, h3s
    
    # Unknown format: return empty
    logger.debug(f"Unknown headings format: {type(headings)}")
    return [], []
def _build_competitor_content(competitor_data: Dict[str, Any]) -> str:
    """Build structured markdown from competitor scraped articles.
    
    Reads ALL available fields: content, tables, h2/h3 titles, snippets.
    Converts HTML content to markdown. Falls back gracefully.
    """
    articles = (
        competitor_data.get("scraped_articles") or
        competitor_data.get("competitors") or
        competitor_data.get("sources") or
        []
    )
    
    if not articles:
        logger.warning("🔍 _build_competitor_content: No articles found in competitor_data")
        return ""
    
    content_parts = []
    
    for i, article in enumerate(articles[:10], 1):
        url = article.get("url", "unknown")
        title = article.get("title", "")
        section_parts = []
        
        # Header
        header = f"### Article {i}: {title or url}"
        section_parts.append(header)
        
        # 1. Tables (highest priority for product names & specs)
        tables = article.get("tables", [])
        if tables:
            section_parts.append("\n**[COMPARISON TABLES]**")
            for t_idx, table in enumerate(tables[:3]):
                section_parts.append(f"Table {t_idx + 1}:\n{table}")
        
        # 2. H2/H3 Headings (product names usually here)
        h2s, h3s = _extract_h2_h3(article)
        if not isinstance(h2s, list):
            h2s = []
        if not isinstance(h3s, list):
            h3s = []
        if h2s or h3s:
            section_parts.append("\n**[ARTICLE STRUCTURE]**")
            for h in h2s[:15]:
                section_parts.append(f"H2: {h}")
            for h in h3s[:20]:
                section_parts.append(f"H3: {h}")
        
        # 3. Main content (convert HTML to markdown if needed)
        raw_content = article.get("content", "")
        if raw_content and len(raw_content) > 20:
            is_html = raw_content.strip()[:50].lower().startswith(("<!doctype", "<html", "<body", "<div", "<p>", "<h1", "<h2", "<main"))
            
            if is_html:
                try:
                    markdown = _html_to_markdown(raw_content)
                    if markdown and len(markdown) > 10:
                        # Truncate to 3000 chars per article
                        if len(markdown) > 3000:
                            markdown = markdown[:3000] + "\n... (truncated)"
                        section_parts.append(f"\n**[FULL CONTENT]**\n{markdown}")
                except Exception as e:
                    logger.debug(f"HTML conversion failed for {url}: {e}")
                    snippet = article.get("content_snippet", raw_content[:1000])
                    section_parts.append(f"\n**[CONTENT EXCERPT]**\n{snippet}")
            else:
                if len(raw_content) > 3000:
                    raw_content = raw_content[:3000] + "\n... (truncated)"
                section_parts.append(f"\n**[FULL CONTENT]**\n{raw_content}")
        
        # 4. Fallback: content_snippet if no content
        elif article.get("content_snippet"):
            section_parts.append(f"\n**[CONTENT EXCERPT]**\n{article['content_snippet'][:1000]}")
        
        if len(section_parts) > 1:
            content_parts.append("\n".join(section_parts))
    
    result = "\n\n---\n\n".join(content_parts)
    
    if not result:
        logger.warning("🔍 _build_competitor_content: All articles produced empty content")
    
    return result[:15000]


def _build_structure_content(competitor_data: Dict[str, Any]) -> str:
    """Build structure content from H2/H3 headings with clear hierarchy.
    
    Reads both h2_titles/h2_headings and h3_titles/h3_headings field names.
    """
    articles = (
        competitor_data.get("scraped_articles") or
        competitor_data.get("competitors") or
        competitor_data.get("sources") or
        []
    )
    
    if not articles:
        return ""
    
    structure_parts = []
    
    for i, article in enumerate(articles[:10], 1):
        url = article.get("url", "unknown")
        
        h2s, h3s = _extract_h2_h3(article)
        if not isinstance(h2s, list):
            h2s = []
        if not isinstance(h3s, list):
            h3s = []
        
        if not h2s and not h3s:
            continue
        
        lines = [f"#### Article {i}: {url}\n"]
        
        if h2s:
            lines.append("**H2 Headings (Main Sections):**")
            for h2 in h2s[:15]:
                lines.append(f"- {h2}")
            lines.append("")
        
        if h3s:
            lines.append("**H3 Headings (Sub-sections — often product names):**")
            for h3 in h3s[:20]:
                lines.append(f"  - {h3}")
            lines.append("")
        
        structure_parts.append("\n".join(lines))
    
    optimal = competitor_data.get("optimal_structure", [])
    if optimal:
        lines = ["#### Optimal Structure (from competitor analysis)\n"]
        for section in optimal[:30]:
            if isinstance(section, dict):
                title = section.get("title", "")
                if title:
                    lines.append(f"- {title}")
            elif isinstance(section, str):
                lines.append(f"- {section}")
        structure_parts.append("\n".join(lines))
    
    return "\n\n".join(structure_parts)


def _parse_llm_response(response: str) -> Dict[str, Any]:
    """Parse JSON from LLM response with multiple fallbacks and debug logging."""
    
    # DEBUG: Log raw response length and preview
    logger.debug(f"🔍 DEBUG: LLM response length = {len(response or '')}")
    if response:
        logger.debug(f"🔍 DEBUG: LLM response preview = {response[:200]}...")
    
    # Try 1: Direct JSON parse
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError as e:
        logger.warning(f"Direct JSON parse failed: {e}")
    
    # Try 2: Extract JSON block from markdown fences
    fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response, re.DOTALL)
    if fence_match:
        try:
            parsed = json.loads(fence_match.group(1))
            logger.info("✅ Extracted JSON from markdown fences")
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"Fence extraction failed: {e}")
    
    # Try 3: Find first { to last }
    brace_match = re.search(r'\{[\s\S]*\}', response)
    if brace_match:
        try:
            parsed = json.loads(brace_match.group(0))
            logger.info("✅ Extracted JSON from braces")
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"Brace extraction failed: {e}")
            # DEBUG: Show what we tried to parse
            logger.warning(f"Failed JSON (first 500 chars): {brace_match.group(0)[:500]}")
    
    # Try 4: Fix common JSON issues and retry
    cleaned = response.strip()
    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)  # Trailing commas
    cleaned = re.sub(r'(\w+):', r'"\1":', cleaned)     # Unquoted keys
    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)  # Control chars
    try:
        parsed = json.loads(cleaned)
        logger.info("✅ Parsed after cleanup")
        return parsed
    except json.JSONDecodeError as e:
        logger.error(f"❌ All JSON parsing attempts failed: {e}")
        # DEBUG: Show full response for debugging
        logger.error(f"Full LLM response (first 1000 chars):\n{response[:1000]}")
        return {"products": []}


def _validate_and_enrich(products: List[Dict], target_count: int) -> List[Dict]:
    """Validate and enrich extracted products."""
    validated = []
    seen_names = set()
    
    for p in products:
        if not isinstance(p, dict):
            continue
        
        name = (p.get("name") or "").strip()
        if not name or len(name) < 5:
            continue
        
        # Deduplicate (case-insensitive)
        name_lower = name.lower()
        if name_lower in seen_names:
            continue
        
        # Check for substring duplicates
        is_duplicate = False
        for seen in list(seen_names):
            if name_lower in seen or seen in name_lower:
                is_duplicate = True
                break
        if is_duplicate:
            continue
        
        seen_names.add(name_lower)
        
        # Handle release date fields
        ry = p.get("release_year")
        try:
            ry = int(ry) if ry is not None else None
        except (ValueError, TypeError):
            ry = None

        rm = p.get("release_month")
        rm = str(rm).strip() if rm else None

        uvn = p.get("updated_version_name")
        uvn = str(uvn).strip() if uvn else None

        # Normalize fields with defaults
        validated.append({
            "name": name,
            "brand": (p.get("brand") or _extract_brand(name)).strip(),
            "tier": _normalize_tier(p.get("tier", "mid_range")),
            "release_year": ry,
            "release_month": rm,
            "updated_version_name": uvn,
            "why_notable": p.get("why_notable", ""),
            "popularity_score": _safe_int(p.get("popularity_score", 1), 1, 10),
            "selling_points": _safe_list(p.get("selling_points", []), max_items=5),
            "pros": _safe_list(p.get("pros", []), max_items=5),
            "cons": _safe_list(p.get("cons", []), max_items=5),
            "source_competitors": _safe_list(p.get("source_competitors", []), max_items=5),
            "source_type": p.get("source_type", "unknown"),
        })
        
        if len(validated) >= target_count * 2:
            break
    
    # Sort by popularity score (highest first)
    validated.sort(key=lambda x: x.get("popularity_score", 0), reverse=True)

    # After validating products, flag suspicious ones
    suspicious = []
    for p in validated:
        name = p.get("name", "")
        # Flag discontinued/generic names
        if any(word in name.lower() for word in ["discontinued", "legacy", "old"]):
            suspicious.append(p["name"])
        # Flag very short names (likely generic)
        if len(name.split()) < 2:
            suspicious.append(p["name"])

    if suspicious:
        logger.warning(f"⚠️ Potentially hallucinated products: {suspicious}")
    
    return validated[:target_count]


SELECTION_PROMPT_TEMPLATE = """You are an expert product analyst making smart selection decisions for a buying guide article.

Current year: {current_year}
Target: Select the {target_count} BEST products from the candidates below.

=== CANDIDATE PRODUCTS ===
{products_json}

=== SELECTION CRITERIA (in order of importance) ===
1. FRESHNESS: Prefer products from {current_year} or {current_year_minus_1}.
   HOWEVER, keep older products if NO newer version exists.
   Example: "ThinkPad X1 Carbon Gen 11 (2023)" with no Gen 12/13 = KEEP
   Example: "MacBook Air M3 (2024)" when M5 exists = REJECT

2. UPDATED VERSIONS: If a product has updated_version_name, strongly prefer the NEWER version. Only keep the old one if it offers exceptional value.

3. MARKET RELEVANCE: Prefer products with high popularity_score.

4. TIER DIVERSITY: Prefer natural mix of premium/mid_range/budget.
   Do NOT force distribution - select BEST products regardless of tier.
   Only ensure at least 1 product from each tier if available.

5. FEATURE IMPORTANCE: Prefer products with notable features.

6. COMPETITOR CONSENSUS: Products mentioned by more competitors rank higher.

=== OUTPUT FORMAT ===
Return ONLY valid JSON:
{{
  "selected_products": [
    {{
      "name": "Product Name",
      "selection_score": 9.5,
      "reasoning": "Why this product was selected (1 sentence)",
      "decision": "keep"
    }}
  ],
  "rejected_products": [
    {{
      "name": "Product Name",
      "reasoning": "Why rejected (1 sentence)",
      "rejection_reason": "outdated_with_update|low_relevance|tier_imbalance|other"
    }}
  ],
  "tier_distribution": {{
    "premium": 3,
    "mid_range": 2,
    "budget": 2
  }}
}}

Sort selected_products by selection_score (highest first).
Return EXACTLY {target_count} selected products (or fewer if candidates < target).
"""


async def intelligent_product_selection(
    products: List[Dict],
    target_count: int,
    current_year: int = None,
) -> Dict[str, Any]:
    """Stage 1b: Intelligently select best products using LLM reasoning.
    
    Returns dict with selected_products, rejected_products, tier_distribution.
    """
    if current_year is None:
        current_year = datetime.now().year
    
    if not products:
        return {
            "selected_products": [],
            "rejected_products": [],
            "tier_distribution": {},
        }
    
    # If fewer products than target, keep all
    if len(products) <= target_count:
        return {
            "selected_products": [
                {
                    "name": p["name"],
                    "selection_score": p.get("popularity_score", 5),
                    "reasoning": "Included (not enough candidates to filter)",
                    "decision": "keep",
                    **{k: v for k, v in p.items() if k != "name"},
                }
                for p in products
            ],
            "rejected_products": [],
            "tier_distribution": {},
        }
    
    # Build products JSON for prompt (compact)
    compact_products = []
    for p in products:
        compact_products.append({
            "name": p.get("name", ""),
            "tier": p.get("tier", ""),
            "release_year": p.get("release_year"),
            "release_month": p.get("release_month"),
            "updated_version_name": p.get("updated_version_name"),
            "popularity_score": p.get("popularity_score", 5),
            "why_notable": p.get("why_notable", ""),
        })
    
    prompt = SELECTION_PROMPT_TEMPLATE.format(
        current_year=current_year,
        current_year_minus_1=current_year - 1,
        target_count=target_count,
        products_json=json.dumps(compact_products, indent=2),
    )
    
    try:
        from backend.llm.router import LLMRouter
        router = LLMRouter(task_type="competitor_analysis")
        response = await router.generate_text(
            prompt=prompt,
            system_prompt="You are a product selection expert. Return ONLY valid JSON.",
        )
        
        result = _parse_llm_response(response)
        
        selected = result.get("selected_products", [])
        rejected = result.get("rejected_products", [])
        
        # Merge full product data into selected products
        products_by_name = {p["name"].lower(): p for p in products}
        enriched_selected = []
        for sel in selected:
            sel_name_lower = sel.get("name", "").lower()
            full_data = products_by_name.get(sel_name_lower, {})
            enriched_selected.append({
                **full_data,
                "name": sel.get("name", full_data.get("name", "")),
                "selection_score": sel.get("selection_score", 5),
                "selection_reasoning": sel.get("reasoning", ""),
                "decision": sel.get("decision", "keep"),
            })
        
        # Sort by selection_score (highest first)
        enriched_selected.sort(
            key=lambda x: x.get("selection_score", 0), 
            reverse=True
        )
        
        return {
            "selected_products": enriched_selected[:target_count],
            "rejected_products": rejected,
            "tier_distribution": result.get("tier_distribution", {}),
        }
        
    except Exception as e:
        logger.warning(f"intelligent_product_selection failed: {e}. Using fallback.")
        # Fallback: just take top N by popularity
        sorted_products = sorted(
            products, 
            key=lambda x: x.get("popularity_score", 0), 
            reverse=True
        )
        return {
            "selected_products": sorted_products[:target_count],
            "rejected_products": [],
            "tier_distribution": {},
        }


def balance_tiers(
    selected: List[Dict],
    pool: List[Dict],
    target_count: int,
) -> List[Dict]:
    """Stage 1c: Ensure mix of premium/mid_range/budget tiers.
    
    If selection lacks a tier, add top product of that tier from pool.
    """
    if not selected:
        return selected
    
    # Count tiers in selection
    tier_counts = {"premium": 0, "mid_range": 0, "budget": 0}
    for p in selected:
        tier = p.get("tier", "mid_range")
        if tier in tier_counts:
            tier_counts[tier] += 1
    
    # Find missing tiers
    missing_tiers = [t for t, count in tier_counts.items() if count == 0]
    
    if not missing_tiers or not pool:
        return selected
    
    result = list(selected)
    used_names = {p["name"].lower() for p in result}
    
    # For each missing tier, add best available from pool
    for missing_tier in missing_tiers:
        candidates = [
            p for p in pool
            if p.get("tier") == missing_tier
            and p["name"].lower() not in used_names
        ]
        if candidates:
            # Sort by popularity, pick best
            best = sorted(
                candidates,
                key=lambda x: x.get("popularity_score", 0),
                reverse=True
            )[0]
            
            # Replace lowest-scored product of over-represented tier
            over_represented = max(tier_counts, key=tier_counts.get)
            replace_candidates = [
                p for p in result if p.get("tier") == over_represented
            ]
            if replace_candidates and len(result) >= target_count:
                # Replace the lowest popularity one
                worst = sorted(
                    replace_candidates,
                    key=lambda x: x.get("popularity_score", 0)
                )[0]
                result.remove(worst)
            
            result.append(best)
            used_names.add(best["name"].lower())
            tier_counts[missing_tier] += 1
    
    return result[:target_count]


def _extract_brand(name: str) -> str:
    """Extract brand from product name (best effort)."""
    common_brands = [
        "Apple", "Samsung", "Google", "Microsoft", "Sony", "LG", "Dell", "HP",
        "Lenovo", "ASUS", "Acer", "MSI", "Gigabyte", "Canon", "Nikon", "Bosch",
        "DeWalt", "Milwaukee", "Makita", "John Deere", "Kubota", "Philips",
        "Dyson", "Garmin", "Fitbit", "Oculus", "Meta", "Tesla", "BMW", "Toyota",
    ]
    
    for brand in common_brands:
        if brand.lower() in name.lower():
            return brand
    
    return name.split()[0] if name else ""


def _normalize_tier(tier: str) -> str:
    """Normalize tier to standard values."""
    tier_lower = (tier or "").lower()
    
    if any(kw in tier_lower for kw in ["premium", "flagship", "luxury", "high-end", "high end", "top"]):
        return "premium"
    if any(kw in tier_lower for kw in ["budget", "entry", "cheap", "affordable", "economy"]):
        return "budget"
    return "mid_range"


def _safe_int(value: Any, min_val: int, max_val: int) -> int:
    """Safely convert to int within range."""
    try:
        v = int(value)
        return max(min_val, min(max_val, v))
    except (ValueError, TypeError):
        return min_val


def _safe_list(value: Any, max_items: int = 5) -> List[str]:
    """Safely convert to list of strings."""
    if not isinstance(value, list):
        return []
    
    result = []
    for item in value[:max_items]:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return result


def get_selected_product_names(state: Dict[str, Any]) -> List[str]:
    """Helper to get just product names for downstream use."""
    products = state.get("selected_products", [])
    return [p["name"] for p in products if isinstance(p, dict) and p.get("name")]


def format_products_summary(products: List[Dict]) -> str:
    """Format products for display."""
    if not products:
        return "No products selected."
    
    lines = [f"## 🛒 {len(products)} Products Selected\n"]
    
    for i, p in enumerate(products, 1):
        tier_emoji = {"premium": "💎", "mid_range": "⭐", "budget": "💰"}.get(p["tier"], "•")
        popularity = p.get("popularity_score", 0)
        lines.append(f"{i}. {tier_emoji} **{p['name']}** ({p['tier']}) — Popularity: {popularity}/10")
        if p.get("why_notable"):
            lines.append(f"   _{p['why_notable']}_")
        lines.append("")
    
    return "\n".join(lines)
