"""Detect product-specific H3 sections in an assembled blog.
Code-based detection using KNOWN_BRANDS dictionary — NO LLM involved."""
from __future__ import annotations
import re
from typing import List, Dict

from app.config import logger
from backend.tools.shopping_intelligence import KNOWN_BRANDS, RETAILERS

# H3 headings that are GENERIC (not product-specific) — skip these
GENERIC_H3_KEYWORDS = [
    "introduction", "conclusion", "comparison", "overview", "summary",
    "buying guide", "faq", "how to", "why", "what is", "verdict",
    "final thoughts", "specification", "features", "specs", "what specs", "pros and cons",
    "methodology", "how we test", "quick snapshot", "tl;dr", "what to look",
    "when to buy", "who this is for", "our methodology", "our picks",
]


def _build_product_pattern() -> re.Pattern:
    """Build regex pattern from KNOWN_BRANDS to match product names."""
    terms = []
    for brand, products in KNOWN_BRANDS.items():
        terms.append(re.escape(brand))
        for p in products:
            terms.append(re.escape(f"{brand} {p}"))
            terms.append(re.escape(p))
    # Sort by length descending so longer matches win
    terms = sorted(set(terms), key=len, reverse=True)
    if not terms:
        return re.compile(r"\b(placeholder_never_match)\b", re.IGNORECASE)
    return re.compile(r"\b(" + "|".join(terms) + r")\b", re.IGNORECASE)


PRODUCT_PATTERN = _build_product_pattern()


def _extract_headings_with_positions(markdown: str) -> List[Dict]:
    """Extract all H2/H3 headings with their character positions."""
    headings = []
    for match in re.finditer(r'^(#{2,3})\s+(.+)$', markdown, re.MULTILINE):
        level = len(match.group(1))
        title = match.group(2).strip()
        headings.append({
            "level": level,
            "title": title,
            "start": match.start(),
            "end": match.end(),
        })
    return headings


def _is_generic_heading(title: str) -> bool:
    """Check if an H3 heading is generic (not a product name)."""
    title_lower = title.lower()
    title_clean = re.sub(r'^\d+[\.\)]\s*', '', title_lower).strip()
    return any(kw in title_clean for kw in GENERIC_H3_KEYWORDS)


def _extract_product_name(title: str) -> str:
    """Extract FULL product name including model number from an H3 heading.
    
    Examples:
    - "Best Overall: ASUS ROG Strix X870E-E Gaming WiFi" → "ASUS ROG Strix X870E-E Gaming WiFi"
    - "Best Value: MSI MAG X870E Tomahawk WiFi" → "MSI MAG X870E Tomahawk WiFi"
    - "1. MacBook Air M2" → "MacBook Air M2"
    """
    # Remove numbering prefix like "1.", "2." etc
    title_clean = re.sub(r'^\d+[\.\)]\s*', '', title)
    
    # Remove award labels like "Best Overall:", "Our Pick:", "Editor's Choice:" etc
    title_clean = re.sub(
        r'^(Best\s+[\w\s-]+|Our\s+[\w\s-]+|Top\s+[\w\s-]+|Editor\'?s?\s+[\w\s-]+|Recommended|Favorite|Budget\s+Pick|Premium\s+Pick)[:\-]\s*',
        '', title_clean, flags=re.IGNORECASE
    ).strip()
    
    # Try to find full product name with model numbers first
    # Match: Brand + Product Line + Model Number (e.g., "ASUS ROG Strix X870E-E")
    full_product_match = re.search(
        r'\b(' + 
        r'(?:ASUS|MSI|Gigabyte|ASRock|NZXT|EVGA|Dell|HP|Lenovo|Acer|Apple|Samsung|Razer|Microsoft|Sony|Bose|Sennheiser|Keychron|Logitech|Corsair|BenQ|LG|Canon|Nikon|Fujifilm)' +
        r'(?:\s+[\w\-]+){0,4}' +  # Up to 4 additional words for product line + model
        r')\b',
        title_clean,
        re.IGNORECASE
    )
    
    if full_product_match:
        result = full_product_match.group(1).strip()
        # Verify it's not a retailer
        if result.lower() not in RETAILERS:
            return result
    
    # Fallback to existing PRODUCT_PATTERN match
    match = PRODUCT_PATTERN.search(title_clean)
    if match:
        return match.group(1).strip()
    
    return ""


