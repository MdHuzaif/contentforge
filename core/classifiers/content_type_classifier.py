"""Content type classifier using LLM to determine article structure type."""
from __future__ import annotations
from typing import Dict, Any, Optional
from app.config import logger


CONTENT_TYPES = {
    "product_recommendation": "Product review/buying guide with multiple products",
    "informational": "Educational content explaining concepts",
    "how_to": "Step-by-step tutorial or guide",
    "comparison": "Side-by-side comparison of 2-3 items",
}


CLASSIFIER_PROMPT_TEMPLATE = """You are an expert content strategist. 
Analyze this topic and determine the BEST content type for SEO and user intent.

TOPIC: {topic}

KEYWORDS FOUND: {keywords}
COMPETITOR ANALYSIS: {competitor_summary}

CONTENT TYPES:
1. product_recommendation - Product reviews, "best X", buying guides with multiple products
2. informational - Educational content, concept explanations, "what is X", "how X works"
3. how_to - Step-by-step tutorials, installation guides, "how to install/do X"
4. comparison - Side-by-side comparisons of 2-3 specific items (e.g., "X vs Y")

DECISION CRITERIA:
- "best", "top", "review", "buying guide", "recommendation" in topic → product_recommendation
- "how to", "guide", "tutorial", "install", "setup" → how_to
- "vs", "versus", "compared", "difference between" → comparison
- "what is", "how does", "why", "understanding" → informational
- Multiple products discussed in competitors → product_recommendation

Return ONLY valid JSON in this EXACT format:
{{
    "content_type": "product_recommendation",
    "confidence": 0.95,
    "reasoning": "Topic contains 'best' + competitors show product review structure",
    "product_count_estimate": 10
}}

Do NOT include any other text, explanation, or markdown fences."""


async def classify_content_type(
    topic: str,
    keywords: Optional[list] = None,
    competitor_data: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Classify content type using LLM.
    
    Returns:
        {
            "content_type": str,
            "confidence": float,
            "reasoning": str,
            "product_count_estimate": int
        }
    """
    try:
        from backend.llm.router import LLMRouter
        
        # Build competitor summary
        comp_summary = "Not available"
        if competitor_data:
            comp_count = competitor_data.get("competitor_count", 0)
            structure = competitor_data.get("optimal_structure", [])
            comp_summary = f"{comp_count} competitors analyzed. Structure: {len(structure)} sections"
        
        # Build keywords summary
        kw_summary = "None"
        if keywords:
            kw_list = [k if isinstance(k, str) else k.get("keyword", "") for k in keywords[:5]]
            kw_summary = ", ".join(kw_list)
        
        prompt = CLASSIFIER_PROMPT_TEMPLATE.format(
            topic=topic,
            keywords=kw_summary,
            competitor_summary=comp_summary,
        )
        
        router = LLMRouter(task_type="competitor_analysis")
        response = await router.generate_text(
            prompt=prompt,
            system_prompt="You are a content strategist. Return ONLY valid JSON.",
        )
        
        # Parse JSON response
        import json
        import re
        
        # Extract JSON from response (handle markdown fences)
        json_match = re.search(r'\{[^{}]*"content_type"[^{}]*\}', response, re.DOTALL)
        if not json_match:
            # Try finding full JSON block
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response.strip()
        else:
            json_str = json_match.group(0)
        
        result = json.loads(json_str)
        
        # Validate result
        if result.get("content_type") not in CONTENT_TYPES:
            logger.warning(f"Invalid content type: {result.get('content_type')}, defaulting to product_recommendation")
            result["content_type"] = "product_recommendation"
        
        # Ensure confidence is valid float
        try:
            result["confidence"] = float(result.get("confidence", 0.8))
        except (ValueError, TypeError):
            result["confidence"] = 0.8
        
        # Ensure product_count_estimate is valid int
        try:
            result["product_count_estimate"] = int(result.get("product_count_estimate", 10))
        except (ValueError, TypeError):
            result["product_count_estimate"] = 10
        
        # Add reasoning if missing
        if "reasoning" not in result:
            result["reasoning"] = "Default reasoning"
        
        logger.info(f"🎯 Content Type: {result['content_type']} (confidence: {result['confidence']:.2f})")
        logger.info(f"   Reasoning: {result['reasoning']}")
        
        return result
        
    except Exception as e:
        logger.warning(f"Content type classification failed: {e}, defaulting to product_recommendation")
        return {
            "content_type": "product_recommendation",
            "confidence": 0.5,
            "reasoning": f"Classification failed ({e}), using default",
            "product_count_estimate": 10,
        }


def is_product_recommendation(state: Dict[str, Any]) -> bool:
    """Helper function to check if current state is product recommendation type."""
    return state.get("content_type") == "product_recommendation"
