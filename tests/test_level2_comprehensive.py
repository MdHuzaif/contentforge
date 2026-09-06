"""
Comprehensive Level 2 Test Suite
Tests product extraction reliability across multiple iterations and scenarios.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.selectors.product_selector import extract_products_universal


class TestReport:
    """Track test results across multiple iterations."""
    
    def __init__(self):
        self.results = []
        self.start_time = datetime.now()
    
    def add_result(self, test_name: str, products_found: int, target: int, 
                   method: str, success: bool, duration: float):
        self.results.append({
            "test_name": test_name,
            "products_found": products_found,
            "target": target,
            "method": method,
            "success": success,
            "duration": duration,
            "timestamp": datetime.now()
        })
    
    def generate_report(self) -> str:
        """Generate comprehensive test report."""
        report = []
        report.append("=" * 80)
        report.append("📊 COMPREHENSIVE LEVEL 2 TEST REPORT")
        report.append("=" * 80)
        report.append(f"\n🕐 Test Duration: {(datetime.now() - self.start_time).total_seconds():.2f} seconds")
        report.append(f"📝 Total Tests Run: {len(self.results)}")
        
        # Group by test type
        test_groups = {}
        for result in self.results:
            test_name = result["test_name"]
            if test_name not in test_groups:
                test_groups[test_name] = []
            test_groups[test_name].append(result)
        
        report.append("\n" + "=" * 80)
        report.append("📈 TEST RESULTS BY CATEGORY")
        report.append("=" * 80)
        
        overall_success = []
        
        for test_name, results in test_groups.items():
            report.append(f"\n🔬 {test_name}")
            report.append("-" * 80)
            
            products_counts = [r["products_found"] for r in results]
            success_flags = [r["success"] for r in results]
            durations = [r["duration"] for r in results]
            
            success_rate = sum(success_flags) / len(success_flags) * 100
            avg_products = statistics.mean(products_counts)
            min_products = min(products_counts)
            max_products = max(products_counts)
            avg_duration = statistics.mean(durations)
            
            overall_success.extend(success_flags)
            
            report.append(f"  Iterations: {len(results)}")
            report.append(f"  Success Rate: {success_rate:.1f}%")
            report.append(f"  Average Products: {avg_products:.1f}")
            report.append(f"  Min/Max Products: {min_products} / {max_products}")
            report.append(f"  Average Duration: {avg_duration:.2f}s")
            
            # Show each iteration
            for i, r in enumerate(results, 1):
                status = "✅" if r["success"] else "❌"
                report.append(f"    {status} Iteration {i}: {r['products_found']} products ({r['method']}) - {r['duration']:.2f}s")
        
        # Overall summary
        report.append("\n" + "=" * 80)
        report.append("🎯 OVERALL SUMMARY")
        report.append("=" * 80)
        
        total_tests = len(overall_success)
        total_success = sum(overall_success)
        overall_rate = total_success / total_tests * 100 if total_tests > 0 else 0
        
        report.append(f"\n  Total Tests: {total_tests}")
        report.append(f"  Successful: {total_success}")
        report.append(f"  Failed: {total_tests - total_success}")
        report.append(f"  Overall Success Rate: {overall_rate:.1f}%")
        
        if overall_rate >= 90:
            report.append("\n  ✅ EXCELLENT: System is highly reliable (90%+ success)")
        elif overall_rate >= 70:
            report.append("\n  ⚠️  GOOD: System is mostly reliable (70-89% success)")
        else:
            report.append("\n  ❌ NEEDS IMPROVEMENT: System reliability is low (<70% success)")
        
        report.append("\n" + "=" * 80)
        
        return "\n".join(report)


async def run_single_test(test_name: str, topic: str, competitor_data: dict, 
                         target_count: int = 10, min_products: int = 8) -> dict:
    """Run a single test iteration."""
    start = datetime.now()
    
    try:
        result = await extract_products_universal(
            topic=topic,
            competitor_data=competitor_data,
            target_count=target_count,
        )
        
        products = result.get("products", [])
        method = result.get("extraction_method", "unknown")
        duration = (datetime.now() - start).total_seconds()
        
        success = len(products) >= min_products
        
        return {
            "test_name": test_name,
            "products_found": len(products),
            "target": target_count,
            "method": method,
            "success": success,
            "duration": duration,
            "products": products
        }
        
    except Exception as e:
        duration = (datetime.now() - start).total_seconds()
        return {
            "test_name": test_name,
            "products_found": 0,
            "target": target_count,
            "method": "failed",
            "success": False,
            "duration": duration,
            "error": str(e)
        }


async def test_real_scraped_content(report: TestReport, iterations: int = 3):
    """Test with real scraped content format."""
    print("\n🧪 Testing: Real Scraped Content from State")
    print("-" * 80)
    
    competitor_data = {
        "competitor_count": 5,
        "scraped_articles": [
            {
                "url": "https://pcmag.com/best-laptops-2026",
                "title": "The Best Laptops for 2026",
                "content": """After extensive testing of over 50 laptops, we've identified the top performers 
                for 2026. The MacBook Pro 16 M3 Max remains the gold standard for creative professionals 
                and developers who need maximum performance. Its 96GB unified memory configuration handles 
                massive codebases and video editing with ease.
                
                The Dell XPS 15 9530 continues to be our top pick for Windows users. With its stunning 
                OLED display and excellent Linux compatibility, it's perfect for developers who prefer 
                open-source operating systems. The keyboard is comfortable for long coding sessions.
                
                For business professionals, the Lenovo ThinkPad X1 Carbon Gen 11 is unmatched. Its legendary 
                keyboard, MIL-SPEC durability testing, and 20-hour battery life make it ideal for road 
                warriors. The 14-inch display is sharp and bright.
                
                Budget-conscious buyers should consider the Acer Swift 3. At under $800, it offers 
                surprisingly good performance with an AMD Ryzen 7 processor and 16GB RAM. The build 
                quality exceeds expectations for the price point.
                
                The ASUS ProArt Studiobook 16 is designed for creative professionals who need color 
                accuracy. Its OLED display covers 100% DCI-P3 and comes with a dial for creative 
                applications. The NVIDIA RTX 4070 handles 3D rendering effortlessly.
                
                Gaming laptops have evolved significantly. The Razer Blade 16 offers desktop-class 
                performance in a portable form factor. The 240Hz QHD+ display is perfect for competitive 
                gaming, while the RTX 4080 GPU handles ray tracing at high settings.
                
                For students and casual users, the HP Pavilion 15 provides solid value. The Intel 
                Core i5 processor and 8GB RAM handle everyday tasks smoothly. Battery life reaches 
                10 hours with light usage.
                
                The Microsoft Surface Laptop 5 combines premium design with excellent productivity 
                features. The 3:2 aspect ratio display is perfect for reading code and documents. 
                The Alcantara keyboard deck feels luxurious.
                
                Chromebook enthusiasts will appreciate the Google Pixelbook Go. While limited to 
                ChromeOS, it offers exceptional build quality and a comfortable keyboard. The 12-hour 
                battery life is impressive.
                
                Finally, the Framework Laptop 16 stands out for its modularity and repairability. 
                Users can upgrade components themselves, reducing e-waste and extending the laptop's 
                lifespan significantly.""",
                "h2_titles": ["Best Overall", "Best for Windows", "Best Business", "Budget Pick"]
            },
            {
                "url": "https://techradar.com/best-programming-laptops",
                "title": "Best Programming Laptops 2026",
                "content": """Choosing the right programming laptop in 2026 requires balancing performance, 
                portability, and price. We've tested dozens of models to find the best options for 
                different use cases.
                
                The Apple MacBook Pro 14 M3 Pro hits the sweet spot for most developers. With its 
                efficient M3 Pro chip, 18GB unified memory, and 17-hour battery life, it handles 
                everything from web development to machine learning workloads. The Liquid Retina XDR 
                display is gorgeous.
                
                Windows developers should look at the Dell XPS 13 Plus. Its compact 13.4-inch form 
                factor doesn't sacrifice performance, thanks to the Intel Core i7-13700H processor. 
                The capacitive touch function row is innovative, though some find it takes getting 
                used to.
                
                The Lenovo Legion 5 Pro is a gaming laptop that excels at programming. The AMD 
                Ryzen 9 7945HX processor offers incredible multi-threaded performance for compiling 
                large codebases. The 16-inch QHD+ display with 165Hz refresh rate is excellent for 
                both work and play.
                
                For data scientists working with large datasets, the MSI Creator Z17 is exceptional. 
                With 64GB DDR5 RAM and Intel Core i9-13900H, it handles massive pandas DataFrames 
                and TensorFlow models without breaking a sweat. The NVIDIA RTX 4070 accelerates 
                GPU-based computations.
                
                The HP Spectre x360 16 offers versatility with its 2-in-1 design. The OLED touch 
                display is perfect for presentations and note-taking. Performance is solid with 
                the Intel Core i7-1360P processor.
                
                Budget developers should consider the Acer Aspire 5. While it won't win any 
                performance awards, the AMD Ryzen 5 7530U processor and 16GB RAM handle web 
                development and light coding tasks adequately. At $600, it's exceptional value.
                
                The ASUS ZenBook 14 OLED combines portability with a stunning display. Weighing 
                just 3.06 pounds, it's perfect for developers who travel frequently. The OLED 
                display is incredibly sharp and color-accurate.
                
                For those who prioritize keyboard quality, the ThinkPad X13 remains excellent. 
                While the display is smaller at 13.3 inches, the keyboard is legendary among 
                programmers. Build quality is rock-solid.
                
                The LG Gram 17 is unique in offering a 17-inch display in a lightweight package. 
                At just 2.98 pounds, it's lighter than many 15-inch laptops. The large screen is 
                excellent for multi-window coding sessions.
                
                Finally, the System76 Lemur Pro deserves mention for Linux enthusiasts. It ships 
                with Pop!_OS and offers excellent Linux compatibility out of the box. The open-source 
                firmware and repairability make it a favorite among the Linux community.""",
                "h2_titles": ["Sweet Spot Pick", "Compact Powerhouse", "Gaming Crossover"]
            }
        ],
        "optimal_structure": []
    }
    
    for i in range(iterations):
        print(f"  Iteration {i+1}/{iterations}...")
        result = await run_single_test(
            "Real Scraped Content",
            "best laptops for programming 2026",
            competitor_data,
            target_count=10,
            min_products=8
        )
        report.add_result(
            result["test_name"],
            result["products_found"],
            result["target"],
            result["method"],
            result["success"],
            result["duration"]
        )
        
        if result["success"]:
            print(f"    ✅ Found {result['products_found']} products")
        else:
            print(f"    ❌ Only found {result['products_found']} products")


async def test_structure_only(report: TestReport, iterations: int = 3):
    """Test with only structure headings (no scraped content)."""
    print("\n🧪 Testing: Structure Headings Only")
    print("-" * 80)
    
    competitor_data = {
        "competitor_count": 5,
        "scraped_articles": [],
        "optimal_structure": [
            {"title": "MacBook Pro 16 M3 Max: Best for Power Users", "content": ""},
            {"title": "Dell XPS 15 9530: Best Windows Laptop", "content": ""},
            {"title": "Lenovo ThinkPad X1 Carbon: Business Champion", "content": ""},
            {"title": "Acer Swift 3: Budget Excellence", "content": ""},
            {"title": "ASUS ProArt Studiobook 16: Creative Professional's Choice", "content": ""},
            {"title": "Razer Blade 16: Gaming Meets Productivity", "content": ""},
            {"title": "HP Pavilion 15: Student-Friendly Option", "content": ""},
            {"title": "Microsoft Surface Laptop 5: Premium Design", "content": ""},
            {"title": "Google Pixelbook Go: Chromebook Excellence", "content": ""},
            {"title": "Framework Laptop 16: Modular and Repairable", "content": ""},
        ]
    }
    
    for i in range(iterations):
        print(f"  Iteration {i+1}/{iterations}...")
        result = await run_single_test(
            "Structure Headings Only",
            "best laptops for programming 2026",
            competitor_data,
            target_count=10,
            min_products=6
        )
        report.add_result(
            result["test_name"],
            result["products_found"],
            result["target"],
            result["method"],
            result["success"],
            result["duration"]
        )
        
        if result["success"]:
            print(f"    ✅ Found {result['products_found']} products")
        else:
            print(f"    ❌ Only found {result['products_found']} products")


async def test_auto_generation(report: TestReport, iterations: int = 3):
    """Test LLM auto-generation (no competitor data)."""
    print("\n🧪 Testing: LLM Auto-Generation")
    print("-" * 80)
    
    competitor_data = {
        "competitor_count": 0,
        "scraped_articles": [],
        "optimal_structure": []
    }
    
    for i in range(iterations):
        print(f"  Iteration {i+1}/{iterations}...")
        result = await run_single_test(
            "LLM Auto-Generation",
            "best wireless earbuds 2026",
            competitor_data,
            target_count=10,
            min_products=7
        )
        report.add_result(
            result["test_name"],
            result["products_found"],
            result["target"],
            result["method"],
            result["success"],
            result["duration"]
        )
        
        if result["success"]:
            print(f"    ✅ Generated {result['products_found']} products")
        else:
            print(f"    ❌ Only generated {result['products_found']} products")


async def test_mixed_categories(report: TestReport):
    """Test different product categories."""
    print("\n🧪 Testing: Mixed Product Categories")
    print("-" * 80)
    
    test_cases = [
        {
            "topic": "best smartwatches 2026",
            "competitor_data": {
                "competitor_count": 3,
                "scraped_articles": [
                    {
                        "url": "https://example.com/smartwatches",
                        "title": "Best Smartwatches 2026",
                        "content": "The Apple Watch Ultra 2 leads with its titanium case and dual-frequency GPS. "
                                  "Samsung Galaxy Watch 6 Classic offers the best Android experience. "
                                  "Garmin Fenix 7 Pro excels for outdoor enthusiasts with 28-day battery life. "
                                  "Fitbit Sense 2 focuses on health tracking with ECG and stress management. "
                                  "Google Pixel Watch 2 integrates perfectly with Google services. "
                                  "Amazfit T-Rex Ultra offers rugged durability. "
                                  "Whoop 4.0 is a screenless fitness tracker. "
                                  "Withings ScanWatch 2 combines hybrid design with health metrics. "
                                  "COROS VERTIX 2 targets endurance athletes. "
                                  "Suunto Race offers great GPS tracking.",
                        "h2_titles": []
                    }
                ],
                "optimal_structure": []
            }
        },
        {
            "topic": "best gaming monitors 2026",
            "competitor_data": {
                "competitor_count": 3,
                "scraped_articles": [
                    {
                        "url": "https://example.com/monitors",
                        "title": "Best Gaming Monitors 2026",
                        "content": "The LG 27GR95QE OLED offers incredible response times and perfect blacks. "
                                  "Samsung Odyssey OLED G8 combines 4K resolution with OLED technology. "
                                  "ASUS ROG Swift PG32UCDM is the ultimate 4K gaming monitor with HDR. "
                                  "Gigabyte AORUS FO32U2 provides excellent value with QD-OLED panel. "
                                  "Dell Alienware AW3225QF delivers immersive curved gaming experience. "
                                  "BenQ Mobiuz EX321UX offers great console gaming features. "
                                  "Sony INZONE M9 targets PlayStation 5 owners. "
                                  "ViewSonic XG322U provides high refresh rate gaming. "
                                  "Philips Evnia 34M2C8600 combines Ambiglow with QD-OLED. "
                                  "MSI MEG 342C QD-OLED delivers vibrant colors.",
                        "h2_titles": []
                    }
                ],
                "optimal_structure": []
            }
        },
        {
            "topic": "best mechanical keyboards 2026",
            "competitor_data": {
                "competitor_count": 3,
                "scraped_articles": [
                    {
                        "url": "https://example.com/keyboards",
                        "title": "Best Mechanical Keyboards 2026",
                        "content": "The Keychron Q1 Pro offers premium build quality with wireless connectivity. "
                                  "Leopold FC750R remains the gold standard for typing feel and reliability. "
                                  "Ducky One 3 provides excellent value with hot-swappable switches. "
                                  "Wooting 60HE revolutionizes gaming with analog switches. "
                                  "Razer Huntsman V3 Pro combines optical switches with rapid trigger. "
                                  "NuPhy Air75 V2 offers low-profile mechanical excellence. "
                                  "Keychron Q2 Pro provides a compact 65% layout. "
                                  "GMMK Pro is highly customizable. "
                                  "Ducky One 3 SF is great for desk space saving. "
                                  "Akko MOD007B features magnetic switches.",
                        "h2_titles": []
                    }
                ],
                "optimal_structure": []
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"  Testing: {test_case['topic']}")
        result = await run_single_test(
            f"Mixed Categories",
            test_case["topic"],
            test_case["competitor_data"],
            target_count=10,
            min_products=8
        )
        report.add_result(
            result["test_name"],
            result["products_found"],
            result["target"],
            result["method"],
            result["success"],
            result["duration"]
        )
        
        if result["success"]:
            print(f"    ✅ Found {result['products_found']} products")
        else:
            print(f"    ❌ Only found {result['products_found']} products")


async def main():
    """Run comprehensive test suite."""
    print("=" * 80)
    print("🚀 COMPREHENSIVE LEVEL 2 PRODUCT EXTRACTION TEST SUITE")
    print("=" * 80)
    print("\nThis test suite verifies that the product extraction system can")
    print("consistently extract 10+ products across multiple scenarios.")
    print("\nTest Categories:")
    print("  1. Real Scraped Content (3 iterations)")
    print("  2. Structure Headings Only (3 iterations)")
    print("  3. LLM Auto-Generation (3 iterations)")
    print("  4. Mixed Product Categories (3 different topics)")
    print("\n" + "=" * 80)
    
    report = TestReport()
    
    # Run all test categories
    await test_real_scraped_content(report, iterations=3)
    await test_structure_only(report, iterations=3)
    await test_auto_generation(report, iterations=3)
    await test_mixed_categories(report)
    
    # Generate and print report
    print("\n")
    final_report = report.generate_report()
    print(final_report)
    
    # Save report to file
    report_file = Path(__file__).parent / "test_level2_report.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(final_report)
    
    print(f"\n💾 Report saved to: {report_file}")
    
    # Return success status
    success_count = sum(1 for r in report.results if r["success"])
    total_count = len(report.results)
    success_rate = success_count / total_count * 100 if total_count > 0 else 0
    
    return success_rate >= 70  # Consider 70%+ success as passing


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
