"""Level 5 verification: Dynamic button injection with intelligent placement."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_button_injection_after_conclusion():
    """Test that buttons are injected after conclusion/verdict sections."""
    from core.exporters.affiliate_buttons import inject_buttons_into_markdown
    
    print("=" * 80)
    print("🧪 LEVEL 5 TEST: Button Injection After Conclusion")
    print("=" * 80)
    
    # Test markdown with conclusion section
    test_md = """## MacBook Pro 16 (M5 Max)

Are your current builds stalling out?

### Key Specifications
- CPU: M5 Max 16-core
- RAM: 64GB unified

### Performance
In our testing, the M5 Max delivered exceptional performance.

### Verdict: Who Should Buy

The MacBook Pro 16 is ideal for AI engineers and full-stack developers 
who need uncompromising performance.

## Next Section
"""
    
    product_links = {
        "MacBook Pro 16 (M5 Max)": "https://amazon.com/dp/B0TEST1?tag=test"
    }
    
    result = inject_buttons_into_markdown(test_md, product_links)
    
    # Verify button is after Verdict section
    verdict_pos = result.find("### Verdict: Who Should Buy")
    button_pos = result.find("amazon-affiliate-btn")
    next_section_pos = result.find("## Next Section")
    
    print(f"   Verdict position: {verdict_pos}")
    print(f"   Button position: {button_pos}")
    print(f"   Next section position: {next_section_pos}")
    
    success = (
        verdict_pos != -1 and
        button_pos != -1 and
        button_pos > verdict_pos and
        button_pos < next_section_pos
    )
    
    if success:
        print("✅ Button correctly placed after Verdict section")
    else:
        print("❌ Button placement failed")
        print("\nResult preview:")
        print(result[verdict_pos:verdict_pos+500] if verdict_pos != -1 else result[:500])
    
    return success


def test_button_injection_fallback():
    """Test that buttons are injected at end when no conclusion found."""
    from core.exporters.affiliate_buttons import inject_buttons_into_markdown
    
    print("\n" + "=" * 80)
    print("🧪 LEVEL 5 TEST: Button Injection Fallback (No Conclusion)")
    print("=" * 80)
    
    # Test markdown WITHOUT conclusion section
    test_md = """## Dell XPS 16 (2026)

This is a powerful laptop for developers.

### Key Specifications
- CPU: Intel Core Ultra 9
- RAM: 64GB DDR5

### Performance
Excellent multi-core performance for heavy workloads.

## Next Product
"""
    
    product_links = {
        "Dell XPS 16 (2026)": "https://amazon.com/dp/B0TEST2?tag=test"
    }
    
    result = inject_buttons_into_markdown(test_md, product_links)
    
    # Verify button is at end of section
    button_pos = result.find("amazon-affiliate-btn")
    next_section_pos = result.find("## Next Product")
    
    print(f"   Button position: {button_pos}")
    print(f"   Next section position: {next_section_pos}")
    
    success = (
        button_pos != -1 and
        next_section_pos != -1 and
        button_pos < next_section_pos
    )
    
    if success:
        print("✅ Button correctly placed at end of section")
    else:
        print("❌ Button placement failed")
    
    return success


def test_no_injection_without_links():
    """Test that no buttons are injected when no links provided."""
    from core.exporters.affiliate_buttons import inject_buttons_into_markdown
    
    print("\n" + "=" * 80)
    print("🧪 LEVEL 5 TEST: No Injection Without Links")
    print("=" * 80)
    
    test_md = """## Product Section

Some content here.

