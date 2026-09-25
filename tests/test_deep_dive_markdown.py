"""TDD tests: Level 2 Deep Dive markdown enhancement."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_crawl_until_success_uses_markdown():
    """_crawl_until_success must use _html_to_markdown instead of _html_to_text."""
    from core.post_processors.product_deep_dive import _crawl_until_success
    
    mock_html = """<!DOCTYPE html>
<html>
<body>
<main>
<h1>MacBook Air M5 Review</h1>
<h2>Key Specifications</h2>
<ul>
<li>M5 chip with 10-core CPU</li>
<li>18-hour battery life</li>
<li>16GB unified memory</li>
</ul>
<p>The performance is <strong>amazing</strong> for productivity.</p>
<table>
<tr><th>Feature</th><th>Value</th></tr>
<tr><td>Price</td><td>$1,599</td></tr>
</table>
</main>
</body>
</html>"""
    
    with patch('core.post_processors.product_deep_dive._httpx_fetch',
               new_callable=AsyncMock) as mock_httpx:
        mock_httpx.return_value = mock_html
        
        results = await _crawl_until_success(
            ["https://example.com/review"],
            target_count=1
        )
        
        assert len(results) == 1
        content = results[0]["content"]
        
        # Must contain markdown structure (not plain text)
        assert "# MacBook Air M5 Review" in content, \
            "H1 must be converted to markdown heading"
        assert "## Key Specifications" in content, \
            "H2 must be converted to markdown heading"
        assert "- M5 chip with 10-core CPU" in content, \
            "List items must have markdown bullet markers"
        assert "**amazing**" in content, \
            "Bold text must be preserved as markdown"
        assert "| Feature | Value |" in content, \
            "Tables must be converted to markdown tables"
        
        # Must NOT contain HTML tags
        assert "<h1>" not in content
        assert "<ul>" not in content
        assert "<strong>" not in content
        assert "<table>" not in content


@pytest.mark.asyncio
async def test_crawl_source_type_is_httpx_markdown():
    """When httpx succeeds, source_type should indicate markdown conversion."""
    from core.post_processors.product_deep_dive import _crawl_until_success
    
    mock_html = "<html><body><main><h1>Test</h1><p>This is a test content paragraph that is long enough to exceed the minimum length threshold for crawling successfully.</p></main></body></html>"
    
    with patch('core.post_processors.product_deep_dive._httpx_fetch',
               new_callable=AsyncMock) as mock_httpx:
        mock_httpx.return_value = mock_html
        
        results = await _crawl_until_success(
            ["https://example.com"],
            target_count=1
        )
        
        assert results[0]["source_type"] in ["httpx", "httpx_markdown"], \
            "source_type should indicate httpx success with markdown"


@pytest.mark.asyncio
async def test_deep_dive_product_receives_markdown():
    """End-to-end: deep_dive_product should receive markdown content for extraction."""
    from core.post_processors.product_deep_dive import deep_dive_product
    
    mock_html = """<!DOCTYPE html>
<html><body><main>
<h1>Dell XPS 15 Review</h1>
<h2>Specs</h2>
<ul><li>Intel Core i9</li><li>32GB RAM</li></ul>
<p>An <strong>excellent</strong> choice for creators.</p>
</main></body></html>"""
    
    with patch('core.post_processors.product_deep_dive._smart_search',
               new_callable=AsyncMock) as mock_search:
        mock_search.return_value = {
            "youtube_urls": [],
            "web_urls": ["https://example.com/review"],
            "all_results": [],
        }
        
        with patch('core.post_processors.product_deep_dive._httpx_fetch',
                   new_callable=AsyncMock) as mock_httpx:
            mock_httpx.return_value = mock_html
            
            with patch('core.post_processors.product_deep_dive.LLMRouter') as mock_llm:
                mock_instance = MagicMock()
                captured = {"prompt": ""}
                
                async def fake_generate(prompt="", system_prompt="", **kwargs):
                    captured["prompt"] = prompt
                    return '{"key_specs": ["i9", "32GB"], "real_pros": ["excellent"], "real_cons": [], "user_quotes": [], "expert_verdict": "Great", "best_for": "creators", "price_range": "$2000", "target_audience": "creators"}'
                
                mock_instance.generate_text = AsyncMock(side_effect=fake_generate)
                mock_llm.return_value = mock_instance
                
                result = await deep_dive_product("Dell XPS 15", "laptop")
                
                prompt = captured["prompt"]
                assert "# Dell XPS 15 Review" in prompt or "Dell XPS 15 Review" in prompt
                assert "## Specs" in prompt or "Specs" in prompt
                assert "<html>" not in prompt or "<main>" not in prompt


def test_html_to_markdown_function_exists():
    """Verify _html_to_markdown is importable from product_selector."""
    from core.selectors.product_selector import _html_to_markdown
    
    html = "<html><body><main><h1>Title</h1><p>Text</p></main></body></html>"
    result = _html_to_markdown(html)
    
    assert "# Title" in result
    assert "Text" in result
    assert "<h1>" not in result


def test_html_to_text_is_deprecated_or_removed():
    """_html_to_text should either be removed or marked deprecated."""
    import core.post_processors.product_deep_dive as pdd
    
    if hasattr(pdd, '_html_to_text'):
        import inspect
        source = inspect.getsource(pdd._crawl_until_success)
        assert '_html_to_text' not in source, \
            "_crawl_until_success must NOT use _html_to_text anymore"
