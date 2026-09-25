"""TDD tests for structured competitor product extraction (Tables + H2/H3s)."""
import pytest


def test_extract_tables_from_html():
    from backend.tools.content_analyzer import extract_tables
    html = """
    <html><body><article>
    <table>
        <tr><th>Product</th><th>Rating</th></tr>
        <tr><td>Dell XPS 15</td><td>9/10</td></tr>
        <tr><td>MacBook Pro 16</td><td>9.5/10</td></tr>
    </table>
    </article></body></html>
    """
    tables = extract_tables(html)
    assert len(tables) >= 1
    assert "Dell XPS 15" in tables[0]
    assert "MacBook Pro 16" in tables[0]
    assert "|" in tables[0]  # Must be pipe-separated for LLM


def test_build_competitor_content_includes_tables_and_h3s():
    from core.selectors.product_selector import _build_competitor_content
    data = {
        "scraped_articles": [{
            "url": "pcmag.com",
            "title": "Best Laptops",
            "h2_titles": ["Best Overall", "Best Budget"],
            "h3_titles": ["Dell XPS 15", "MacBook Air M2"],
            "tables": ["Product | Rating\nDell XPS 15 | 9/10"],
            "content_snippet": "Welcome to our guide..."
        }]
    }
    result = _build_competitor_content(data)
    assert "Dell XPS 15" in result
    assert "MacBook Air M2" in result
    assert "Product | Rating" in result
    assert "[QUICK COMPARISON TABLES]" in result
    assert "[ARTICLE STRUCTURE" in result