### Verdict: Who Should Buy
Buy this product.
"""
    
    # Empty product links
    product_links = {}
    
    result = inject_buttons_into_markdown(test_md, product_links)
    
    # Verify no button injected
    has_button = "amazon-affiliate-btn" in result
    
    print(f"   Has button: {has_button}")
    
    success = not has_button
    
    if success:
        print("✅ No button injected (correct)")
    else:
        print("❌ Button was injected when it shouldn't be")
    
    return success


def test_table_enhancement():
    """Test that Buy column is added to At a Glance table."""
    from core.exporters.affiliate_buttons import inject_buttons_into_markdown
    
    print("\n" + "=" * 80)
    print("🧪 LEVEL 5 TEST: Table Enhancement")
    print("=" * 80)
    
    test_md = """## At a Glance: Quick Comparison

| Product | Tier | Best For | Rating |
|---------|------|----------|--------|
| MacBook Pro 16 | Premium | AI Devs | 9.5/10 |
| Dell XPS 16 | Premium | Windows | 9.0/10 |

## Detailed Reviews
"""
    
    product_links = {
        "MacBook Pro 16": "https://amazon.com/dp/B0TEST1?tag=test"
    }
    
    result = inject_buttons_into_markdown(test_md, product_links)
    
    # Verify Buy column added
    has_buy_header = "Buy" in result
    has_table_button = "amazon-btn-table" in result
    
    print(f"   Has Buy header: {has_buy_header}")
    print(f"   Has table button: {has_table_button}")
    
    success = has_buy_header and has_table_button
    
    if success:
        print("✅ Table correctly enhanced with Buy column")
    else:
        print("❌ Table enhancement failed")
        print("\nResult:")
        print(result[:800])
    
    return success


def test_best_deal_badge():
    """Test that top pick gets Best Deal badge."""
    from core.exporters.affiliate_buttons import inject_buttons_into_markdown
    
    print("\n" + "=" * 80)
    print("🧪 LEVEL 5 TEST: Best Deal Badge for Top Pick")
    print("=" * 80)
    
    test_md = """## MacBook Pro 16 (M5 Max)

Content here.

### Verdict: Who Should Buy
Buy this.

## ThinkPad X1 Carbon

Content here.

### Verdict: Who Should Buy
Buy this too.
"""
    
    product_links = {
        "MacBook Pro 16 (M5 Max)": "https://amazon.com/dp/B0TEST1?tag=test",
        "ThinkPad X1 Carbon": "https://amazon.com/dp/B0TEST2?tag=test"
    }
    
    result = inject_buttons_into_markdown(
        test_md, 
        product_links,
        top_pick_product="MacBook Pro 16 (M5 Max)"
    )
    
    # Verify Best Deal badge
    has_badge = "best-deal-badge" in result or "Best Deal" in result
    has_top_pick_button = "best-deal-btn" in result
    
    print(f"   Has Best Deal badge: {has_badge}")
    print(f"   Has top pick button style: {has_top_pick_button}")
    
    success = has_badge or has_top_pick_button
    
    if success:
        print("✅ Best Deal badge correctly applied")
    else:
        print("❌ Best Deal badge not applied")
    
    return success


def test_disclosure_footer():
    """Test that disclosure footer is added."""
    from core.exporters.affiliate_buttons import generate_disclosure_footer
    
    print("\n" + "=" * 80)
    print("🧪 LEVEL 5 TEST: Disclosure Footer")
    print("=" * 80)
    
    footer = generate_disclosure_footer()
    
    # Verify footer content
    has_disclosure = "affiliate-disclosure" in footer
    has_amazon = "Amazon" in footer
    has_associate = "Associate" in footer
    
    print(f"   Has disclosure class: {has_disclosure}")
    print(f"   Mentions Amazon: {has_amazon}")
    print(f"   Mentions Associate: {has_associate}")
    
    success = has_disclosure and has_amazon and has_associate
    
    if success:
        print("✅ Disclosure footer correctly formatted")
    else:
        print("❌ Disclosure footer incomplete")
    
    return success


def test_multiple_products():
    """Test injection with multiple products."""
    from core.exporters.affiliate_buttons import inject_buttons_into_markdown
    
    print("\n" + "=" * 80)
    print("🧪 LEVEL 5 TEST: Multiple Products Injection")
    print("=" * 80)
    
    test_md = """## MacBook Pro 16 (M5 Max)
