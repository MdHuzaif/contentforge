from __future__ import annotations

import html
import re
import urllib.parse
import base64
import asyncio
from typing import Any, Dict, List, Optional

import httpx

from app.config import logger


def clean_html(text: str) -> str:
    """Strip HTML tags with regex and apply html.unescape."""
    if not text:
        return ""
    text = re.sub(r'(?is)<(script|style).*?>.*?</\1>', '', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _decode_ddg_url(href: str) -> str:
    """If href contains 'uddg=' extract and URL-decode the real target URL, else return href as-is."""
    if not href:
        return ""
    if "uddg=" in href:
        try:
            parsed = urllib.parse.urlparse(href)
            qs = urllib.parse.parse_qs(parsed.query)
            if "uddg" in qs:
                return qs["uddg"][0]
        except Exception:
            pass
    return href


def _decode_bing_redirect_url(bing_url: str) -> str:
    """Decode Bing's ck/a redirect URLs to extract actual destination."""
    try:
        if not bing_url or "bing.com/ck/a" not in bing_url:
            return bing_url
        
        parsed = urllib.parse.urlparse(bing_url)
        params = urllib.parse.parse_qs(parsed.query)
        
        if "u" not in params:
            return bing_url
        
        encoded_url = params["u"][0]
        if encoded_url.startswith("a1"):
            try:
                b64_content = encoded_url[2:]
                padded = b64_content + "=" * (-len(b64_content) % 4)
                decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
                if decoded.startswith("http"):
                    return decoded
            except Exception:
                pass
        return bing_url
    except Exception:
        return bing_url


async def search_duckduckgo(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Search DuckDuckGo HTML and return a list of result dicts."""
    results: List[Dict[str, str]] = []
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.post(url, data={"q": query}, headers=headers)
            response.raise_for_status()
            html_content = response.text

        a_matches = re.findall(
            r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html_content,
            re.DOTALL,
        )
        snippet_matches = re.findall(
            r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
            html_content,
            re.DOTALL,
        )
        if not snippet_matches:
            snippet_matches = re.findall(
                r'<div[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</div>',
                html_content,
                re.DOTALL,
            )
        if not snippet_matches:
            snippet_matches = re.findall(
                r'<td[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</td>',
                html_content,
                re.DOTALL,
            )

        for i, (href, title_html) in enumerate(a_matches):
            if len(results) >= max_results:
                break
            real_url = _decode_ddg_url(href)
            if real_url.startswith("//"):
                real_url = "https:" + real_url
            title = clean_html(title_html)
            snippet = ""
            if i < len(snippet_matches):
                snippet = clean_html(snippet_matches[i])

            if real_url and title:
                results.append({
                    "title": title,
                    "url": real_url,
                    "snippet": snippet,
                })
        logger.info("DuckDuckGo search for '%s' returned %d results", query, len(results))
    except Exception as e:
        logger.warning("DuckDuckGo search error for query '%s': %s", query, e)
    return results


async def search_ddg_lite(query: str, max_results: int = 6) -> List[Dict[str, str]]:
    """Search DuckDuckGo Lite - simpler HTML, less likely to be blocked."""
    url = "https://lite.duckduckgo.com/lite/"
    results: List[Dict[str, str]] = []
    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html",
            }
        ) as client:
            response = await client.post(url, data={"q": query, "kl": "us-en"})
            
            if response.status_code != 200:
                logger.warning(f"DDG Lite returned {response.status_code}")
                return []
            
            html_content = response.text
            link_matches = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html_content, re.DOTALL)
            
            for href, title_html in link_matches:
                if not href.startswith("http") or "duckduckgo.com" in href:
                    continue
                title = clean_html(title_html)
                if href and title and len(results) < max_results:
                    if not any(r["url"] == href for r in results):
                        results.append({
                            "url": href,
                            "title": title,
                            "snippet": title,
                            "source": "duckduckgo_lite"
                        })
            
            logger.info(f"DDG Lite search for '{query}' returned {len(results)} results")
            return results
    except Exception as e:
        logger.warning(f"DDG Lite search failed: {e}")
        return []


async def search_bing(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Search Bing and return a list of result dicts."""
    results: List[Dict[str, str]] = []
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.bing.com/search?q={encoded_query}"
    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
            }
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html_content = response.text

        algo_blocks = re.findall(
            r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>',
            html_content,
            re.DOTALL,
        )
        for block in algo_blocks:
            if len(results) >= max_results:
                break
            h2_match = re.search(
                r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?</h2>',
                block,
                re.DOTALL,
            )
            if not h2_match:
                h2_match = re.search(
                    r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                    block,
                    re.DOTALL,
                )

            if h2_match:
                raw_href = h2_match.group(1)
                if "bing.com/ck/a" in raw_href:
                    real_url = _decode_bing_redirect_url(raw_href)
                else:
                    real_url = raw_href

                if not real_url.startswith("http"):
                    continue
                if "bing.com" in real_url or "microsoft.com" in real_url:
                    continue

                title = clean_html(h2_match.group(2))
                p_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
                snippet = clean_html(p_match.group(1)) if p_match else ""

                if real_url and title:
                    results.append({
                        "title": title,
                        "url": real_url,
                        "snippet": snippet,
                    })
        logger.info("Bing search for '%s' returned %d results", query, len(results))
    except Exception as e:
        logger.warning("Bing search error for query '%s': %s", query, e)
    return results


async def _async_search_web(query: str, num_results: int = 10) -> list:
    # Try DuckDuckGo first (most reliable)
    try:
        results = await search_duckduckgo(query, num_results)
        if results:
            logger.info("✅ Search succeeded via DuckDuckGo: %d results", len(results))
            return results[:num_results]
        logger.debug("DuckDuckGo returned 0 results, trying Bing")
    except Exception as e:
        logger.warning("DuckDuckGo raised exception: %s — trying Bing", e)
    
    # Fallback to Bing
    try:
        results = await search_bing(query, num_results)
        if results:
            logger.info("✅ Search succeeded via Bing: %d results", len(results))
            return results[:num_results]
        logger.warning("Bing also returned 0 results")
    except Exception as e:
        logger.warning("Bing raised exception: %s", e)
    
    logger.error("❌ All search sources failed for: %s", query)
    return []


def search_web(query: str, num_results: int = 10) -> list:
    """Search using DuckDuckGo and Bing (proven reliable).
    
    Chain: DuckDuckGo → Bing (if DDG fails)
    """
    try:
        return asyncio.run(_async_search_web(query, num_results))
    except RuntimeError:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return asyncio.run_coroutine_threadsafe(_async_search_web(query, num_results), loop).result()
        except Exception:
            pass
        return []


async def get_top_results(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Try DuckDuckGo first; fall back to DDG Lite; fall back to Bing if empty; return trimmed results."""
    results = await search_duckduckgo(query, max_results=max_results)
    if not results:
        logger.info(f"DDG HTML failed, trying DDG Lite for '{query}'")
        results = await search_ddg_lite(query, max_results=max_results)

    if not results:
        logger.info(f"DDG Lite also failed, falling back to Bing for '{query}'")
        results = await search_bing(query, max_results=max_results)

    trimmed = results[:max_results]
    logger.info("get_top_results for '%s' found %d results total", query, len(trimmed))
    return trimmed
