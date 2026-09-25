# Decision Log

| Date | Decision | Why | Impact |
|---|---|---|---|
| 2026-09-25 | Removed `target_count * 2` from extraction | LLM hallucinated products to hit quota of 20 | Dynamic extraction, authentic products only |
| 2026-09-25 | Changed prompt to "Extract ALL products mentioned" | Prevents forcing LLM to invent products | Quality over quantity |
| 2026-09-25 | Pinned `youtube-transcript-api==0.6.2` | v1.x removed `get_transcript()` class method | Transcripts work again |
| 2026-09-25 | Added `blocked_domains` list (15 domains) | Irrelevant sources (indeed, walmart, etc.) polluted deep dive data | Cleaner, relevant sources |
| 2026-09-25 | Added early stop at 4 pages in `_crawl_until_success` | Save Firecrawl credits, 4 pages sufficient | Cost reduction |
| 2026-09-25 | Changed `_html_to_text` to `_html_to_markdown` | Plain text lost structure; markdown preserves headings/lists/tables | Better LLM extraction |
| 2026-09-25 | Added `_extract_h2_h3` with defensive type checking | `headings` field was sometimes dict not list, caused KeyError | No more crashes |
| 2026-09-25 | Shopping signals skipped at topic level | Deep Dive provides better per-product signals | Simplified pipeline |
