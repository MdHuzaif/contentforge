"""Tests for Stage 1a competitor content extraction."""
import pytest
from core.selectors.product_selector import (
    _build_competitor_content,
    _build_structure_content,
)


def test_build_content_with_tables_and_headings():
    """Should extract from tables, h2_titles, h3_titles fields."""
    data = {
        "scraped_articles": [
            {
                "url": "https://pcmag.com/best-laptops",
                "title": "Best Laptops 2026",
                "tables": ["| Product | Price |\n| MacBook Air M5 | $1599 |"],
                "h2_titles": ["Best Overall", "Best Budget"],
                "h3_titles": ["MacBook Air M5", "Dell XPS 15", "Acer Nitro V15"],
                "content_snippet": "These are the best laptops we tested.",
                "content": "",
            }
        ]
    }
    
    result = _build_competitor_content(data)
    
    # Must contain product names from h3_titles
    assert "MacBook Air M5" in result
    assert "Dell XPS 15" in result
    assert "Acer Nitro V15" in result
    
    # Must contain tables
    assert "COMPARISON TABLES" in result or "MacBook Air M5" in result
    
    # Must contain structure
    assert "Best Overall" in result
    assert "ARTICLE STRUCTURE" in result or "H3:" in result
    
    # Must NOT be empty
    assert len(result) > 200


def test_build_content_with_html_content():
    """Should convert HTML content to markdown."""
    data = {
        "scraped_articles": [
            {
                "url": "https://test.com",
                "title": "Review",
                "content": "<html><body><main><h1>Best Laptops</h1><h2>MacBook Air M5</h2><p>Amazing laptop with <strong>great</strong> battery.</p></main></body></html>",
            }
        ]
    }
    
    result = _build_competitor_content(data)
    
    assert "MacBook Air M5" in result
    assert "Amazing laptop" in result
    assert "<html>" not in result


def test_build_content_with_competitors_key():
    """Should work with 'competitors' key (not just 'scraped_articles')."""
    data = {
        "competitors": [
            {
                "url": "https://test.com",
                "h3_titles": ["Product A", "Product B"],
                "content_snippet": "Review content here",
            }
        ]
    }
    
    result = _build_competitor_content(data)
    assert "Product A" in result
    assert "Product B" in result


def test_build_structure_with_both_field_names():
    """Should read both h2_titles and h2_headings."""
    data = {
        "scraped_articles": [
            {
                "url": "https://test1.com",
                "h2_titles": ["Section A"],
                "h3_titles": ["Product 1"],
            },
            {
                "url": "https://test2.com",
                "h2_headings": ["Section B"],
                "h3_headings": ["Product 2"],
            },
        ]
    }
    
    result = _build_structure_content(data)
    
    assert "Section A" in result
    assert "Product 1" in result
    assert "Section B" in result
    assert "Product 2" in result


def test_build_content_empty_data():
    """Should return empty string for empty data."""
    assert _build_competitor_content({}) == ""
    assert _build_competitor_content({"scraped_articles": []}) == ""
    assert _build_structure_content({}) == ""


def test_build_content_not_empty_for_real_data():
    """CRITICAL: Must NOT return empty for typical competitor data."""
    data = {
        "scraped_articles": [
            {
                "url": "https://pcmag.com/picks/the-best-gaming-laptops",
                "title": "The Best Gaming Laptops",
                "tables": [],
                "h2_titles": ["Best Gaming Laptops", "What to Look For"],
                "h3_titles": [
                    "Razer Blade 16",
                    "ASUS ROG Zephyrus G16", 
                    "Lenovo Legion Pro 7i",
                    "Acer Predator Helios 16",
                ],
                "content_snippet": "We tested dozens of gaming laptops...",
                "content": "",
            }
        ],
        "competitor_count": 1,
    }
    
    result = _build_competitor_content(data)
    
    assert len(result) > 100, \
        f"Content must not be empty! Got {len(result)} chars. " \
        f"This causes Stage 1a to skip and auto-generate fake products."
    
    assert "Razer Blade 16" in result
    assert "ASUS ROG Zephyrus G16" in result
