"""Product Deep Dive: optimized Smart Search + YouTube Transcript + Early Stop Crawl (Level 2)."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

import httpx

from app.config import logger
from backend.llm.router import LLMRouter
from backend.tools.content_analyzer import fetch_main_text
from backend.tools.web_search import get_top_results

# YouTube transcript extraction
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YOUTUBE_TRANSCRIPT_AVAILABLE = True
except ImportError:
    YOUTUBE_TRANSCRIPT_AVAILABLE = False

_OLD_SYSTEM_DISABLED = True  # Level 2 replacement active
_MAX_PAGES_DEFAULT = 4
_PAGE_CHARS = 3000          # per-page truncation
_REAL_SLEEP = asyncio.sleep

_EMPTY = {
    "found": False,
    "key_specs": [],
    "real_pros": [],
    "real_cons": [],
    "user_quotes": [],
    "expert_verdict": "",
    "best_for": "",
    "price_range": "",
    "target_audience": "",
    "sources": [],
}

_EXTRACTION_SYSTEM = """You are a strict product data extraction engine.
You receive text from MULTIPLE numbered sources plus search snippets about
ONE product. Extract ONLY facts explicitly present in the provided text.
NEVER invent specifications, prices, pros, cons or quotes.
Prefer facts confirmed by multiple sources; if sources conflict, omit.
Direct user quotes must be copied VERBATIM with their source domain.
If a field has no support in the text, return an empty list or empty string.
Return ONLY valid JSON with keys:
key_specs (list[str], max 10), real_pros (list[str], max 6),
real_cons (list[str], max 6),
user_quotes (list of {quote, source}, max 3, verbatim only),
expert_verdict (str, one sentence consensus from reviewer sources or ""),
best_for (str, who this product suits or ""),
price_range (str like "$120-$150" or ""),
target_audience (str or "")."""


def deep_dive_enabled() -> bool:
    return os.environ.get("PRODUCT_DEEP_DIVE", "true").strip().lower() \
        not in ("false", "0", "no", "off")


def _max_pages() -> int:
    try:
        return max(1, int(os.environ.get("PRODUCT_DEEP_DIVE_PAGES",
                                         str(_MAX_PAGES_DEFAULT))))
    except ValueError:
        return _MAX_PAGES_DEFAULT


async def _safe_sleep(delay: float):
    try:
        sleep_fn = asyncio.sleep
        if sleep_fn is _REAL_SLEEP:
            await _REAL_SLEEP(delay)
        else:
            res = sleep_fn(delay)
            if asyncio.isfuture(res) or asyncio.iscoroutine(res):
                await res
    except Exception:
        pass


async def _search_product(*args, **kwargs):
    """[DISABLED - Level 2] Old search function. Use _smart_search() instead."""
    if _OLD_SYSTEM_DISABLED:
        raise RuntimeError(
            "_search_product is DISABLED in Level 2. Use _smart_search() instead."
        )


async def _crawl_multi_text(*args, **kwargs):
    """[DISABLED - Level 2] Old crawl function. Use _crawl_until_success() instead."""
    if _OLD_SYSTEM_DISABLED:
        raise RuntimeError(
            "_crawl_multi_text is DISABLED in Level 2. Use _crawl_until_success() instead."
        )


async def _smart_search(product_name: str) -> Dict[str, Any]:
    """Single smart search returning top 10 ranked URLs.
    
    Filters out Reddit and Amazon (blocked sites).
    Separates YouTube URLs from web page URLs.
    
    Cost: 1 Tavily credit (vs old 4 credits)
    """
    query = f"{product_name} review specifications pros cons customer opinions"
    
    try:
        results = await get_top_results(query, max_results=10)
    except Exception as e:
        logger.warning(f"_smart_search failed for {product_name}: {e}")
        return {"youtube_urls": [], "web_urls": [], "all_results": []}
    
    # Filter out blocked domains
    blocked_domains = ["reddit.com", "amazon.com", "facebook.com", "twitter.com"]
    
    filtered = [
        r for r in results
        if not any(domain in r.get("url", "").lower() for domain in blocked_domains)
    ]
    
    # Separate YouTube and web URLs
    youtube_urls = []
    web_urls = []
    
    for r in filtered:
        url = r.get("url", "")
        if "youtube.com" in url or "youtu.be" in url:
            youtube_urls.append(url)
        else:
            web_urls.append(url)
    
    logger.info(
        f"Smart search for {product_name}: {len(filtered)} results "
        f"({len(youtube_urls)} YouTube, {len(web_urls)} web)"
    )
    
    return {
        "youtube_urls": youtube_urls[:2],  # Max 2 YouTube videos
        "web_urls": web_urls,
        "all_results": filtered,
    }


async def _extract_youtube_transcript(url: str) -> Optional[str]:
    """Extract full transcript from YouTube video using youtube-transcript-api.
    
    Cost: FREE (no API credits)
    """
    if not YOUTUBE_TRANSCRIPT_AVAILABLE:
        logger.warning("youtube-transcript-api not installed, skipping YouTube")
        return None
    
    # Extract video ID
    video_id = None
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{6,12}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{6,12})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{6,12})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            break
    
    if not video_id:
        return None
    
    try:
        loop = asyncio.get_event_loop()
        
        def _fetch():
            try:
                res = YouTubeTranscriptApi.get_transcript(video_id)
                if isinstance(res, list):
                    return res
                if hasattr(res, "fetch"):
                    return res.fetch()
                return res
            except Exception as ex:
                logger.debug(f"get_transcript error: {ex}")
                if hasattr(YouTubeTranscriptApi, "list_transcripts"):
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                    try:
                        transcript = transcript_list.find_transcript(['en'])
                    except Exception:
                        transcript = transcript_list.find_generated_transcript(['en'])
                    return transcript.fetch()
                raise
        
        transcript_data = await loop.run_in_executor(None, _fetch)
        
        full_text = " ".join([entry['text'] for entry in transcript_data])
        
        if len(full_text) > 10000:
            full_text = full_text[:10000]
        
        logger.info(f"YouTube transcript extracted: {len(full_text)} chars from {url}")
        return full_text
    
    except Exception as e:
        logger.warning(f"YouTube transcript failed for {url}: {e}")
        return None


TRANSCRIPT_TO_MARKDOWN_PROMPT = """You are an expert product analyst.

