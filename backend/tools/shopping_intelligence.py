"""Dynamic shopping intelligence via competitor analysis + LLM classification.
No hardcoded product lists — learns from real competitor content."""
from __future__ import annotations
import re
from typing import List, Dict, Optional
import json

from app.config import logger
from backend.tools.serp_scraper import get_top_results
from backend.llm.router import LLMRouter

# Price regex for extraction
PRICE_RE = re.compile(r"\$\s?(\d{1,4}(?:\.\d{2})?)")

# Retailers to filter out
RETAILERS = {
    "amazon", "ebay", "walmart", "best buy", "bestbuy", "newegg",
    "target", "costco", "b&h", "bhphotovideo", "micro center",
}

# Known brands and their product lines for product detection
KNOWN_BRANDS = {
    "apple": ["macbook air", "macbook pro", "macbook", "ipad", "iphone", "watch", "airpods"],
    "asus": ["vivobook", "zenbook", "rog", "tuf"],
    "dell": ["xps", "inspiron", "latitude", "alienware"],
    "lenovo": ["thinkpad", "ideapad", "legion", "yoga"],
    "hp": ["spectre", "envy", "pavilion", "elitebook", "omen"],
    "microsoft": ["surface pro", "surface laptop", "surface"],
    "acer": ["aspire", "predator", "swift", "nitro"],
    "msi": ["stealth", "raider", "katana", "vector"],
    "samsung": ["galaxy", "odyssey", "tab"],
    "sony": ["wh-1000xm4", "wh-1000xm5", "wf-1000xm5", "bravia", "playstation"],
}

# Tier keywords for context extraction
TIER_KEYWORDS = {
    "premium": ["premium", "high-end", "flagship", "top tier", "luxury", "expensive", "best of the best", "pro"],
    "mid-range": ["mid-range", "midrange", "mid tier", "balanced", "mainstream", "sweet spot"],
    "budget": ["budget", "cheap", "affordable", "entry-level", "value", "under $500", "under $1000"],
}

# Extended sentiment lists (keep these — they're timeless)
PRAISE_WORDS = [
    "battery life", "battery", "fast", "reliable", "sturdy", "value", "smooth",
    "quiet", "cool", "bright", "great", "excellent", "solid", "durable",
    "responsive", "lightweight", "portable", "premium", "well built",
    "snappy", "crisp display", "good keyboard", "comfortable", "silent",
    "powerful", "gaming performance", "multitasking", "boot speed", "clear audio",
    "noise cancellation", "accurate colors", "sharp image", "ergonomic",
    "easy to install", "great vrm", "good thermals", "stable bios",
]
COMPLAINT_WORDS = [
    "overheats", "overheating", "heating", "hot", "loud", "fan noise", "noisy fan",
    "broke", "dead", "driver issue", "coil whine", "cheap", "slow", "fails", "bug",
    "flimsy", "heavy", "bulky", "disappointing", "screen bleed", "dim screen",
    "weak speakers", "trackpad issue", "bloatware", "short battery",
    "throttles", "laggy", "crashing", "bluescreen", "drops signal", "weak wifi",
    "muddy sound", "tinny speakers", "uncomfortable", "tight fit",
    "bad vrm", "bios issues", "no wifi", "limited ports", "no usb-c",
    "pricey", "overpriced", "not worth", "avoid", "regret",
]

