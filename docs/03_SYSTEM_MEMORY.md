# System Memory (Current State)

**Last Updated:** 2026-09-25

## Configuration

| Setting | Value | Location |
|---|---|---|
| Default target_count | 10 | `extract_products_universal()` |
| Extraction strategy | DYNAMIC (no quota) | `EXTRACTION_PROMPT_TEMPLATE` Rule 5 |
| YouTube API version | pinned 0.6.2 | `requirements.txt` |
| Deep Dive pages/product | 4 (early stop) | `_crawl_until_success()` |
| Blocked domains | 15 domains | `_smart_search()` |
| Gemini model | gemini-3.5-flash-lite | `LLMRouter` routing |

## Gotchas / Learnings

- LLM hallucinates if forced to hit a product quota. Use dynamic extraction.
- `youtube-transcript-api` v1.x removed `get_transcript()`; stay on 0.6.2.
- `content_analyzer` uses `"headings"` key (mixed); selector must handle both `"headings"` and `"h2_titles"` / `"h3_titles"` formats.
- HuggingFace rejects binary files — never commit `.db` files.
- Many YouTube videos have subtitles disabled → transcript fails. Fallback: web articles only.
- Reddit and Amazon always return 403 → already in `blocked_domains`.
- Python 3.10 asyncio shows "ValueError: Invalid file descriptor" — cosmetic only, ignore.

## Environment Variables Required
- `TAVILY_API_KEY`
- `FIRECRAWL_API_KEY`
- `GEMINI_API_KEY`
- `PRODUCT_DEEP_DIVE` (true/false)

## API Credits Usage

| API | Cost | Notes |
|---|---|---|
| Tavily | 1 credit per search | 1 per product deep dive |
| Firecrawl | 1 credit per scrape | Only when httpx fails |
| Gemini | Free tier | All LLM calls |
| YouTube transcript | Free | But often fails (subtitles) |

## Current Status
- Phase 1 (data gathering): **WORKING**
- Product selection (Stage 1a/1b/1c): **WORKING** (dynamic extraction)
- Deep Dive (Level 2): **WORKING**
- Shopping signals: **SKIPPED** (using Deep Dive for refinement)
- YouTube transcripts: **PARTIAL** (subtitles often disabled)
