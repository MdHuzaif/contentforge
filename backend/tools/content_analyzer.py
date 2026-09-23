from __future__ import annotations

import html
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.config import logger
from backend.tools.serp_scraper import clean_html


_PARSER: Optional[str] = None


def _get_parser() -> str:
    global _PARSER
    if _PARSER is None:
        try:
            import lxml  # noqa: F401
            _PARSER = "lxml"
        except Exception:
            _PARSER = "html.parser"
    return _PARSER


def _soup(html_content: str):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html_content or "", _get_parser())


_NOISE = ["script", "style", "noscript", "template", "svg", "form", "button"]
_CHROME = ["nav", "footer", "aside", "header"]


def _main_node(soup):
    """Locate main article content container."""
    import re as _re
    for tag, attrs in [
        ("article", {}),
        ("main", {}),
        ("div", {"id": _re.compile(r"(content|main|article|post)", _re.I)}),
        ("div", {"class": _re.compile(r"(entry-content|post-content|article-body|content-body)", _re.I)}),
    ]:
        node = soup.find(tag, attrs)
        if node:
            return node
    return soup.body or soup


def extract_headings(html: str) -> Dict[str, List[str]]:
    """Extract text of all <h1>, <h2>, <h3> tags, ignoring nav/footer/aside/header."""
    if not html:
        return {"h1": [], "h2": [], "h3": []}
    soup = _soup(html)
    result: Dict[str, List[str]] = {"h1": [], "h2": [], "h3": []}
    for tag in soup.find_all(re.compile(r"^h[1-6]$", re.I)):
        if tag.find_parent(_CHROME):
            continue
        text = tag.get_text(" ", strip=True)
        if text:
            name = tag.name.lower()
            if name in result:
                result[name].append(text)
    return result


def extract_main_text(html: str) -> str:
    """Remove script, style, nav, footer, header blocks and all tags; return cleaned visible text."""
    if not html:
        return ""
    soup = _soup(html)
    node = _main_node(soup)
    for t in node.find_all(_NOISE + _CHROME):
        t.decompose()
    return node.get_text(" ", strip=True)


def count_words(text: str) -> int:
    """Count words in text."""
    if not text:
        return 0
    words = re.findall(r'\b\w+\b', text)
    return len(words)


def readability_score(text: str) -> float:
    """Simplified Flesch Reading Ease score calculation."""
    if not text:
        return 0.0
    words_list = re.findall(r'\b\w+\b', text)
    words = len(words_list)
    if words == 0:
        return 0.0

    sentences_list = [s for s in re.split(r'[.!?]+', text) if s.strip()]
    sentences = len(sentences_list)
    if sentences == 0:
        sentences = 1

    syllables = 0
    for word in words_list:
        groups = re.findall(r'[aeiouy]+', word.lower())
        syl = len(groups)
        if word.lower().endswith('e') and syl > 1:
            syl -= 1
        syllables += max(1, syl)

    score = 206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)
    return round(float(score), 2)


