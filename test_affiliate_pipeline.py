"""
End-to-End Affiliate System Verification Script
================================================
Tests the complete pipeline:
1. Keyword Research
2. Competitor Analysis
3. Sub-prompt Generation
4. Section Writing (with product detection)
5. Auto-add test affiliate links
6. Export to Uniscolian with buttons
7. Verify output

Usage: python test_affiliate_pipeline.py
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def run_full_pipeline():
    """Run complete blog generation pipeline with affiliate verification."""
    
    print("=" * 80)
    print("🧪 END-TO-END AFFILIATE SYSTEM VERIFICATION")
    print("=" * 80)
    print()
    
    # Import core modules
    from core.graph import (
        keyword_research_node,
        competitor_analysis_node,
        subprompt_generator_node,
        section_writer_node,
        blog_assembler_node,
    )
    from core.state import create_initial_state
    from core.exporters.static_exporter import export_post_to_uniscolian
    
    # Step 1: Initialize state
    print("📋 Step 1: Initializing state...")
    topic = "best motherboard for ryzen 9 9800x3d"
    state = create_initial_state(topic)
    print(f"✓ State initialized for topic: '{topic}'")
    print()
    
    # Step 2: Keyword Research
    print("🔍 Step 2: Running keyword research...")
    try:
        kw_result = await keyword_research_node(state)
        state.update(kw_result)
        keywords = kw_result.get("keyword_research", {}).get("keywords", [])
        print(f"✓ Generated {len(keywords)} keywords")
        for i, kw in enumerate(keywords[:3], 1):
            print(f"  {i}. {kw.get('keyword', 'N/A')}")
    except Exception as e:
        print(f"❌ Keyword research failed: {e}")
        return False
    print()
    
    # Step 3: Competitor Analysis
    print("🏆 Step 3: Running competitor analysis...")
    try:
        comp_result = await competitor_analysis_node(state)
        state.update(comp_result)
        comp_data = comp_result.get("competitor_analysis", {})
        print(f"✓ Analyzed {comp_data.get('competitor_count', 0)} competitors")
        print(f"✓ Optimal structure: {comp_data.get('optimal_sections', 0)} sections")
    except Exception as e:
        print(f"❌ Competitor analysis failed: {e}")
        return False
    print()
    
    # Step 4: Generate Sub-prompts
    print("📝 Step 4: Generating sub-prompts...")
    try:
        subprompt_result = await subprompt_generator_node(state)
        state.update(subprompt_result)
        sub_prompts = subprompt_result.get("sub_prompts", [])
        print(f"✓ Generated {len(sub_prompts)} sub-prompts")
        for i, sp in enumerate(sub_prompts[:3], 1):
            title = sp.get("title", "Untitled")
            words = sp.get("word_target", 0)
            print(f"  {i}. {title} ({words} words)")
    except Exception as e:
        print(f"❌ Sub-prompt generation failed: {e}")
        return False
    print()
    
    # Step 5: Generate Sections (with product detection)
    print("✍️  Step 5: Generating sections (product detection active)...")
    state["current_section_index"] = 0
    state["total_sections"] = len(sub_prompts)
    
    # Generate only first 5 sections for speed
    sections_to_generate = min(5, len(sub_prompts))
    
    for i in range(sections_to_generate):
        print(f"\n  📄 Section {i+1}/{sections_to_generate}...")
        try:
            section_result = await section_writer_node(state)
            state.update(section_result)
            
            # Check for product detection
            detected = state.get("detected_products", [])
            if detected and i == 0:
                print(f"    ✓ Detected {len(detected)} product(s)")
                for p in detected:
                    print(f"      - {p.get('name', 'Unknown')}")
            
            # Check current section
            sections = state.get("generated_sections", [])
            if sections and i < len(sections):
                current = sections[i]
                content = current.get("content", "")
                words = len(content.split())
                print(f"    ✓ Generated {words} words")
                if current.get("refined"):
                    print(f"    ✓ Auto-refined with shopping signals")
        except Exception as e:
            print(f"    ❌ Section {i+1} failed: {e}")
            continue
    
    print()
    
    # Step 6: Check detected products
    print("📦 Step 6: Checking detected products...")
    detected_products = state.get("detected_products", [])
    print(f"✓ Total detected products: {len(detected_products)}")
    
    if detected_products:
        for i, p in enumerate(detected_products, 1):
            print(f"  {i}. {p.get('name', 'Unknown')} (Section {p.get('section_index', '?')})")
    else:
        print("⚠️  No products detected - affiliate buttons will not be injected")
    print()
    
    # Step 7: Add test affiliate links
    print("🔗 Step 7: Adding test affiliate links...")
    test_links = {
        "ASUS ROG": "https://www.amazon.com/dp/B0CH3X1XYZ?tag=huzaif1612-20",
        "MSI MAG": "https://www.amazon.com/dp/B0CH3X2ABC?tag=huzaif1612-20",
        "Gigabyte": "https://www.amazon.com/dp/B0CH3X3DEF?tag=huzaif1612-20",
    }
    
    # Match detected products with test links
    product_affiliate_links = {}
    for product in detected_products:
        name = product.get("name", "")
        for test_name, test_url in test_links.items():
            if test_name.lower() in name.lower():
                product_affiliate_links[name] = test_url
                print(f"  ✓ Added link for: {name}")
                break
    
    state["product_affiliate_links"] = product_affiliate_links
    print(f"✓ Total links added: {len(product_affiliate_links)}")
    print()
    
    # Step 8: Assemble blog
    print("📚 Step 8: Assembling complete blog...")
    try:
        assembly_result = await blog_assembler_node(state)
        state.update(assembly_result)
        markdown = state.get("assembled_blog", "")
        word_count = len(markdown.split())
        print(f"✓ Blog assembled: {word_count} words")
        print(f"✓ Markdown length: {len(markdown)} characters")
    except Exception as e:
        print(f"❌ Blog assembly failed: {e}")
        return False
    print()
    
    # Step 9: Export to Uniscolian
    print("🚀 Step 9: Exporting to Uniscolian with affiliate buttons...")
    try:
        # Determine top pick
        top_pick = None
        if detected_products:
            top_pick = detected_products[0].get("name")
        
        result = export_post_to_uniscolian(
            markdown=markdown,
            topic=topic,
            keywords=[k.get("keyword", "") for k in keywords[:5]],
            generate_image=False,  # Skip image for speed
            add_related=True,
            update_sitemap=True,
            avoid_duplicates=True,
            product_affiliate_links=product_affiliate_links,
            top_pick_product=top_pick,
        )
        
        print(f"✓ Export successful!")
        print(f"  📁 Slug: {result.get('slug', 'N/A')}")
        print(f"  📊 Words: {result.get('word_count', 0)}")
        print(f"  🗺️  Sitemap: {'Updated' if result.get('sitemap_updated') else 'Already exists'}")
        
        # Check for affiliate button injection
        html_path = result.get("html_path", "")
        button_count = 0
        table_button_count = 0
        disclosure_count = 0
        
        if html_path and Path(html_path).exists():
            html_content = Path(html_path).read_text(encoding="utf-8")
            
            # Count affiliate buttons
            button_count = html_content.count("amazon-affiliate-btn")
            table_button_count = html_content.count("amazon-btn-table")
            disclosure_count = html_content.count("affiliate-disclosure")
            
            print(f"\n  💰 Affiliate Button Verification:")
            print(f"    - Product buttons: {button_count}")
            print(f"    - Table buttons: {table_button_count}")
            print(f"    - Disclosure footers: {disclosure_count}")
            
            if button_count > 0:
                print(f"\n  ✅ SUCCESS: Affiliate buttons injected!")
                print(f"  📄 Preview: {html_path}")
                print(f"  🌐 Open in browser to verify")
            else:
                print(f"\n  ⚠️  WARNING: No affiliate buttons found in HTML")
                print(f"     Check if product_affiliate_links were passed correctly")
        else:
            print(f"  ⚠️  HTML file not found at: {html_path}")
            
    except Exception as e:
        print(f"❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    
    # Step 10: Final verification
    print("=" * 80)
    print("📊 FINAL VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"✓ Keywords generated: {len(keywords)}")
    print(f"✓ Sub-prompts created: {len(sub_prompts)}")
    print(f"✓ Sections generated: {sections_to_generate}")
    print(f"✓ Products detected: {len(detected_products)}")
    print(f"✓ Affiliate links added: {len(product_affiliate_links)}")
    print(f"✓ Blog assembled: {word_count} words")
    print(f"✓ Exported to Uniscolian: Yes")
    print()
    
    if button_count > 0:
        print("🎉 ALL SYSTEMS WORKING!")
        print("   Affiliate buttons are being injected correctly.")
        print(f"   Open this file to verify: {html_path}")
    else:
        print("⚠️  PARTIAL SUCCESS")
        print("   Pipeline works but affiliate buttons not injected.")
        print("   Check product_affiliate_links dictionary.")
    
    print()
    print("=" * 80)
    
    return True


def main():
    """Main entry point."""
    print("\n🧪 Starting automated affiliate system verification...\n")
    
    try:
        success = asyncio.run(run_full_pipeline())
        
        if success:
            print("\n✅ Verification completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Verification failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()