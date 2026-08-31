from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.config import logger
from backend.tools.serp_scraper import clean_html


def extract_headings(html: str) -> Dict[str, List[str]]:
    """Extract text of all <h1>, <h2>, <h3> tags."""
    if not html:
        return {"h1": [], "h2": [], "h3": []}
    h1 = [clean_html(m) for m in re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)]
    h2 = [clean_html(m) for m in re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL | re.IGNORECASE)]
    h3 = [clean_html(m) for m in re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL | re.IGNORECASE)]
    return {
        "h1": [x for x in h1 if x],
        "h2": [x for x in h2 if x],
        "h3": [x for x in h3 if x],
    }


def extract_main_text(html: str) -> str:
    """Remove script, style, nav, footer, header blocks and all tags; return cleaned visible text."""
    if not html:
        return ""
    cleaned = re.sub(r'(?is)<(script|style|nav|footer|header).*?>.*?</\1>', ' ', html)
    return clean_html(cleaned)


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

    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
    title = clean_html(title_match.group(1)) if title_match else ""

    desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if not desc_match:
        desc_match = re.search(r'<meta[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\']', html, re.IGNORECASE)
    meta_desc = desc_match.group(1) if desc_match else ""

    has_meta_desc = bool(meta_desc.strip())
    has_schema = bool(re.search(r'application/ld\+json', html, re.IGNORECASE) or re.search(r'itemtype=', html, re.IGNORECASE))
    has_canonical = bool(re.search(r'<link[^>]*rel=["\']canonical["\']', html, re.IGNORECASE))

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

    headings = extract_headings(html)
    main_text = extract_main_text(html)
    w_count = count_words(main_text)

    h1_count = len(headings["h1"])
    h2_count = len(headings["h2"])
    h3_count = len(headings["h3"])

    image_count = len(re.findall(r'<img\b', html, re.IGNORECASE))
    all_links = re.findall(r'<a\b[^>]*href=["\']([^"\']*)["\']', html, re.IGNORECASE)
    total_links = len(all_links)

    parsed_base = urlparse(url)
    base_host = parsed_base.netloc.lower()

    external_links_count = 0
    for href in all_links:
        if href.startswith("http://") or href.startswith("https://"):
            p_href = urlparse(href)
            if p_href.netloc and p_href.netloc.lower() != base_host:
                external_links_count += 1
        elif href.startswith("//"):
            external_links_count += 1

    meta = get_meta_info(html)
    readability = readability_score(main_text)

    sentences_list = [s for s in re.split(r'[.!?]+', main_text) if s.strip()]
    num_sentences = len(sentences_list) if sentences_list else 1
    avg_sentence_length = round(w_count / num_sentences, 2)

    has_lists = bool(re.search(r'<(ul|ol)\b', html, re.IGNORECASE))
    has_table = bool(re.search(r'<table\b', html, re.IGNORECASE))
    has_video_embed = bool(re.search(r'<iframe\b', html, re.IGNORECASE) or re.search(r'youtube\.com|vimeo\.com', html, re.IGNORECASE))
    has_faq = bool(re.search(r'<details\b', html, re.IGNORECASE) or re.search(r'faq', html, re.IGNORECASE))
    has_toc = bool(re.search(r'table of contents', html, re.IGNORECASE) or re.search(r'<nav\b[^>]*>.*?#', html, re.IGNORECASE))

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


async def fetch_and_analyze(url: str) -> Optional[Dict[str, Any]]:
    """Fetch URL via HTTPX and return analysis dict or None on exception."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html_content = response.text
        return analyze_html(html_content, url=url)
    except Exception as e:
        logger.warning("Failed to fetch and analyze URL '%s': %s", url, e)
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