Below are YouTube video review transcript(s) for: {product_name}

Extract structured information and return ONLY markdown in this format:

## Specs
- [spec 1]
- [spec 2]

## Pros
- [pro 1]
- [pro 2]

## Cons
- [con 1]
- [con 2]

## User Quotes
> "[direct quote from reviewer]"
> "[another quote]"

## Expert Verdict
[1-2 sentence summary]

=== TRANSCRIPTS ===
{transcripts}

Return ONLY the markdown, no explanation."""


async def _transcripts_to_markdown(
    transcripts: List[str], 
    product_name: str
) -> Optional[str]:
    """Convert YouTube transcripts to structured markdown.
    
    Cost: 1 Gemini call (free tier)
    """
    if not transcripts:
        return None
    
    combined = "\n\n=== NEXT VIDEO ===\n\n".join(transcripts)
    
    prompt = TRANSCRIPT_TO_MARKDOWN_PROMPT.format(
        product_name=product_name,
        transcripts=combined,
    )
    
    try:
        router = LLMRouter(task_type="default")
        markdown = await router.generate_text(
            prompt=prompt,
            system_prompt="Return ONLY markdown, no other text.",
        )
        logger.info(f"Transcripts converted to markdown: {len(markdown)} chars")
        return markdown
    except Exception as e:
        logger.warning(f"Transcript to markdown failed: {e}")
        return None


async def _httpx_fetch(url: str) -> Optional[str]:
    """Fetch URL content via httpx (free)."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.text
    except Exception as e:
        logger.debug(f"_httpx_fetch failed for {url}: {e}")
    return None


