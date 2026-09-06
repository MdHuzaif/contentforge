"""Level 1 verification: Content type classification works correctly."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_classifier():
    """Test content type classifier with various topics."""
    from core.classifiers.content_type_classifier import classify_content_type
    
    test_cases = [
        {
            "topic": "best motherboard for ryzen 9 9800x3d",
            "expected": "product_recommendation",
        },
        {
            "topic": "how does 3d v-cache work in amd processors",
            "expected": "informational",
        },
        {
            "topic": "how to install motherboard in pc case",
            "expected": "how_to",
        },
        {
            "topic": "intel i9 14900k vs amd ryzen 9 7950x",
            "expected": "comparison",
        },
    ]
    
    print("=" * 70)
    print("🧪 LEVEL 1 TEST: Content Type Classifier")
    print("=" * 70)
    
    results = []
    for i, case in enumerate(test_cases, 1):
        print(f"\n[Test {i}/{len(test_cases)}]")
        print(f"Topic: {case['topic']}")
        print(f"Expected: {case['expected']}")
        
        result = await classify_content_type(
            topic=case["topic"],
            keywords=["related", "keywords"],
            competitor_data={"competitor_count": 5},
        )
        
        actual = result["content_type"]
        confidence = result["confidence"]
        match = "✅" if actual == case["expected"] else "❌"
        
        print(f"Actual: {actual} (confidence: {confidence:.2f}) {match}")
        print(f"Reasoning: {result['reasoning']}")
        
        results.append({
            "topic": case["topic"],
            "expected": case["expected"],
            "actual": actual,
            "confidence": confidence,
            "pass": actual == case["expected"],
        })
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    
    for r in results:
        status = "✅ PASS" if r["pass"] else "❌ FAIL"
        print(f"{status} | {r['topic'][:40]:40} | Expected: {r['expected']:20} | Got: {r['actual']:20}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 LEVEL 1 COMPLETE: All content type classifications working!")
        return True
    else:
        print(f"\n⚠️  LEVEL 1 PARTIAL: {total - passed} tests failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_classifier())
    sys.exit(0 if success else 1)
