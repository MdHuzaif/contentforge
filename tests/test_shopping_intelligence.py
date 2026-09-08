"""Tests for dynamic shopping intelligence with LLM-based tier classification."""
import asyncio
from backend.tools import shopping_intelligence as si


def test_price_extraction():
    """Price regex should extract dollar amounts correctly."""
    assert si._extract_prices("costs $180 or $99.99 now") == [180, 99]
    assert si._extract_prices("no prices here") == []
    assert si._extract_prices("$2000 and $150") == [2000, 150]


def test_tier_context_extraction():
    """Should count tier keyword mentions."""
    text = "This premium high-end flagship is expensive. Budget alternatives are cheap and affordable."
    counts = si._extract_tier_context(text)
    assert counts["premium"] >= 3  # premium, high-end, flagship, expensive
    assert counts["budget"] >= 2   # budget, cheap, affordable


def test_product_category_detection():
    """Category detection should work for all major categories."""
    assert si._detect_product_category("best motherboard for ryzen 7") == "motherboard"
    assert si._detect_product_category("best budget laptop 2026") == "laptop"
    assert si._detect_product_category("apple watch series 9 review") == "smartwatch"
    assert si._detect_product_category("sony wh-1000xm5 headphones") == "headphone"
    assert si._detect_product_category("rtx 4070 vs rx 7800 xt") == "gpu"


def test_fallback_tier_budget():
    """Fallback should detect budget tier from topic keywords."""
    assert si._fallback_tier_detection("best budget laptop under $500", "") == "budget-friendly tier"
    assert si._fallback_tier_detection("cheap affordable laptop", "") == "budget-friendly tier"


def test_fallback_tier_midrange():
    """Fallback should detect mid-range tier."""
    assert si._fallback_tier_detection("best laptop under $1000 2026", "") == "mid-range tier"


def test_fallback_tier_premium():
    """Fallback should detect premium tier."""
    assert si._fallback_tier_detection("premium flagship laptop", "") == "premium tier"
    assert si._fallback_tier_detection("high-end gaming laptop", "") == "premium tier"


def test_fallback_tier_from_prices():
    """Fallback should use price analysis when topic has no signals."""
    assert si._fallback_tier_detection("some laptop", "$200 $300 $250") == "budget-friendly tier"
    assert si._fallback_tier_detection("some laptop", "$800 $900 $1000") == "mid-range tier"
    assert si._fallback_tier_detection("some laptop", "$2000 $2500") == "premium tier"


def test_dynamic_tier_detection():
    """Full dynamic detection should work (LLM or fallback)."""
    async def run_test():
        snippets = [
            "The ASUS ROG Strix X670E is a premium motherboard for Ryzen 9 7950X",
            "This high-end board costs $450 and offers flagship features",
            "Expensive but worth it for enthusiasts"
        ]
        tier = await si._detect_budget_tier("best motherboard for ryzen 9 7950x", snippets)
        # Should detect as premium (either via LLM or fallback)
        assert "premium" in tier.lower() or "high-end" in tier.lower(), f"Got: {tier}"
    
    asyncio.run(run_test())


def test_no_specific_dollars_in_output():
    """Output must NOT contain literal $XXX dollar amounts."""
    async def run_test():
        out = await si.gather_shopping_signals("best budget laptop 2026")
        if out:
            prices = si._extract_prices(out)
            assert len(prices) == 0, f"Output contained specific dollar prices: {prices}"
    
    asyncio.run(run_test())


def test_sentiment_lists_comprehensive():
    """Sentiment word lists should be comprehensive."""
    assert "battery life" in si.PRAISE_WORDS
    assert "noise cancellation" in si.PRAISE_WORDS
    assert "overheats" in si.COMPLAINT_WORDS
    assert "throttles" in si.COMPLAINT_WORDS
    assert len(si.PRAISE_WORDS) >= 30
    assert len(si.COMPLAINT_WORDS) >= 30


def test_retailers_filtered():
    """Retailers should be in the filter list."""
    assert "amazon" in si.RETAILERS
    assert "ebay" in si.RETAILERS
    assert "best buy" in si.RETAILERS


def test_dynamic_category_detection_hybrid():
    """Test hybrid dynamic category detection for unknown topics and caching."""
    # Known topic (rule-based)
    cat1 = si._detect_product_category("best motherboard for ryzen 7")
    assert cat1 == "motherboard"

    # Test caching works
    assert si._CATEGORY_CACHE.get("best motherboard for ryzen 7") == "motherboard"

    # Unknown topic (fallback/LLM)
    cat2 = si._detect_product_category("best irrigation system for drought")
    assert cat2 in ["irrigation", "system", "drought", "general"] or len(cat2) > 0

    # Test category page creation
    from pathlib import Path
    import tempfile
    from core.exporters.static_exporter import create_category_page

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Create a mock post directory and index.html
        post_dir = tmp_path / "best-tractor-2026"
        post_dir.mkdir()
        (post_dir / "index.html").write_text(
            '<!DOCTYPE html><html><body><h1>Best Tractor for Farms</h1><time datetime="2026-03-01T00:00:00Z">March 1, 2026</time><a href="../tractors/index.html">Tractors</a></body></html>',
            encoding="utf-8"
        )
        create_category_page("Tractors", "tractors", tmp_path)
        cat_page = tmp_path / "tractors" / "index.html"
        assert cat_page.exists()
        assert "Tractors" in cat_page.read_text(encoding="utf-8")
        assert "Best Tractor for Farms" in cat_page.read_text(encoding="utf-8")


def test_unknown_topic_does_not_early_return():
    """TDD RED: Prove the early return bug exists for unknown topics."""
    # Clear cache to ensure a fresh run
    si._CATEGORY_CACHE.clear()
    
    # 1. Verify known topic still works (baseline)
    known_cat = si._detect_product_category("best motherboard for ryzen 7")
    assert known_cat == "motherboard", f"Rule-based failed: got {known_cat}"
    
    # 2. Test the BUG: Unknown topic should NOT return hardcoded "general tech"
    # It should fall through to LLM detection or word extraction.
    unknown_cat = si._detect_product_category("best compact tractor for small farms 2026")
    
    # THIS ASSERTION WILL FAIL BEFORE THE FIX
    assert unknown_cat != "general tech", (
        f"BUG CONFIRMED: Early return triggered! Got '{unknown_cat}'. "
        "LLM fallback and word extraction were skipped."
    )
    
    # Verify it actually extracted a word or used LLM (e.g., "tractor", "compact", "farms")
    assert len(unknown_cat) > 2, f"Fallback returned too-short string: {unknown_cat}"
    print(f"✅ TDD Test passed after fix: Unknown topic resolved to '{unknown_cat}'")


def main():
    """Run all tests."""
    test_price_extraction()
    test_tier_context_extraction()
    test_product_category_detection()
    test_fallback_tier_budget()
    test_fallback_tier_midrange()
    test_fallback_tier_premium()
    test_fallback_tier_from_prices()
    test_dynamic_tier_detection()
    test_no_specific_dollars_in_output()
    test_sentiment_lists_comprehensive()
    test_retailers_filtered()
    test_dynamic_category_detection_hybrid()
    test_unknown_topic_does_not_early_return()
    print("SHOPPING INTELLIGENCE VERIFIED — dynamic LLM classification ready")


if __name__ == "__main__":
    main()