def get_meta_info(html: str) -> Dict[str, Any]:
    """Extract title, meta description, schema/json-ld presence, and canonical link presence."""
    if not html:
        return {
            "title": "",
            "meta_description": "",
            "has_meta_description": False,
            "has_schema": False,
            "has_canonical": False,
        }

    soup = _soup(html)
    title_tag = soup.find("title")
    title = title_tag.get_text(" ", strip=True) if title_tag else ""

    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)}) or \
               soup.find("meta", attrs={"property": re.compile(r"^description$", re.I)}) or \
               soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
    if meta_tag and meta_tag.get("content"):
        meta_desc = meta_tag["content"].strip()

    has_meta_desc = bool(meta_desc)
    has_schema = bool(soup.find("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}) or soup.find(attrs={"itemtype": True}))
    has_canonical = bool(soup.find("link", attrs={"rel": re.compile(r"canonical", re.I)}))

    return {
        "title": title,
        "meta_description": meta_desc,
        "has_meta_description": has_meta_desc,
        "has_schema": has_schema,
        "has_canonical": has_canonical,
    }


def analyze_html(html: str, url: str = "") -> Dict[str, Any]:
    """Analyze raw HTML of competitor pages and return structured metrics and signals."""
    if not html:
        html = ""

    soup = _soup(html)
    main = _main_node(soup)
    for t in main.find_all(_NOISE + _CHROME):
        t.decompose()

    main_text = main.get_text(" ", strip=True)
    w_count = count_words(main_text)

    headings = extract_headings(html)

    h1_count = len(headings["h1"])
    h2_count = len(headings["h2"])
    h3_count = len(headings["h3"])

    image_count = len(soup.find_all("img"))
    links = soup.find_all("a", href=True)
    total_links = len(links)

    parsed_base = urlparse(url) if url else urlparse("")
    base_host = parsed_base.netloc.lower() if parsed_base else ""

    external_links_count = 0
    for a in links:
        href = a["href"]
        if href.startswith("http://") or href.startswith("https://"):
            p_href = urlparse(href)
            if base_host and p_href.netloc and p_href.netloc.lower() != base_host:
                external_links_count += 1
            elif not base_host:
                external_links_count += 1
        elif href.startswith("//"):
            external_links_count += 1

    meta = get_meta_info(html)
    readability = readability_score(main_text)

    sentences_list = [s for s in re.split(r'[.!?]+', main_text) if s.strip()]
    num_sentences = len(sentences_list) if sentences_list else 1
    avg_sentence_length = round(w_count / num_sentences, 2)

    has_lists = bool(main.find(["ul", "ol"]))
    has_table = bool(main.find("table"))
    has_video_embed = bool(soup.find("iframe", src=re.compile(r"(youtube|vimeo|dailymotion)", re.I))) or \
                      bool(soup.find("div", class_=re.compile("video", re.I))) or \
                      bool(soup.find("video"))

    has_schema_FAQPage = False
    for s in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        try:
            content = s.get_text()
            if content and ("FAQPage" in content or "faq" in content.lower()):
                has_schema_FAQPage = True
                break
        except Exception:
            pass
    if not has_schema_FAQPage:
        for el in soup.find_all(attrs={"itemtype": re.compile(r"FAQPage", re.I)}):
            has_schema_FAQPage = True
            break

    has_faq = has_schema_FAQPage or bool(main.find("details")) or any("faq" in h.lower() for h in headings.get("h2", [])) or any("faq" in h.lower() for h in headings.get("h3", []))
    has_toc = bool(soup.find(id=re.compile(r"toc|table-of-contents|contents", re.I))) or any("table of contents" in h.lower() for h in headings.get("h2", []))

    engagement_signals = {
        "has_lists": has_lists,
        "has_table": has_table,
        "has_video_embed": has_video_embed,
        "has_faq": has_faq,
        "has_toc": has_toc,
    }

    return {
        "url": url,
        "word_count": w_count,
        "h1_count": h1_count,
        "h2_count": h2_count,
        "h3_count": h3_count,
        "headings": headings,
        "image_count": image_count,
        "total_links": total_links,
        "external_links_count": external_links_count,
        "meta": meta,
        "readability": readability,
        "avg_sentence_length": avg_sentence_length,
        "engagement_signals": engagement_signals,
    }


async def _httpx_fetch(url: str, timeout: float = 15.0) -> Optional[str]:
    """Lightweight HTTP fetch (Layer 1, free)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text
    except Exception as e:
        logger.warning("httpx fetch failed for %s: %s", url, e)
        return None


_FIRECRAWL_TIMEOUT = 45.0


def _firecrawl_enabled() -> bool:
    return bool(os.environ.get("FIRECRAWL_API_KEY", "").strip())


def _firecrawl_endpoints() -> List[str]:
    """v2 first, v1 fallback; env override possible."""
    custom = os.environ.get("FIRECRAWL_API_URL", "").strip()
    if custom:
        return [custom.rstrip("/")]
    return ["https://api.firecrawl.dev/v2/scrape",
            "https://api.firecrawl.dev/v1/scrape"]


def _is_info_rich(info: Dict[str, Any]) -> bool:
    """True when parsed page has real article content (not a JS shell)."""
    return bool(info) and (
        info.get("word_count", 0) >= 200 or info.get("h2_count", 0) >= 2
    )


async def _firecrawl_fetch(url: str) -> Optional[str]:
    """Rescue fetch via Firecrawl browser rendering (1 credit per success)."""
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not key:
        return None
    body = {"url": url, "formats": ["html"], "onlyMainContent": True}
    headers = {"Authorization": f"Bearer {key}",
               "Content-Type": "application/json"}
    endpoints = _firecrawl_endpoints()
    for i, endpoint in enumerate(endpoints):
        try:
            async with httpx.AsyncClient(timeout=_FIRECRAWL_TIMEOUT) as client:
                r = await client.post(endpoint, headers=headers, json=body)
                if r.status_code in (404, 410) and i < len(endpoints) - 1:
                    logger.debug("Firecrawl %s deprecated, trying next", endpoint)
                    continue
                r.raise_for_status()
                data = (r.json() or {}).get("data") or {}
                html = data.get("html") or ""
                if len(html) > 200:
                    return html
                logger.warning("Firecrawl returned thin html for %s", url)
                return None
        except Exception as e:
            logger.warning("Firecrawl fetch failed via %s for %s: %s",
                           endpoint, url, e)
            continue
    return None


async def fetch_main_text(url: str) -> Optional[str]:
    """Fetch page (httpx -> firecrawl rescue) and return cleaned main text."""
    html = await _httpx_fetch(url)
    if not html and _firecrawl_enabled():
        html = await _firecrawl_fetch(url)
    if not html:
        return None
    return extract_main_text(html)


async def fetch_and_analyze(url: str) -> Optional[Dict[str, Any]]:
    """Fetch chain: httpx (free) -> Firecrawl rescue (credits) -> None."""
    html = await _httpx_fetch(url)
    if html:
        info = analyze_html(html, url=url)
        # Without firecrawl key: keep EXACT old behavior (accept any page)
        if _is_info_rich(info) or not _firecrawl_enabled():
            return info
    if _firecrawl_enabled():
        fc = await _firecrawl_fetch(url)
        if fc:
            logger.info("Fetched %s via firecrawl (httpx blocked/empty)", url)
            return analyze_html(fc, url=url)
    logger.warning("All fetch layers failed for %s", url)
    return None


def aggregate_metrics(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute average metrics and coverage percentages across multiple competitor analyses."""
    if not analyses:
        return {
            "competitor_count": 0,
            "avg_word_count": 0.0,
            "avg_h2_count": 0.0,
            "avg_h3_count": 0.0,
            "avg_image_count": 0.0,
            "avg_readability": 0.0,
            "pct_with_meta_description": 0.0,
            "pct_with_schema": 0.0,
            "pct_with_lists": 0.0,
            "pct_with_table": 0.0,
            "pct_with_video": 0.0,
        }

    count = len(analyses)
    total_words = sum(a.get("word_count", 0) for a in analyses)
    total_h2 = sum(a.get("h2_count", 0) for a in analyses)
    total_h3 = sum(a.get("h3_count", 0) for a in analyses)
    total_images = sum(a.get("image_count", 0) for a in analyses)
    total_readability = sum(a.get("readability", 0.0) for a in analyses)

    with_meta_desc = sum(1 for a in analyses if a.get("meta", {}).get("has_meta_description"))
    with_schema = sum(1 for a in analyses if a.get("meta", {}).get("has_schema"))
    with_lists = sum(1 for a in analyses if a.get("engagement_signals", {}).get("has_lists"))
    with_table = sum(1 for a in analyses if a.get("engagement_signals", {}).get("has_table"))
    with_video = sum(1 for a in analyses if a.get("engagement_signals", {}).get("has_video_embed"))

    return {
        "competitor_count": count,
        "avg_word_count": round(total_words / count, 2),
        "avg_h2_count": round(total_h2 / count, 2),
        "avg_h3_count": round(total_h3 / count, 2),
        "avg_image_count": round(total_images / count, 2),
        "avg_readability": round(total_readability / count, 2),
        "pct_with_meta_description": round((with_meta_desc / count) * 100, 2),
        "pct_with_schema": round((with_schema / count) * 100, 2),
        "pct_with_lists": round((with_lists / count) * 100, 2),
        "pct_with_table": round((with_table / count) * 100, 2),
        "pct_with_video": round((with_video / count) * 100, 2),
    }


# Alias for step 2 integration
fetch_and_analyze_url = fetch_and_analyze
