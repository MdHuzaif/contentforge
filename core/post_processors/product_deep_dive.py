"""Product Deep Dive: multi-source verified product data (Phase 1.5).

Crawls up to 4 pages per selected product, cross-checks facts across
sources, extracts specs/pros/cons/user-quotes/verdict with a strict
anti-hallucination LLM pass, and feeds it into H3 sub-prompts so reviews
are accurate (trust) and quote-rich (engagement).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from typing import Any, Dict, List

from app.config import logger
from backend.llm.router import LLMRouter
from backend.tools.content_analyzer import fetch_main_text
from backend.tools.web_search import get_top_results

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


async def _search_product(product_name: str, kind: str) -> List[Dict[str, str]]:
    query = (f"{product_name} specifications review" if kind == "specs"
             else f"{product_name} real user review pros cons")
    try:
        import core.post_processors.product_deep_dive as pdd_mod
        search_fn = getattr(pdd_mod, "get_top_results", get_top_results)
        return await search_fn(query, max_results=4)
    except Exception as e:
        logger.warning("Deep dive search failed for %s (%s): %s",
                       product_name, kind, e)
        return []


async def _crawl_multi_text(urls: List[str]) -> List[Dict[str, str]]:
    """Crawl up to _max_pages() URLs; skip thin/failed pages; keep order."""
    pages: List[Dict[str, str]] = []
    seen = set()
    import core.post_processors.product_deep_dive as pdd_mod
    fetch_fn = getattr(pdd_mod, "fetch_main_text", fetch_main_text)
    for url in urls:
        if len(pages) >= _max_pages() or url in seen:
            continue
        seen.add(url)
        try:
            text = await fetch_fn(url)
            if text and len(text) > 50:
                pages.append({"url": url, "text": text[:_PAGE_CHARS]})
        except Exception as e:
            logger.warning("Deep dive crawl failed for %s: %s", url, e)
    return pages


async def _extract_with_llm(product_name: str,
                            pages: List[Dict[str, str]],
                            snippets: List[str]) -> Dict[str, Any]:
    src_blocks = "\n\n".join(
        f"SOURCE {i + 1} ({p['url']}):\n{p['text']}"
        for i, p in enumerate(pages)
    ) or "(no pages crawled)"
    user = (f"Product: {product_name}\n\n{src_blocks}\n\n"
            f"SEARCH SNIPPETS:\n" +
            "\n".join(f"- {s}" for s in snippets[:8]) +
            "\n\nExtract verified data as JSON.")
    try:
        import core.post_processors.product_deep_dive as pdd_mod
        router_cls = getattr(pdd_mod, "LLMRouter", LLMRouter)
        router = router_cls(task_type="default")
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
    result = dict(_EMPTY)
    result["product"] = product_name
    specs_res = await _search_product(product_name, "specs")
    pros_res = await _search_product(product_name, "proscons")
    all_res = specs_res + pros_res
    urls = [r["url"] for r in all_res if r.get("url")]
    snippets = [r.get("snippet") or r.get("content") or ""
                for r in all_res if r.get("snippet") or r.get("content")]
    snippets = [s for s in snippets if s]
    if not urls and not snippets:
        logger.warning("Deep dive: no search results for %s", product_name)
        return result
    pages = await _crawl_multi_text(urls)
    extracted = await _extract_with_llm(product_name, pages, snippets)
    if not extracted:
        logger.warning("Deep dive: extraction empty for %s", product_name)
        return result
    result.update(extracted)
    result["found"] = bool(extracted.get("key_specs") or
                           extracted.get("real_pros") or
                           extracted.get("real_cons") or
                           extracted.get("user_quotes"))
    result["sources"] = [p["url"] for p in pages] or urls[:3]
    logger.info("🔍 Deep dive %s: %d pages, %d specs, %d pros, %d cons, "
                "%d quotes, price=%s", product_name, len(pages),
                len(result["key_specs"]), len(result["real_pros"]),
                len(result["real_cons"]), len(result["user_quotes"]),
                result["price_range"] or "n/a")
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