def _html_to_text(html: str) -> str:
    """Simple HTML to text conversion using BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        text = soup.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)
    except Exception:
        return ""


async def _firecrawl_fetch_markdown(url: str) -> Optional[str]:
    """Fetch page via Firecrawl in markdown format.
    
    Cost: 1 Firecrawl credit per success
    """
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not key:
        return None
    
    body = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    
    endpoints = [
        "https://api.firecrawl.dev/v2/scrape",
        "https://api.firecrawl.dev/v1/scrape",
    ]
    
    for endpoint in endpoints:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(endpoint, headers=headers, json=body)
                
                if r.status_code == 429:
                    logger.warning("Firecrawl rate limited (429)")
                    return None
                
                r.raise_for_status()
                data = (r.json() or {}).get("data") or {}
                markdown = data.get("markdown") or ""
                
                if len(markdown) > 200:
                    return markdown
                
        except Exception as e:
            logger.debug(f"Firecrawl markdown failed via {endpoint}: {e}")
            continue
    
    return None


async def _crawl_until_success(
    urls: List[str], 
    target_count: int = 4
) -> List[Dict[str, str]]:
    """Crawl URLs in rank order until target_count successes.
    
    Strategy:
    1. Try httpx + BeautifulSoup first (FREE)
    2. If fails, try Firecrawl with markdown format (1 credit)
    3. STOP when target_count pages collected
    
    Cost: 0-4 Firecrawl credits (vs old 4-8)
    """
    successful_pages = []
    
    for url in urls:
        if len(successful_pages) >= target_count:
            logger.info(
                f"Early stop: {len(successful_pages)} pages collected, "
                f"skipping remaining {len(urls) - urls.index(url)} URLs"
            )
            break
        
        # Skip YouTube URLs (handled separately)
        if "youtube.com" in url or "youtu.be" in url:
            continue
        
        # Try 1: httpx (free)
        try:
            html = await _httpx_fetch(url)
            if html and len(html) > 500:
                text = _html_to_text(html)
                if text and len(text) > 300:
                    successful_pages.append({
                        "url": url,
                        "content": text,
                        "source_type": "httpx",
                    })
                    logger.info(f"Crawled via httpx: {url}")
                    continue
        except Exception as e:
            logger.debug(f"httpx failed for {url}: {e}")
        
        # Try 2: Firecrawl with markdown format (1 credit)
        try:
            markdown = await _firecrawl_fetch_markdown(url)
            if markdown and len(markdown) > 300:
                successful_pages.append({
                    "url": url,
                    "content": markdown,
                    "source_type": "firecrawl",
                })
                logger.info(f"Crawled via Firecrawl: {url}")
                continue
        except Exception as e:
            logger.debug(f"Firecrawl failed for {url}: {e}")
    
    logger.info(
        f"Crawl complete: {len(successful_pages)}/{target_count} pages"
    )
    
    return successful_pages


async def _extract_with_llm(product_name: str,
                            pages: List[Dict[str, str]],
                            snippets: List[str]) -> Dict[str, Any]:
    src_blocks = "\n\n".join(
        f"SOURCE {i + 1} ({p['url']}):\n{p.get('text', p.get('content', ''))}"
        for i, p in enumerate(pages)
    ) or "(no pages crawled)"
    user = (f"Product: {product_name}\n\n{src_blocks}\n\n"
            f"SEARCH SNIPPETS:\n" +
            "\n".join(f"- {s}" for s in snippets[:8]) +
            "\n\nExtract verified data as JSON.")
    try:
        router = LLMRouter(task_type="default")
        raw = await router.generate_text(prompt=user,
                                         system_prompt=_EXTRACTION_SYSTEM,
                                         task_type="default")
        m = re.search(r"\{[\s\S]*\}", raw or "")
        if not m:
            logger.warning("Deep dive LLM returned no JSON for %s", product_name)
            return {}
        data = json.loads(m.group())
        if not isinstance(data, dict):
            return {}
        quotes = []
        for q in data.get("user_quotes", [])[:3]:
            if isinstance(q, dict) and q.get("quote"):
                quotes.append({"quote": str(q["quote"])[:300],
                               "source": str(q.get("source", ""))[:80]})
        return {
            "key_specs": [str(x) for x in data.get("key_specs", []) if x][:10],
            "real_pros": [str(x) for x in data.get("real_pros", []) if x][:6],
            "real_cons": [str(x) for x in data.get("real_cons", []) if x][:6],
            "user_quotes": quotes,
            "expert_verdict": str(data.get("expert_verdict", "") or "")[:300],
            "best_for": str(data.get("best_for", "") or "")[:200],
            "price_range": str(data.get("price_range", "") or "")[:60],
            "target_audience": str(data.get("target_audience", "") or "")[:200],
        }
    except Exception as e:
        logger.warning("Deep dive LLM extraction failed for %s: %s",
                       product_name, e)
        return {}


def format_deep_data_block(deep: Dict[str, Any]) -> str:
    """Render verified data + trust/engagement rules; '' when not found."""
    if not deep or not deep.get("found"):
        return ""
    specs = deep.get("key_specs") or []
    pros = deep.get("real_pros") or []
    cons = deep.get("real_cons") or []
    quotes = deep.get("user_quotes") or []
    lines = ["VERIFIED SPECIFICATIONS (use ONLY these; do NOT invent specs):"]
    lines += [f"- {s}" for s in specs] or ["- (none verified)"]
    lines += ["", "REAL PROS from reviews:"]
    lines += [f"- {s}" for s in pros] or ["- (none verified)"]
    lines += ["", "REAL CONS from reviews:"]
    lines += [f"- {s}" for s in cons] or ["- (none verified)"]
    if quotes:
        lines += ["", "REAL USER QUOTES (copy verbatim, attribute naturally):"]
        lines += [f'- "{q["quote"]}" — via {q["source"] or "user review"}'
                  for q in quotes]
    if deep.get("expert_verdict"):
        lines += ["", f'EXPERT VERDICT: "{deep["expert_verdict"]}"']
    lines += ["", f'Best for: {deep.get("best_for") or "general buyers"}']
    lines += [f'Price range: {deep.get("price_range") or "not verified - do not state prices"}']
    lines += [f'Target audience: {deep.get("target_audience") or "general buyers"}']
    lines += ["", "TRUST & ENGAGEMENT RULES:",
              "- Attribute each user quote naturally (e.g. 'as one Reddit user put it, ...').",
              "- Use the EXPERT VERDICT in the section's closing paragraph.",
              "- Open the section by naming who this product is best for.",
              "- Balance praise with at least one real con (honesty builds trust).",
              "- If a spec is not listed above, omit it entirely."]
    return "\n".join(lines)


async def deep_dive_product(product_name: str, category: str = "") -> Dict[str, Any]:
    """Deep dive into a product using NEW Level 2 system.
    
    Flow:
    1. Smart Search (1 Tavily credit) → 10 URLs
    2. YouTube Transcripts (FREE) → max 2 videos
    3. Transcripts to Markdown (1 Gemini call, free tier)
    4. Crawl web pages (0-4 Firecrawl credits, early stop)
    5. LLM Extraction (1 Gemini call, free tier)
    
    Total cost: 1 Tavily + 0-4 Firecrawl = 1-5 credits
    """
    result = dict(_EMPTY)
    result["product"] = product_name
    
    # === PHASE 1: Smart Search (1 Tavily credit) ===
    search_result = await _smart_search(product_name)
    youtube_urls = search_result["youtube_urls"]
    web_urls = search_result["web_urls"]
    all_results = search_result["all_results"]
    
    if not youtube_urls and not web_urls:
        logger.warning(f"No URLs found for {product_name}")
        return result
    
    # === PHASE 2: YouTube Transcripts (FREE) ===
    youtube_markdown = None
    if youtube_urls:
        transcripts = []
        for url in youtube_urls[:2]:  # Max 2 videos
            transcript = await _extract_youtube_transcript(url)
            if transcript:
                transcripts.append(transcript)
        
        if transcripts:
            youtube_markdown = await _transcripts_to_markdown(
                transcripts, product_name
            )
    
    # === PHASE 3: Crawl Web Pages (0-4 Firecrawl credits) ===
    crawled_pages = await _crawl_until_success(web_urls, target_count=4)
    
    # === PHASE 4: Combine All Content ===
    all_content_parts = []
    
    # Add YouTube markdown first (highest quality)
    if youtube_markdown:
        all_content_parts.append(
            f"=== YOUTUBE VIDEO REVIEW (Markdown) ===\n{youtube_markdown}"
        )
    
    # Add crawled web pages
    for page in crawled_pages:
        all_content_parts.append(
            f"=== WEB PAGE: {page['url']} ===\n{page['content'][:5000]}"
        )
    
    # Add search snippets as fallback
    if not all_content_parts and all_results:
        snippets = "\n".join([
            f"- {r.get('title', '')}: {r.get('snippet', '')}"
            for r in all_results
        ])
        all_content_parts.append(f"=== SEARCH SNIPPETS ===\n{snippets}")
    
    if not all_content_parts:
        logger.warning(f"No content collected for {product_name}")
        return result
    
    combined_content = "\n\n".join(all_content_parts)
    
    # === PHASE 5: LLM Extraction ===
    extraction_prompt = f"""Extract verified product data from the following content about: {product_name}

