# Known Issues

| ID | Issue | Severity | Status | Workaround |
|---|---|---|---|---|
| KI-001 | YouTube transcripts fail when subtitles disabled | Medium | Open | Fall back to web articles |
| KI-002 | Reddit/Amazon block scraping (403) | Medium | Won't Fix | Blocked in `_smart_search` |
| KI-003 | ValueError: Invalid file descriptor (cosmetic) | Low | Won't Fix | Ignore (Python 3.10 asyncio bug) |
| KI-004 | Mixed currencies in price (Rs/RM/£/$) | Low | Open | Normalize to USD in prompt |
| KI-005 | Some products get 0 user quotes | Medium | Open | Improve quote extraction prompt |
| KI-006 | Firecrawl rate limit (429) during heavy crawl | Low | Open | Early stop helps; add delay |
| KI-007 | `competitor_data` "content" field often empty | Medium | Fixed | Use headings/tables/content_snippet |