# Topic-to-category detection (keep this — categories are stable)
TOPIC_CATEGORIES = {
    "laptop": "laptop", "notebook": "laptop", "ultrabook": "laptop",
    "motherboard": "motherboard", "mobo": "motherboard",
    "cpu": "cpu", "processor": "cpu", "ryzen": "cpu", "intel core": "cpu",
    "gpu": "gpu", "graphics card": "gpu", "rtx": "gpu", "radeon": "gpu",
    "smartwatch": "smartwatch", "watch": "smartwatch",
    "headphone": "headphone", "headset": "headphone", "earbuds": "headphone",
    "keyboard": "keyboard", "mouse": "mouse",
    "monitor": "monitor", "display": "monitor",
    "ssd": "ssd", "nvme": "ssd", "ram": "ram",
    "power supply": "power supply", "psu": "power supply",
    "cooler": "cooler", "aio": "cooler", "case": "case",
    "phone": "phone", "smartphone": "phone", "iphone": "phone",
    "camera": "camera", "dslr": "camera", "mirrorless": "camera",
    "tablet": "tablet", "ipad": "tablet",
    "printer": "printer", "speaker": "speaker", "soundbar": "speaker",
    "router": "router", "wifi": "router",
}


def _detect_product_category(topic: str) -> str:
    """Detect product category from topic."""
    topic_lower = topic.lower()
    for keyword, category in TOPIC_CATEGORIES.items():
        if keyword in topic_lower:
            return category
    return "general tech"


def _extract_prices(text: str) -> List[int]:
    """Extract all dollar amounts from text."""
    prices = PRICE_RE.findall(text)
    return [int(p.replace("$","").replace(",","").split(".")[0]) for p in prices if p]


def _extract_tier_context(text: str) -> Dict[str, int]:
    """Count tier keyword mentions in text."""
    text_lower = text.lower()
    counts = {}
    for tier, keywords in TIER_KEYWORDS.items():
        count = sum(text_lower.count(kw) for kw in keywords)
        counts[tier] = count
    return counts


async def _classify_tier_with_llm(
    topic: str,
    competitor_texts: List[str],
    category: str
) -> str:
    """Use LLM to dynamically classify the product tier based on competitor context."""
    # Extract relevant context
    all_text = " ".join(competitor_texts[:3])  # Use top 3 competitors
    prices = _extract_prices(all_text)
    tier_context = _extract_tier_context(all_text)
    
    # Build classification prompt
    prompt = f"""Analyze this tech product topic and classify its price tier based on competitor content.

TOPIC: {topic}
CATEGORY: {category}

COMPETITOR CONTEXT (excerpt):
{all_text[:1500]}

PRICE MENTIONS FOUND: {prices if prices else "None detected"}

TIER KEYWORD COUNTS:
- Premium/High-end mentions: {tier_context.get('premium', 0)}
- Mid-range mentions: {tier_context.get('mid-range', 0)}
- Budget mentions: {tier_context.get('budget', 0)}

Based on this context, classify the product tier. Consider:
1. If topic mentions specific high-end models (latest gen, flagship), lean premium
2. If competitors use "budget", "affordable", "under $X" language, lean budget
3. If price mentions are mostly $200-600, lean budget
4. If price mentions are mostly $600-1200, lean mid-range
5. If price mentions are mostly $1200+, lean premium

Respond with ONLY ONE of these exact strings:
- "budget-friendly tier"
- "mid-range tier"
- "premium/high-end tier"
- "mid-to-premium tier"

Tier:"""

    try:
        router = LLMRouter()
        response = await router.generate_text(
            prompt,
            system_prompt="You are a product tier classification expert. Respond with only the tier label.",
            task_type="competitor_analysis"
        )
        
        # Extract tier from response
        response_lower = response.lower().strip()
        if "premium" in response_lower or "high-end" in response_lower:
            return "premium/high-end tier"
        elif "mid-to-premium" in response_lower:
            return "mid-to-premium tier"
        elif "mid-range" in response_lower or "midrange" in response_lower:
            return "mid-range tier"
        elif "budget" in response_lower or "friendly" in response_lower:
            return "budget-friendly tier"
        
        logger.warning("LLM tier classification unclear: %s", response)
        return ""
        
    except Exception as e:
        logger.warning("LLM tier classification failed: %s", e)
        return ""


