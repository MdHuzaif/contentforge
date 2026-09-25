"""TDD tests: Level 2 - Complete Deep Dive Replacement."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_smart_search_returns_filtered_urls():
    """_smart_search must return URLs without Reddit/Amazon."""
    from core.post_processors.product_deep_dive import _smart_search
    
    mock_results = [
        {"url": "https://tomshardware.com/review/xyz", "title": "T1", "snippet": "s1"},
        {"url": "https://reddit.com/r/buildapc/xyz", "title": "T2", "snippet": "s2"},
        {"url": "https://amazon.com/dp/B0XYZ", "title": "T3", "snippet": "s3"},
        {"url": "https://pcmag.com/review/xyz", "title": "T4", "snippet": "s4"},
        {"url": "https://youtube.com/watch?v=abc123", "title": "T5", "snippet": "s5"},
        {"url": "https://techradar.com/review/xyz", "title": "T6", "snippet": "s6"},
        {"url": "https://laptopmag.com/review/xyz", "title": "T7", "snippet": "s7"},
        {"url": "https://wired.com/review/xyz", "title": "T8", "snippet": "s8"},
        {"url": "https://theverge.com/review/xyz", "title": "T9", "snippet": "s9"},
        {"url": "https://pcgamer.com/review/xyz", "title": "T10", "snippet": "s10"},
    ]
    
    with patch('core.post_processors.product_deep_dive.get_top_results', 
               new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_results
        
        result = await _smart_search("MacBook Air M5")
        
        # Should filter out Reddit and Amazon
        urls = result["web_urls"]
        assert not any("reddit.com" in u for u in urls)
        assert not any("amazon.com" in u for u in urls)
        
        # Should separate YouTube URLs
        youtube_urls = result["youtube_urls"]
        web_urls = result["web_urls"]
        assert len(youtube_urls) == 1
        assert len(web_urls) >= 5


@pytest.mark.asyncio
async def test_youtube_transcript_extraction():
    """_extract_youtube_transcript must return transcript text."""
    from core.post_processors.product_deep_dive import _extract_youtube_transcript
    
    with patch('core.post_processors.product_deep_dive.YouTubeTranscriptApi') as mock_yt:
        mock_transcript = [
            {"text": "hey guys today we review the macbook air m5"},
            {"text": "the battery life is amazing about 18 hours"},
            {"text": "the only downside is the price at 1599 dollars"},
        ]
        mock_yt.get_transcript.return_value = mock_transcript
        
        transcript = await _extract_youtube_transcript(
            "https://youtube.com/watch?v=abc123"
        )
        
        assert transcript is not None
        assert "macbook air m5" in transcript.lower()
        assert "battery life" in transcript.lower()


@pytest.mark.asyncio
async def test_transcripts_to_markdown():
    """_transcripts_to_markdown must convert transcripts to structured markdown."""
    from core.post_processors.product_deep_dive import _transcripts_to_markdown
    
    transcripts = [
        "hey guys today we review the macbook air m5 the battery life is amazing",
        "the display is gorgeous but the price is steep at 1599",
    ]
    
    with patch('core.post_processors.product_deep_dive.LLMRouter') as mock_llm:
        mock_instance = MagicMock()
        mock_instance.generate_text = AsyncMock(return_value="""## Specs
- M5 chip
- 18 hour battery

## Pros
- Amazing battery life
- Gorgeous display

## Cons
- Expensive ($1599)

## User Quotes
> "the battery life is amazing"
> "the display is gorgeous"
""")
        mock_llm.return_value = mock_instance
        
        markdown = await _transcripts_to_markdown(transcripts, "MacBook Air M5")
        
        assert "## Specs" in markdown
        assert "## Pros" in markdown
        assert "## Cons" in markdown


@pytest.mark.asyncio
async def test_crawl_until_success_early_stop():
    """_crawl_until_success must stop after 4 successful pages."""
    from core.post_processors.product_deep_dive import _crawl_until_success
    
    crawl_count = {"count": 0}
    
    async def fake_httpx(url):
        crawl_count["count"] += 1
        return "<html>" + "word " * 200 + "</html>"
    
    urls = [f"https://site{i}.com/review" for i in range(10)]
    
    with patch('core.post_processors.product_deep_dive._httpx_fetch', 
               side_effect=fake_httpx):
        results = await _crawl_until_success(urls, target_count=4)
        
        assert len(results) == 4
        assert crawl_count["count"] <= 5  # Should stop early


@pytest.mark.asyncio
async def test_deep_dive_product_new_flow():
    """deep_dive_product must use new flow (1 search + transcripts + early stop)."""
    from core.post_processors.product_deep_dive import deep_dive_product
    
    with patch('core.post_processors.product_deep_dive._smart_search') as mock_search:
        mock_search.return_value = {
            "youtube_urls": ["https://youtube.com/watch?v=abc"],
            "web_urls": [f"https://site{i}.com" for i in range(8)],
            "all_results": [
                {"url": f"https://site{i}.com", "title": f"T{i}", "snippet": f"snippet {i}"}
                for i in range(8)
            ],
        }
        
        with patch('core.post_processors.product_deep_dive._extract_youtube_transcript',
                   new_callable=AsyncMock) as mock_yt:
            mock_yt.return_value = "macbook air m5 review transcript"
            
            with patch('core.post_processors.product_deep_dive._transcripts_to_markdown',
                       new_callable=AsyncMock) as mock_md:
                mock_md.return_value = "## Specs\n- M5 chip"
                
                with patch('core.post_processors.product_deep_dive._crawl_until_success',
                           new_callable=AsyncMock) as mock_crawl:
                    mock_crawl.return_value = [
                        {"url": "https://site1.com", "content": "# Review content", "source_type": "httpx"},
                        {"url": "https://site2.com", "content": "# More content", "source_type": "httpx"},
                        {"url": "https://site3.com", "content": "# Extra content", "source_type": "httpx"},
                        {"url": "https://site4.com", "content": "# Final content", "source_type": "httpx"},
                    ]
                    
                    with patch('core.post_processors.product_deep_dive.LLMRouter') as mock_llm:
                        mock_instance = MagicMock()
                        mock_instance.generate_text = AsyncMock(return_value='{"key_specs": ["M5 chip"], "real_pros": ["fast"], "real_cons": ["expensive"], "user_quotes": [], "expert_verdict": "Great", "best_for": "professionals", "price_range": "$1599", "target_audience": "creatives"}')
                        mock_llm.return_value = mock_instance
                        
                        result = await deep_dive_product("MacBook Air M5", "laptop")
                        
                        assert result["found"] is True
                        assert "M5 chip" in result["key_specs"]


def test_old_search_product_disabled():
    """Old _search_product function must not exist or be disabled."""
    import core.post_processors.product_deep_dive as pdd
    
    # Old function should be removed or clearly marked disabled
    if hasattr(pdd, '_search_product'):
        # If it exists, it must not be called in production flow
        import inspect
        source = inspect.getsource(pdd.deep_dive_product)
        assert '_search_product' not in source, \
            "Old _search_product must not be called in deep_dive_product"
