import pytest
from core.selectors.product_selector import _build_competitor_content, _html_to_markdown

def test_html_to_markdown_headings():
    """Should convert HTML headings to markdown."""
    html = """
    <html>
    <body>
    <main>
    <h1>Best Laptops 2026</h1>
    <h2>The MacBook Air M5</h2>
    <p>The MacBook Air M5 is amazing.</p>
    <h3>Key Features</h3>
    <ul>
    <li>M5 chip</li>
    <li>18-hour battery</li>
    </ul>
    </main>
    </body>
    </html>
    """
    
    markdown = _html_to_markdown(html)
    
    # Should have markdown headings
    assert "# Best Laptops 2026" in markdown
    assert "## The MacBook Air M5" in markdown
    assert "### Key Features" in markdown
    
    # Should have list items
    assert "- M5 chip" in markdown
    assert "- 18-hour battery" in markdown
    
    # Should NOT have HTML tags
    assert "<h1>" not in markdown
    assert "<ul>" not in markdown

def test_html_to_markdown_tables():
    """Should convert HTML tables to markdown tables."""
    html = """
    <table>
    <tr><th>Product</th><th>Price</th></tr>
    <tr><td>MacBook Air M5</td><td>$1,599</td></tr>
    <tr><td>Dell XPS 15</td><td>$1,799</td></tr>
    </table>
    """
    
    markdown = _html_to_markdown(html)
    
    # Should have markdown table
    assert "| Product | Price |" in markdown
    assert "|---|---|" in markdown
    assert "| MacBook Air M5 | $1,599 |" in markdown

def test_html_to_markdown_removes_noise():
    """Should remove nav, footer, scripts."""
    html = """
    <html>
    <body>
    <nav>Navigation Menu</nav>
    <main>
    <h1>Article Title</h1>
    <p>Real content here</p>
    </main>
    <footer>Footer Links</footer>
    <script>alert('bad');</script>
    </body>
    </html>
    """
    
    markdown = _html_to_markdown(html)
    
    # Should have main content
    assert "Article Title" in markdown
    assert "Real content here" in markdown
    
    # Should NOT have noise
    assert "Navigation Menu" not in markdown
    assert "Footer Links" not in markdown
    assert "alert" not in markdown

def test_build_competitor_content_full():
    """Should build complete competitor content with markdown."""
    test_data = {
        "scraped_articles": [
            {
                "url": "https://test.com/laptops",
                "content": """<!DOCTYPE html>
<html>
<body>
<main>
<h1>Best Laptops 2026</h1>
<h2>MacBook Air M5</h2>
<p>The MacBook Air M5 is <strong>amazing</strong> for productivity.</p>
<h3>Pros</h3>
<ul>
<li>18-hour battery</li>
<li>Fast M5 chip</li>
</ul>
</main>
</body>
</html>"""
            }
        ]
    }
    
    result = _build_competitor_content(test_data)
    
    # Should have article header
    assert "### Article 1: https://test.com/laptops" in result
    
    # Should have markdown headings
    assert "# Best Laptops 2026" in result
    assert "## MacBook Air M5" in result
    assert "### Pros" in result
    
    # Should have markdown formatting
    assert "**amazing**" in result  # Bold preserved
    assert "- 18-hour battery" in result  # List preserved
    
    # Should NOT have HTML tags
    assert "<h1>" not in result
    assert "<strong>" not in result

def test_already_clean_content():
    """Should handle content that's already clean text."""
    test_data = {
        "scraped_articles": [
            {
                "url": "https://test.com",
                "content": "The MacBook Air M5 is amazing for productivity."
            }
        ]
    }
    
    result = _build_competitor_content(test_data)
    assert "MacBook Air M5" in result
    assert "amazing" in result