Content 1.
### Verdict: Who Should Buy
Buy MacBook.

## Dell XPS 16 (2026)
Content 2.
### Verdict: Who Should Buy
Buy Dell.

## ThinkPad X1 Carbon
Content 3.
### Verdict: Who Should Buy
Buy ThinkPad.

## Buying Guide
"""
    
    product_links = {
        "MacBook Pro 16 (M5 Max)": "https://amazon.com/dp/B0TEST1?tag=test",
        "Dell XPS 16 (2026)": "https://amazon.com/dp/B0TEST2?tag=test",
        "ThinkPad X1 Carbon": "https://amazon.com/dp/B0TEST3?tag=test"
    }
    
    result = inject_buttons_into_markdown(test_md, product_links)
    
    # Count buttons
    button_count = result.count("amazon-affiliate-btn")
    
    print(f"   Buttons injected: {button_count}")
    print(f"   Expected: 3")
    
    success = button_count == 3
    
    if success:
        print("✅ All 3 products got buttons")
    else:
        print(f"❌ Expected 3 buttons, got {button_count}")
    
    return success


def test_case_insensitive_matching():
    """Test that product matching is case-insensitive."""
    from core.exporters.affiliate_buttons import inject_buttons_into_markdown
    
    print("\n" + "=" * 80)
    print("🧪 LEVEL 5 TEST: Case-Insensitive Matching")
    print("=" * 80)
    
    test_md = """## macbook pro 16 (m5 max)

Lowercase heading.

### verdict: who should buy
Buy this.
"""
    
    # Uppercase in links dict
    product_links = {
        "MacBook Pro 16 (M5 Max)": "https://amazon.com/dp/B0TEST1?tag=test"
    }
    
    result = inject_buttons_into_markdown(test_md, product_links)
    
    # Verify button injected
    has_button = "amazon-affiliate-btn" in result
    
    print(f"   Has button: {has_button}")
    
    success = has_button
    
    if success:
        print("✅ Case-insensitive matching works")
    else:
        print("❌ Case-insensitive matching failed")
    
    return success


if __name__ == "__main__":
    print("=" * 80)
    print("🚀 LEVEL 5 COMPREHENSIVE TEST SUITE")
    print("Dynamic Button Injection")
    print("=" * 80)
    
    tests = [
        ("Button After Conclusion", test_button_injection_after_conclusion),
        ("Button Fallback Placement", test_button_injection_fallback),
        ("No Injection Without Links", test_no_injection_without_links),
        ("Table Enhancement", test_table_enhancement),
        ("Best Deal Badge", test_best_deal_badge),
        ("Disclosure Footer", test_disclosure_footer),
        ("Multiple Products", test_multiple_products),
        ("Case-Insensitive Matching", test_case_insensitive_matching),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ Test '{name}' failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 LEVEL 5 TEST SUMMARY")
    print("=" * 80)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} | {name}")
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    print(f"\n{'=' * 80}")
    print(f"Total: {passed_count}/{total_count} tests passed")
    print(f"{'=' * 80}")
    
    if passed_count == total_count:
        print("\n🎉 LEVEL 5 COMPLETE: All button injection tests passed!")
        print("\nKey achievements:")
        print("  ✓ Buttons intelligently placed after conclusion/verdict")
        print("  ✓ Fallback to end of section when no conclusion")
        print("  ✓ No injection without user-provided links")
        print("  ✓ Table Buy column added when links exist")
        print("  ✓ Best Deal badge for top pick")
        print("  ✓ Disclosure footer properly formatted")
        print("  ✓ Multiple products handled correctly")
        print("  ✓ Case-insensitive matching works")
    else:
        print(f"\n⚠️  LEVEL 5 PARTIAL: {total_count - passed_count} tests failed")
    
    sys.exit(0 if passed_count == total_count else 1)
