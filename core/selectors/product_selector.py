"""Universal product selector: Uses LLM to extract authentic products 
from competitor analysis for ANY product category (laptops, watches, 
dental tech, farm equipment, cameras, etc.)."""
from __future__ import annotations
import re
import json
from typing import Dict, Any, List, Optional
from app.config import logger


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
   ✅ GOOD: "Dell XPS 15 9530", "Apple Watch Ultra 2", "John Deere 5075E Tractor"
   ❌ BAD: "laptop", "smartwatch", "a good tractor", "Dell" (brand only)

2. Include products from ALL price tiers if available:
   - Premium/Flagship (highest-end, most expensive)
   - Mid-range/Value (balanced performance and price)
   - Budget/Entry-level (affordable options)

3. For EACH product, extract:
   - Full product name (brand + model + variant if applicable)
   - Brand name (alone)
   - Tier category (premium / mid_range / budget)
   - Why this product is notable (1 sentence, based on competitor mentions)
   - Estimated popularity: How many competitors mentioned it (1-10)
   - Key selling points (3-5 bullet points from competitor reviews)
   - Pros (from competitor reviews)
   - Cons (from competitor reviews)

4. Be AUTHENTIC — only include products that competitors ACTUALLY mentioned 
   with specific details. Do NOT invent products.

5. Target: Extract {target_count} products (or fewer if competitors mention fewer)

=== OUTPUT FORMAT ===

Return ONLY valid JSON in this EXACT structure (no markdown, no explanation):

{{
  "products": [
    {{
      "name": "Full Brand Model Name",
      "brand": "Brand Name",
      "tier": "premium",
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
        logger.info("🔍 Stage 1: Trying competitor scraped content...")
        competitor_content = _build_competitor_content(competitor_data)
        structure_content = _build_structure_content(competitor_data)
        
        if competitor_content or structure_content:
            if len(competitor_content) > 15000:
                competitor_content = competitor_content[:15000] + "\n... (truncated)"
            if len(structure_content) > 5000:
                structure_content = structure_content[:5000] + "\n... (truncated)"
            
            # ENHANCED PROMPT: Ask for target_count, suggest alternatives if fewer found
            prompt = f"""You are an expert product analyst. Analyze competitor content for topic: "{topic}"

=== COMPETITOR CONTENT ===
{competitor_content}

=== STRUCTURE HEADINGS ===
{structure_content}

=== EXTRACTION RULES ===
1. Extract SPECIFIC products with brand + model from the content
2. Target: {target_count} products total
3. If content mentions fewer than {target_count}, ALSO suggest popular alternatives 
   in this category to reach {target_count}
4. Mark which products are FROM CONTENT vs SUGGESTED
5. Include mix of tiers: premium, mid_range, budget

Return ONLY valid JSON (no markdown, no explanation):
{{
  "products": [
    {{
      "name": "Brand Model Name",
      "brand": "Brand",
      "tier": "premium",
      "why_notable": "Reason",
      "popularity_score": 8,
      "selling_points": ["Point 1", "Point 2"],
      "pros": ["Pro 1"],
      "cons": ["Con 1"],
      "source_competitors": ["url"],
      "source_type": "from_content"
    }}
  ],
  "category_detected": "category",
  "total_products_found": 10,
  "extraction_confidence": 0.95,
  "extraction_notes": "Notes"
}}"""
            
            logger.info(f"🤖 Stage 1: Sending extraction request")
            router = LLMRouter(task_type="competitor_analysis")
            response = await router.generate_text(
                prompt=prompt,
                system_prompt="Return ONLY valid JSON, no other text.",
            )
            
            result = _parse_llm_response(response)
            products = _validate_and_enrich(result.get("products", []), target_count)
            
            if products:
                extraction_method = "competitor_content"
                logger.info(f"✅ Stage 1: Extracted {len(products)} products")
        
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


def _build_competitor_content(competitor_data: Dict[str, Any]) -> str:
    """Build combined text from competitor scraped content."""
    parts = []
    
    # Try scraped_articles first (clean raw content), then competitors
    competitors = competitor_data.get("scraped_articles", [])
    if not competitors:
        competitors = competitor_data.get("competitors", [])
    
    for i, comp in enumerate(competitors[:10], 1):
        title = comp.get("title", "Untitled")
        content = comp.get("content", "")[:3000]  # Limit per competitor
        url = comp.get("url", "")
        
        if content:
            parts.append(f"\n--- COMPETITOR {i}: {title} ---\nSource: {url}\n{content}")
    
    # Also check for raw content field
    if not parts:
        raw_content = competitor_data.get("combined_content", "")
        if raw_content:
            parts.append(raw_content[:15000])
    
    return "\n".join(parts)


def _build_structure_content(competitor_data: Dict[str, Any]) -> str:
    """Build content from competitor structure/headings."""
    parts = []
    
    structure = competitor_data.get("optimal_structure", [])
    if not structure:
        structure = competitor_data.get("extracted_headings", [])
    
    for section in structure[:30]:
        title = section.get("title", "")
        content = section.get("content", "")
        
        if title:
            parts.append(f"- {title}")
            if content:
                parts.append(f"  {content[:200]}")
    
    return "\n".join(parts)


def _parse_llm_response(response: str) -> Dict[str, Any]:
    """Parse JSON from LLM response with multiple fallbacks."""
    
    # Try 1: Direct JSON parse
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        pass
    
    # Try 2: Extract JSON block from markdown fences
    fence_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try 3: Find first { to last }
    brace_match = re.search(r'\{[\s\S]*\}', response)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # Try 4: Fix common JSON issues and retry
    cleaned = response.strip()
    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)  # Trailing commas
    cleaned = re.sub(r'(\w+):', r'"\1":', cleaned)     # Unquoted keys
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Could not parse LLM JSON response")
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
        
        # Normalize fields with defaults
        validated.append({
            "name": name,
            "brand": (p.get("brand") or _extract_brand(name)).strip(),
            "tier": _normalize_tier(p.get("tier", "mid_range")),
            "why_notable": p.get("why_notable", ""),
            "popularity_score": _safe_int(p.get("popularity_score", 1), 1, 10),
            "selling_points": _safe_list(p.get("selling_points", []), max_items=5),
            "pros": _safe_list(p.get("pros", []), max_items=5),
            "cons": _safe_list(p.get("cons", []), max_items=5),
            "source_competitors": _safe_list(p.get("source_competitors", []), max_items=5),
        })
        
        if len(validated) >= target_count * 2:
            break
    
    # Sort by popularity score (highest first)
    validated.sort(key=lambda x: x.get("popularity_score", 0), reverse=True)
    
    return validated[:target_count]


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
