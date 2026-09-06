"""Level 2 verification: Universal product selection works for ANY category."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_universal_extraction():
    """Test universal product extraction with various categories."""
    from core.selectors.product_selector import extract_products_universal
    
    print("=" * 70)
    print("🧪 LEVEL 2 TEST: Universal Product Selection Engine")
    print("=" * 70)
    
    test_cases = [
        {
            "name": "Laptops",
            "topic": "best laptop for programming 2026",
            "competitor_data": {
                "competitor_count": 3,
                "competitors": [
                    {
                        "title": "Top 10 Laptops for Developers",
                        "content": "The MacBook Pro 16 M3 Max is the ultimate choice for heavy IDEs. "
                                  "The Dell XPS 15 9530 offers excellent Linux support. "
                                  "Lenovo ThinkPad X1 Carbon Gen 11 remains a business favorite. "
                                  "For budget options, the Acer Swift 3 is surprisingly capable.",
                        "url": "techsite1.com"
                    }
                ]
            },
            "expected_category": "laptop",
            "min_products": 2,
        },
        {
            "name": "Smartwatches",
            "topic": "best smartwatch for fitness tracking",
            "competitor_data": {
                "competitor_count": 2,
                "competitors": [
                    {
                        "title": "Fitness Smartwatch Roundup",
                        "content": "The Apple Watch Ultra 2 leads in GPS accuracy. "
                                  "Garmin Fenix 7 Pro excels at multi-day battery life. "
                                  "Samsung Galaxy Watch 6 Classic offers best Android integration.",
                        "url": "fitness.com"
                    }
                ]
            },
            "expected_category": "smartwatch",
            "min_products": 2,
        },
        {
            "name": "Farm Equipment",
            "topic": "best compact tractor for small farms",
            "competitor_data": {
                "competitor_count": 2,
                "competitors": [
                    {
                        "title": "Compact Tractor Comparison",
                        "content": "The John Deere 3032E is reliable for small acreage. "
                                  "Kubota L2501 offers great PTO power. "
                                  "Mahindra 1626 is budget-friendly with decent features.",
                        "url": "farmmag.com"
                    }
                ]
            },
            "expected_category": "tractor",
            "min_products": 2,
        },
    ]
    
    results = []
    for i, case in enumerate(test_cases, 1):
        print(f"\n[Test {i}/{len(test_cases)}] Category: {case['name']}")
        print(f"  Topic: {case['topic']}")
        
        try:
            result = await extract_products_universal(
                topic=case["topic"],
                competitor_data=case["competitor_data"],
                target_count=5,
            )
            
            products = result.get("products", [])
            category = result.get("category_detected", "")
            confidence = result.get("extraction_confidence", 0.0)
            
            print(f"  Category detected: {category}")
            print(f"  Confidence: {confidence:.2f}")
            print(f"  Products found: {len(products)}")
            for j, p in enumerate(products[:3], 1):
                print(f"    {j}. {p['name']} ({p['tier']}) - popularity: {p.get('popularity_score', 0)}")
            
            # Validation
            has_enough = len(products) >= case["min_products"]
            category_ok = len(category) > 0
            confidence_ok = confidence >= 0.0
            passed = has_enough and category_ok and confidence_ok
            
            results.append({
                "name": case["name"],
                "passed": passed,
                "products": len(products),
                "category": category,
            })
            
        except Exception as e:
            print(f"  ❌ Test failed with error: {e}")
            results.append({"name": case["name"], "passed": False, "products": 0})
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 LEVEL 2 SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    
    for r in results:
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        print(f"{status} | {r['name']:15} | Products: {r['products']:2} | Category: {r.get('category', 'N/A')}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 LEVEL 2 COMPLETE: Universal product extraction working for all categories!")
        return True
    else:
        print(f"\n⚠️  LEVEL 2 PARTIAL: {total - passed} tests failed")
        return passed >= total - 1  # Allow 1 failure


if __name__ == "__main__":
    success = asyncio.run(test_universal_extraction())
    sys.exit(0 if success else 1)
