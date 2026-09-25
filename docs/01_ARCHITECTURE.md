# Architecture

## Pipeline Flow (Phase 1: Data Gathering)

1. keyword_research_node → 10 keywords
2. competitor_analysis_node → scrape top SERP results (Tavily search)
3. content_type_classification → product_recommendation / informational
4. product_selector (if product_recommendation)
5. product_deep_dive (per product)

## Product Selection Pipeline

File: core/selectors/product_selector.py
Function: extract_products_universal()

Stage 1a: _build_competitor_content() + _build_structure_content()
          → LLM extracts candidate products (DYNAMIC count, no quota)
Stage 1b: intelligent_product_selection() → filter to target_count
Stage 1c: balance_tiers() → ensure premium/mid/budget mix
Stage 2:  fallback to structure headings (if Stage 1a returns 0)
Stage 3:  LLM auto-generate (last resort)
Retry:    If JSON parse fails, retry with simpler prompt

## Product Deep Dive Pipeline

File: core/post_processors/product_deep_dive.py
Function: deep_dive_product()

1. _smart_search() → Tavily search with blocked_domains filter
2. _extract_youtube_transcript() → youtube-transcript-api (may fail)
3. _crawl_until_success() → early stop at 4 pages
   - Try httpx + _html_to_markdown() first (FREE)
   - Fall back to Firecrawl markdown (1 credit)
4. LLM extraction → specs, pros, cons, quotes, price

## Key Functions Map

| Function | File | Purpose |
|----------|------|---------|
| extract_products_universal | core/selectors/product_selector.py | Main product selector |
| _build_competitor_content | product_selector.py | Markdown from scraped articles |
| _build_structure_content | product_selector.py | H2/H3 hierarchy |
| _validate_and_enrich | product_selector.py | Validate/dedupe products |
| intelligent_product_selection | product_selector.py | Stage 1b LLM selection |
| balance_tiers | product_selector.py | Stage 1c tier balance |
| filter_outdated_products | product_selector.py | Freshness safety net |
| deep_dive_product | core/post_processors/product_deep_dive.py | Per-product research |
| _smart_search | product_deep_dive.py | Tavily search + domain filter |
| _crawl_until_success | product_deep_dive.py | Crawl with early stop |
| _html_to_markdown | product_deep_dive.py | HTML → structured markdown |
| _extract_youtube_transcript | product_deep_dive.py | YouTube transcript |

## Critical Data Structures

### competitor_data (from competitor_analysis)
```python
{
    "status": "completed",
    "topic": "...",
    "competitors": [...],
    "metrics": {...},
    "gap_analysis": "...",
    "sources": [...],
    "scraped_articles": [
        {
            "url": "...",
            "word_count": 0,
            "h1_count": 0, "h2_count": 0, "h3_count": 0,
            "headings": [...],      # Mixed list (ALL headings)
            "tables": [...],
            "content": "",          # Often EMPTY — use headings/tables
            "content_snippet": "",  # Fallback text
        }
    ]
}
```
IMPORTANT: content_analyzer stores headings as a MIXED list.
product_selector must handle BOTH:
- `"h2_titles"` / `"h3_titles"` (separate lists) — preferred
- `"headings"` (mixed list with level info) — fallback

### Blocked Domains (in _smart_search)
```python
blocked_domains = [
    "reddit.com", "amazon.com", "facebook.com", "twitter.com",
    "indeed.com", "glassdoor.com", "linkedin.com", "cbinsights.com",
    "ziprecruiter.com", "monster.com",
    "walmart.com", "target.com",
    "instagram.com", "tiktok.com", "pinterest.com"
]
```
