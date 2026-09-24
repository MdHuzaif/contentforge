"""TDD tests: Level 1 - Smart Product Selection with 2-stage approach."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch


def test_extraction_prompt_no_rigid_freshness_rules():
    """Stage 1a must NOT have rigid rejection rules."""
    from core.selectors.product_selector import EXTRACTION_PROMPT_TEMPLATE
    
    prompt_lower = EXTRACTION_PROMPT_TEMPLATE.lower()
    
    # Old rigid rules must be GONE
    assert "reject products from 2024" not in prompt_lower, \
        "Old Rule 10 (reject 2024) must be removed"
    
    # New instruction must exist
    assert "do not filter" in prompt_lower or "extract all" in prompt_lower, \
        "Must instruct to extract ALL products without filtering"
    
    assert "release_month" in prompt_lower, \
        "Must ask for release_month"
    
    assert "updated_version" in prompt_lower, \
        "Must ask for updated_version detection"


def test_extraction_prompt_keeps_tier_classification():
    """Stage 1a must keep tier classification for At-a-Glance table."""
    from core.selectors.product_selector import EXTRACTION_PROMPT_TEMPLATE
    
    prompt_lower = EXTRACTION_PROMPT_TEMPLATE.lower()
    assert "premium" in prompt_lower
    assert "mid_range" in prompt_lower or "mid-range" in prompt_lower
    assert "budget" in prompt_lower


def test_validate_enrich_handles_new_fields():
    """_validate_and_enrich must preserve new fields."""
    from core.selectors.product_selector import _validate_and_enrich
    
    raw_products = [
        {
            "name": "MacBook Air M4",
            "brand": "Apple",
            "tier": "premium",
            "release_year": 2025,
            "release_month": "March",
            "updated_version_name": None,
            "why_notable": "Latest ultrabook",
            "popularity_score": 9,
            "selling_points": ["M4 chip"],
            "pros": ["Fast"],
            "cons": ["Expensive"],
        },
        {
            "name": "Dell XPS 15 9530",
            "brand": "Dell",
            "tier": "premium",
            "release_year": 2024,
            "release_month": "May",
            "updated_version_name": "Dell XPS 16 (2026)",
            "why_notable": "Reliable workhorse",
            "popularity_score": 8,
            "selling_points": ["OLED display"],
            "pros": ["Great screen"],
            "cons": ["Pricey"],
        },
    ]
    
    enriched = _validate_and_enrich(raw_products, target_count=10)
    
    macbook = next(p for p in enriched if "MacBook" in p["name"])
    assert macbook["release_year"] == 2025
    assert macbook["release_month"] == "March"
    assert macbook.get("updated_version_name") is None
    
    dell = next(p for p in enriched if "Dell" in p["name"])
    assert dell["release_year"] == 2024
    assert dell["updated_version_name"] == "Dell XPS 16 (2026)"


@pytest.mark.asyncio
async def test_intelligent_selection_basic():
    """intelligent_product_selection returns sorted products with reasoning."""
    from core.selectors.product_selector import intelligent_product_selection
    
    products = [
        {
            "name": "MacBook Air M5",
            "tier": "premium",
            "release_year": 2026,
            "updated_version_name": None,
            "popularity_score": 9,
        },
        {
            "name": "MacBook Air M4",
            "tier": "premium",
            "release_year": 2025,
            "updated_version_name": "MacBook Air M5 (2026)",
            "popularity_score": 8,
        },
        {
            "name": "MacBook Air M2",
            "tier": "budget",
            "release_year": 2022,
            "updated_version_name": "MacBook Air M5 (2026)",
            "popularity_score": 6,
        },
    ]
    
    with patch('backend.llm.router.LLMRouter') as mock_llm:
        mock_instance = MagicMock()
        mock_instance.generate_text = AsyncMock(return_value='''{
            "selected_products": [
                {
                    "name": "MacBook Air M5",
                    "selection_score": 9.5,
                    "reasoning": "Latest model, best performance",
                    "decision": "keep"
                },
                {
                    "name": "MacBook Air M4",
                    "selection_score": 7.0,
                    "reasoning": "Good value but M5 available",
                    "decision": "keep"
                }
            ],
            "rejected_products": [
                {
                    "name": "MacBook Air M2",
                    "reasoning": "Too old, M5 available",
                    "rejection_reason": "outdated_with_update"
                }
            ]
        }''')
        mock_llm.return_value = mock_instance
        
        result = await intelligent_product_selection(
            products=products,
            target_count=2,
            current_year=2026
        )
        
        assert "selected_products" in result
        assert len(result["selected_products"]) == 2
        assert result["selected_products"][0]["name"] == "MacBook Air M5"
        assert "reasoning" in result["selected_products"][0] or "selection_reasoning" in result["selected_products"][0]


def test_balance_tiers_adds_missing_tier():
    """balance_tiers must ensure premium/mid/budget mix."""
    from core.selectors.product_selector import balance_tiers
    
    # All premium - needs mid/budget from pool
    selected = [
        {"name": "Product A", "tier": "premium", "popularity_score": 9},
        {"name": "Product B", "tier": "premium", "popularity_score": 8},
        {"name": "Product C", "tier": "premium", "popularity_score": 7},
    ]
    
    pool = [
        {"name": "Product D", "tier": "mid_range", "popularity_score": 8},
        {"name": "Product E", "tier": "budget", "popularity_score": 7},
    ]
    
    balanced = balance_tiers(selected, pool, target_count=5)
    
    tiers = [p["tier"] for p in balanced]
    assert "premium" in tiers
    assert "mid_range" in tiers
    assert "budget" in tiers


def test_balance_tiers_keeps_if_already_balanced():
    """balance_tiers keeps selection if already balanced."""
    from core.selectors.product_selector import balance_tiers
    
    selected = [
        {"name": "A", "tier": "premium", "popularity_score": 9},
        {"name": "B", "tier": "mid_range", "popularity_score": 8},
        {"name": "C", "tier": "budget", "popularity_score": 7},
    ]
    
    pool = []
    
    balanced = balance_tiers(selected, pool, target_count=3)
    assert len(balanced) == 3


def test_old_product_kept_if_no_update():
    """Products with no newer version should NOT be auto-rejected."""
    from core.selectors.product_selector import _validate_and_enrich
    
    # A 2023 product with NO updated version
    raw = [{
        "name": "ThinkPad X1 Carbon Gen 11",
        "brand": "Lenovo",
        "tier": "premium",
        "release_year": 2023,
        "release_month": "April",
        "updated_version_name": None,  # No newer version!
        "why_notable": "Business classic",
        "popularity_score": 8,
    }]
    
    enriched = _validate_and_enrich(raw, target_count=10)
    
    # Must NOT be auto-rejected (validation keeps it)
    assert len(enriched) == 1
    assert enriched[0]["release_year"] == 2023


def test_obsolete_functions_removed():
    """Old regex-based functions must be deleted."""
    import core.selectors.product_selector as ps
    
    assert not hasattr(ps, "verify_unknown_products_batch"), \
        "verify_unknown_products_batch must be deleted"
    
    assert not hasattr(ps, "parse_release_year"), \
        "parse_release_year must be deleted"
    
    assert not hasattr(ps, "is_product_outdated_by_age"), \
        "is_product_outdated_by_age must be deleted"
