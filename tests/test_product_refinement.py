"""Tests for the product detection and refinement system.
Includes mocked LLM tests to verify the full flow without real API calls."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.post_processors.product_detector import (
    detect_product_sections,
    format_detection_report,
    get_section_detail,
    _is_generic_heading,
    _extract_product_name,
)
from core.post_processors import product_refiner

SAMPLE_BLOG = """# Best Budget Laptops 2026

## Introduction

Welcome to our guide on the best budget laptops.

## Top Laptop Picks

### 1. MacBook Air M2

The MacBook Air M2 offers excellent performance with its Apple silicon chip. It has great battery life and a beautiful display. The build quality is premium and it weighs only 2.7 pounds.

### 2. ASUS VivoBook 15

The ASUS VivoBook 15 provides solid performance for everyday tasks. It features a 15.6-inch display and comes with 16GB of RAM.

### 3. Dell XPS 13

The Dell XPS 13 is known for its stunning display and compact design. It offers powerful performance in a portable package.

## Buying Guide

### How to Choose the Right Laptop

Consider your needs before buying. Think about battery life, display quality, and performance requirements.

### What Specs Matter Most

RAM and storage are important considerations for most users.

## Conclusion

These are our top picks for budget laptops in 2026.
"""


def test_detect_product_sections():
    """Should detect 3 product sections (MacBook, ASUS, Dell) but not generic H3s."""
    sections = detect_product_sections(SAMPLE_BLOG)
    
    assert len(sections) == 3, f"Expected 3, got {len(sections)}: {[s['product_name'] for s in sections]}"
    
    names = [s["product_name"].lower() for s in sections]
    assert any("macbook" in n for n in names), f"MacBook not found in {names}"
    assert any("vivobook" in n or "asus" in n for n in names), f"ASUS not found in {names}"
    assert any("xps" in n or "dell" in n for n in names), f"Dell not found in {names}"
    
    headings = [s["heading"].lower() for s in sections]
    assert not any("how to choose" in h for h in headings)
    assert not any("what specs" in h for h in headings)
    
    print("[OK] test_detect_product_sections passed")


def test_generic_heading_detection():
    """Generic H3 headings should be correctly identified."""
    assert _is_generic_heading("How to Choose the Right Laptop") is True
    assert _is_generic_heading("What Specs Matter Most") is True
    assert _is_generic_heading("Introduction") is True
    assert _is_generic_heading("Buying Guide") is True
    assert _is_generic_heading("MacBook Air M2") is False
    assert _is_generic_heading("ASUS VivoBook 15") is False
    print("[OK] test_generic_heading_detection passed")


def test_product_name_extraction():
    """Should extract product names from various H3 formats."""
    assert "MacBook" in _extract_product_name("1. MacBook Air M2")
    assert "VivoBook" in _extract_product_name("2. ASUS VivoBook 15")
    assert "XPS" in _extract_product_name("Best Overall: Dell XPS 13")
    print("[OK] test_product_name_extraction passed")


def test_empty_blog():
    """Empty blog should return empty list."""
    assert detect_product_sections("") == []
    assert detect_product_sections("   ") == []
    print("[OK] test_empty_blog passed")


def test_no_products_blog():
    """Blog without products should return empty list."""
    blog = "# Guide\n\n## Introduction\n\nSome text.\n\n## How To\n\n### Step One\n\nDo this."
    sections = detect_product_sections(blog)
    assert len(sections) == 0
    print("[OK] test_no_products_blog passed")


def test_format_detection_report():
    """Detection report should be formatted correctly."""
    sections = detect_product_sections(SAMPLE_BLOG)
    report = format_detection_report(sections)
    
    assert "Detected" in report
    assert "Product Sections" in report
    assert "MacBook" in report
    assert "Section Preview" in report  # preview column exists
    print("[OK] test_format_detection_report passed")


def test_get_section_detail():
    """Detail view should show full section content."""
    sections = detect_product_sections(SAMPLE_BLOG)
    detail = get_section_detail(sections[0])
    
    assert sections[0]["heading"] in detail
    assert sections[0]["product_name"] in detail
    assert sections[0]["content"] in detail  # Full content shown
    assert "will be refined" in detail
    print("[OK] test_get_section_detail passed")


def test_headings_not_changed():
    """H3 headings should remain intact in section content boundaries."""
    sections = detect_product_sections(SAMPLE_BLOG)
    for s in sections:
        assert s["heading"] in SAMPLE_BLOG
    print("[OK] test_headings_not_changed passed")


def test_refinement_with_mocked_llm():
    """CRITICAL: Full refinement flow with mocked LLM and shopping signals."""
    
    async def run_test():
        # Mock signals
        mock_signals = {
            "MacBook Air M2": {
                "product": "MacBook Air M2",
                "praise": ["battery life", "silent", "portable"],
                "complaints": ["heating under load"],
                "snippet_count": 5,
                "found": True,
            },
            "ASUS VivoBook 15": {
                "product": "ASUS VivoBook 15",
                "praise": ["great value", "solid build"],
                "complaints": ["fan noise"],
                "snippet_count": 4,
                "found": True,
            },
            "Dell XPS 13": {
                "product": "Dell XPS 13",
                "praise": ["crisp display", "lightweight"],
                "complaints": ["pricey"],
                "snippet_count": 3,
                "found": True,
            },
        }
        
        # Mock LLM to return a refined section (includes heading)
        def mock_llm_response(prompt, **kwargs):
            # Extract heading from prompt
            import re
            m = re.search(r"### ([^\n]+)", prompt)
            heading = m.group(1) if m else "Product"
            return (f"### {heading}\n\nThis product has been refined with real user feedback. "
                   f"Users consistently praise the battery life, while some note heating under load.")
        
        with patch.object(product_refiner, 'gather_product_signals',
                         new=AsyncMock(side_effect=lambda name, topic="": mock_signals.get(name, {
                             "product": name, "praise": [], "complaints": [], "found": False
                         }))):
            with patch.object(product_refiner.LLMRouter, 'generate_text',
                             new=AsyncMock(side_effect=mock_llm_response)):
                result = await product_refiner.refine_blog_products(SAMPLE_BLOG, "best laptop")
                
                # Should refine 3 sections
                assert result["total_products"] == 3, f"Got {result['total_products']}"
                assert result["skipped"] is False
                assert result["sections_refined"] >= 2, \
                    f"Should refine at least 2, got {result['sections_refined']}"
                
                # Refined blog should contain user signals
                refined = result["refined_blog"]
                assert "refined with real user feedback" in refined.lower() or "battery life" in refined.lower()
                
                # H3 headings should be preserved
                assert "### 1. MacBook Air M2" in refined
                assert "### 2. ASUS VivoBook 15" in refined
                assert "### 3. Dell XPS 13" in refined
                
                # Generic H3s should be unchanged
                assert "### How to Choose the Right Laptop" in refined
                assert "### What Specs Matter Most" in refined
                
                # NO dollar prices should be in refined content
                import re
                assert not re.search(r"\$\s?\d{1,4}", refined), "Refined blog contains dollar prices!"
                
                # Non-product sections should be preserved
                assert "## Introduction" in refined
                assert "## Conclusion" in refined
                
                # Stats should be populated
                assert len(result["stats"]) == 3
                
                print("[OK] test_refinement_with_mocked_llm passed")
    
    asyncio.run(run_test())


def test_refinement_fallback_on_empty_signals():
    """If signals are empty, refinement should still work (original preserved)."""
    
    async def run_test():
        empty_signals = {"product": "X", "praise": [], "complaints": [], "found": False}
        
        with patch.object(product_refiner, 'gather_product_signals',
                         new=AsyncMock(return_value=empty_signals)):
            with patch.object(product_refiner.LLMRouter, 'generate_text',
                             new=AsyncMock(return_value="This should not be used")):
                result = await product_refiner.refine_blog_products(SAMPLE_BLOG, "laptop")
                
                # Should still complete without error
                assert result["total_products"] == 3
                assert "refined_blog" in result
                print("[OK] test_refinement_fallback_on_empty_signals passed")
    
    asyncio.run(run_test())


def test_format_refinement_report():
    """Report formatting should work correctly."""
    result = {
        "sections_refined": 2,
        "total_products": 3,
        "skipped": False,
        "stats": [
            {"product": "MacBook", "praise_found": ["battery"], "complaints_found": [], "was_refined": True},
            {"product": "ASUS", "praise_found": [], "complaints_found": ["loud"], "was_refined": True},
            {"product": "Dell", "praise_found": [], "complaints_found": [], "was_refined": False},
        ],
    }
    report = product_refiner.format_refinement_report(result)
    
    assert "2 of 3" in report
    assert "MacBook" in report
    assert "ASUS" in report
    assert "Dell" in report
    assert "Blog Comparison tab" in report
    print("[OK] test_format_refinement_report passed")


def test_minimum_products_threshold():
    """Should skip refinement if fewer than MIN_PRODUCTS_FOR_REFINEMENT."""
    
    async def run_test():
        # Blog with only 1 product
        short_blog = "# Blog\n\n## Picks\n\n### MacBook Air M2\n\nThis is a laptop."
        result = await product_refiner.refine_blog_products(short_blog, "laptop")
        
        assert result["skipped"] is True
        assert result["refined_blog"] == short_blog  # unchanged
        print("[OK] test_minimum_products_threshold passed")
    
    asyncio.run(run_test())


def main():
    test_detect_product_sections()
    test_generic_heading_detection()
    test_product_name_extraction()
    test_empty_blog()
    test_no_products_blog()
    test_format_detection_report()
    test_get_section_detail()
    test_headings_not_changed()
    test_refinement_with_mocked_llm()
    test_refinement_fallback_on_empty_signals()
    test_format_refinement_report()
    test_minimum_products_threshold()
    print("\n[OK] ALL 12 PRODUCT REFINEMENT TESTS PASSED")


if __name__ == "__main__":
    main()