def detect_product_sections(blog_markdown: str) -> List[Dict]:
    """Detect all product-specific H3 sections in the blog.
    
    Returns list of dicts with: heading, product_name, content, start, end, word_count
    """
    if not blog_markdown or not blog_markdown.strip():
        return []
    
    headings = _extract_headings_with_positions(blog_markdown)
    h3_headings = [h for h in headings if h["level"] == 3]
    
    product_sections = []
    
    for heading in h3_headings:
        # Skip generic headings
        if _is_generic_heading(heading["title"]):
            continue
        
        # Extract product name
        product_name = _extract_product_name(heading["title"])
        if not product_name:
            continue
        
        # Skip retailers
        if product_name.lower() in RETAILERS:
            continue
        
        # Determine section content boundaries
        content_start = heading["end"]
        next_headings = [h for h in headings if h["start"] > content_start]
        if next_headings:
            content_end = min(h["start"] for h in next_headings)
        else:
            content_end = len(blog_markdown)
        
        section_content = blog_markdown[content_start:content_end].strip()
        
        product_sections.append({
            "heading": heading["title"],
            "product_name": product_name,
            "content": section_content,
            "start": heading["start"],
            "end": content_end,
            "word_count": len(section_content.split()),
        })
    
    # Deduplicate by full product_name (keep first occurrence)
    seen = set()
    unique_sections = []
    for section in product_sections:
        key = section["product_name"].lower().strip()
        # Skip if too short (probably just a brand name)
        if len(key) < 5:
            continue
        if key not in seen:
            seen.add(key)
            unique_sections.append(section)
    
    logger.info("Detected %d product sections in blog", len(unique_sections))
    return unique_sections


async def enhance_detection_with_llm(blog_markdown: str, detected_products: List[str]) -> List[str]:
    """Use LLM to find any products that code-based detection missed.
    
    This is OPTIONAL and user-controlled via UI button.
    """
    from backend.llm.router import LLMRouter
    
    prompt = f"""Analyze this blog post and extract ALL specific product names mentioned.

DETECTED PRODUCTS (already found by code):
{chr(10).join(f"- {p}" for p in detected_products) if detected_products else "(none detected yet)"}

BLOG CONTENT (first 3000 chars):
\"\"\"
{blog_markdown[:3000]}
\"\"\"

TASK: List any ADDITIONAL specific product names (brand + model) that appear in the blog but are NOT in the detected list above.

Rules:
- Only include specific products with brand AND model (e.g., "ASUS ROG Strix X870E-E", not just "motherboard")
- Do NOT include generic terms like "laptop", "CPU", "GPU"
- Do NOT repeat products already in the detected list
- Return ONLY a JSON array of product names, or empty array if none found

Output format (JSON array only):
["Product Name 1", "Product Name 2"]
"""

    try:
        router = LLMRouter()
        response = await router.generate_text(
            prompt=prompt,
            system_prompt="You are a product detection expert. Return only a JSON array of product names.",
            task_type="competitor_analysis"
        )
        
        # Parse JSON response
        import json
        import re
        
        # Extract JSON array from response
        json_match = re.search(r'\[.*?\]', response, re.DOTALL)
        if json_match:
            additional_products = json.loads(json_match.group(0))
            return [p for p in additional_products if isinstance(p, str) and len(p) > 3]
        
        return []
        
    except Exception as e:
        logger.warning(f"LLM enhancement failed: {e}")
        return []


def format_detection_report(sections: List[Dict]) -> str:
    """Format detected sections as a markdown report for UI display."""
    if not sections:
        return ("### 🔍 No Product Sections Detected\n\n"
                "This blog doesn't appear to have product-specific H3 sections. "
                "The refinement feature works best with product review/comparison blogs.")
    
    lines = [
        f"### 🔍 Detected {len(sections)} Product Sections\n",
        "| # | Product Name | H3 Heading | Words | Section Preview |",
        "|---|--------------|-----------|-------|-----------------|",
    ]
    for i, s in enumerate(sections, 1):
        preview = s['content'][:80].replace('\n', ' ').replace('|', '/').strip()
        lines.append(
            f"| {i} | **{s['product_name']}** | {s['heading']} | "
            f"{s['word_count']} | {preview}... |"
        )
    
    lines.append("\n✅ **All sections look good!** Use the dropdown below to inspect the "
                 "exact section that will be refined, then click Refine.")
    lines.append("\n💡 *Only the content under each H3 heading will be enhanced — "
                 "the H3 headings themselves stay unchanged.*")
    
    return "\n".join(lines)


def get_section_detail(section: Dict) -> str:
    """Format a single section's full content for the detail view."""
    if not section:
        return "*Select a product to see the exact section that will be refined.*"
    
    return "\n".join([
        f"### 📌 {section['heading']}",
        f"**Product:** `{section['product_name']}` | **Words:** {section['word_count']}",
        "",
        "---",
        "",
        "**📝 This is the exact section content that will be refined:**",
        "",
        section['content'],
        "",
        "---",
        "",
        "✨ *After refinement, real user shopping signals will be naturally woven "
        "into this section while keeping the same tone.*",
    ])