{combined_content}

Extract ONLY facts explicitly present. NEVER invent data.
Return ONLY valid JSON with keys:
key_specs (list, max 10), real_pros (list, max 6), real_cons (list, max 6),
user_quotes (list of {{quote, source}}, max 5, VERBATIM only),
expert_verdict (str, 1 sentence), best_for (str), price_range (str),
target_audience (str)."""
    
    try:
        router = LLMRouter(task_type="default")
        raw = await router.generate_text(
            prompt=extraction_prompt,
            system_prompt="You are a strict data extraction engine. Return ONLY valid JSON.",
        )
        
        m = re.search(r"\{[\s\S]*\}", raw or "")
        if not m:
            logger.warning(f"LLM returned no JSON for {product_name}")
            return result
        
        data = json.loads(m.group())
        if not isinstance(data, dict):
            return result
        
        # Process quotes
        quotes = []
        for q in data.get("user_quotes", [])[:5]:
            if isinstance(q, dict) and q.get("quote"):
                quotes.append({
                    "quote": str(q["quote"])[:300],
                    "source": str(q.get("source", ""))[:80],
                })
        
        result.update({
            "key_specs": [str(x) for x in data.get("key_specs", []) if x][:10],
            "real_pros": [str(x) for x in data.get("real_pros", []) if x][:6],
            "real_cons": [str(x) for x in data.get("real_cons", []) if x][:6],
            "user_quotes": quotes,
            "expert_verdict": str(data.get("expert_verdict", "") or "")[:300],
            "best_for": str(data.get("best_for", "") or "")[:200],
            "price_range": str(data.get("price_range", "") or "")[:60],
            "target_audience": str(data.get("target_audience", "") or "")[:200],
        })
        
        result["found"] = bool(
            result["key_specs"] or result["real_pros"] or 
            result["real_cons"] or result["user_quotes"]
        )
        
        # Store sources
        result["sources"] = [p["url"] for p in crawled_pages] + youtube_urls
        
        logger.info(
            f"Deep dive (Level 2) {product_name}: "
            f"{len(crawled_pages)} pages + {len(youtube_urls)} YouTube, "
            f"{len(result['key_specs'])} specs, {len(result['real_pros'])} pros, "
            f"{len(result['real_cons'])} cons, {len(result['user_quotes'])} quotes, "
            f"price={result['price_range'] or 'n/a'}"
        )
        
    except Exception as e:
        logger.warning(f"Deep dive extraction failed for {product_name}: {e}")
    
    return result


async def product_deep_dive(products: List[Dict[str, Any]],
                            category: str = "") -> Dict[str, Dict[str, Any]]:
    if not deep_dive_enabled():
        logger.info("Product Deep Dive disabled via PRODUCT_DEEP_DIVE env")
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for p in products:
        name = p.get("name", "") if isinstance(p, dict) else str(p)
        if not name:
            continue
        try:
            out[name] = await deep_dive_product(name, category)
        except Exception as e:
            logger.warning("Deep dive crashed for %s: %s", name, e)
            failed = dict(_EMPTY)
            failed["product"] = name
            out[name] = failed
        await _safe_sleep(1.5)  # rate-limit breathing room
    return out
