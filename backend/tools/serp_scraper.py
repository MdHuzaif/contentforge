from __future__ import annotations

import html
import re
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

from app.config import logger


def clean_html(text: str) -> str:
    """Strip HTML tags with regex and apply html.unescape."""
    if not text:
        return ""
    # Remove script and style elements first
    text = re.sub(r'(?is)<(script|style).*?>.*?</\1>', '', text)
    # Remove all HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Unescape HTML entities
    text = html.unescape(text)
    # Collapse whitespace
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


async def search_bing(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Search Bing and return a list of result dicts."""
    results: List[Dict[str, str]] = []
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.bing.com/search?q={encoded_query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
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
                href = h2_match.group(1)
                title = clean_html(h2_match.group(2))

                p_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
                snippet = clean_html(p_match.group(1)) if p_match else ""

                if href and title:
                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": snippet,
                    })
        logger.info("Bing search for '%s' returned %d results", query, len(results))
    except Exception as e:
        logger.warning("Bing search error for query '%s': %s", query, e)
    return results


async def get_top_results(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Try DuckDuckGo first; fall back to Bing if empty; return trimmed results."""
    results = await search_duckduckgo(query, max_results=max_results)
    if not results:
        logger.info("DuckDuckGo returned no results for '%s', falling back to Bing...", query)
        results = await search_bing(query, max_results=max_results)

    trimmed = results[:max_results]
    logger.info("get_top_results for '%s' found %d results total", query, len(trimmed))
    return trimmed