def _fallback_tier_detection(topic: str, text: str) -> str:
    """Fallback: simple keyword + price-based detection if LLM fails."""
    topic_lower = topic.lower()
    
    # Check explicit budget words in topic
    if any(w in topic_lower for w in ["under $500", "under 500", "budget", "cheap", "affordable", "entry-level"]):
        return "budget-friendly tier"
    if any(w in topic_lower for w in ["under $1000", "under 1000", "under $1k"]):
        return "mid-range tier"
    if any(w in topic_lower for w in ["premium", "high-end", "flagship", "expensive", "pro"]):
        return "premium tier"
    
    # Fallback to price analysis (filter out accessories < $50)
    prices = _extract_prices(text)
    prices = [p for p in prices if p >= 50]
    
    if prices:
        avg = sum(prices) / len(prices)
        if avg < 600:
            return "budget-friendly tier"
        if avg < 1200:
            return "mid-range tier"
        return "premium tier"
    
    return ""


async def _detect_budget_tier(topic: str, competitor_texts: List[str]) -> str:
    """Dynamic tier detection: LLM first, then fallback."""
    category = _detect_product_category(topic)
    
    # Try LLM classification first
    tier = await _classify_tier_with_llm(topic, competitor_texts, category)
    
    if tier:
        logger.info("LLM classified tier: %s", tier)
        return tier
    
    # Fallback to keyword/price detection
    combined_text = " ".join(competitor_texts)
    tier = _fallback_tier_detection(topic, combined_text)
    
    if tier:
        logger.info("Fallback tier detection: %s", tier)
    
    return tier


def _extract_product_mentions(text: str) -> List[str]:
    """Extract product/brand mentions (simple pattern for now)."""
    # This is a simplified version — could be enhanced with brand dictionary
    # For now, just return empty list since we're focusing on tier classification
    return []


async def gather_shopping_signals(topic: str, max_per_query: int = 4) -> str:
    """Gather shopping signals with dynamic LLM-based tier classification."""
    category = _detect_product_category(topic)
    
    # Fetch competitor content (reuse existing infrastructure)
    queries = [
        f"site:reddit.com {topic}",
        f"site:amazon.com {topic}",
        f"{topic} review pros and cons",
        f"{topic} worth it problems",
    ]
    
    snippets: List[str] = []
    for q in queries:
        try:
            results = await get_top_results(q, max_results=max_per_query)
            for r in results:
                snip = (r.get("snippet") or r.get("description") or "").strip()
                if snip:
                    snippets.append(snip)
        except Exception as e:
            logger.warning("Shopping query failed (%s): %s", q, e)
    
    if not snippets:
        logger.warning("No shopping snippets retrieved for topic '%s'", topic)
        return ""
    
    # Dynamic tier classification (LLM + fallback)
    tier = await _detect_budget_tier(topic, snippets)
    
    # Extract sentiment
    text = " ".join(snippets)
    praise = [w for w in PRAISE_WORDS if w in text.lower()][:6]
    complaints = [w for w in COMPLAINT_WORDS if w in text.lower()][:6]
    
    logger.info(
        "Shopping signals [%s]: %d snippets, tier=%s, %d praise, %d complaints",
        category, len(snippets), tier or "(unknown)", len(praise), len(complaints),
    )
    
    # Build output
    lines = [f"## REAL-WORLD SHOPPING & USER SIGNALS (live SERP data, category: {category})"]
    if tier:
        lines.append(f"- Target price tier: {tier} (do NOT mention specific dollar prices)")
    if praise:
        lines.append(f"- What real users praise: {', '.join(praise)}")
    else:
        lines.append("- (No strong praise signals detected)")
    if complaints:
        lines.append(f"- Common user complaints: {', '.join(complaints)}")
    else:
        lines.append("- (No strong complaint signals detected)")
    lines.append(
        "IMPORTANT: DO NOT write specific dollar amounts (e.g. 850, 999) anywhere in the article — prices "
        "change frequently and outdated numbers hurt SEO. Use relative language: "
        "'budget-friendly', 'affordable', 'premium-tier', 'great value', 'entry-level'."
    )
    return "\n".join(lines)
