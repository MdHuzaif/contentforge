from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import logger
from backend.tools.content_analyzer import count_words, readability_score


def extract_markdown_headings(content: str) -> Dict[str, List[str]]:
    """Parse lines starting with #, ##, ### (strip # and whitespace) and return {"h1": [...], "h2": [...], "h3": [...]}."""
    if not content:
        return {"h1": [], "h2": [], "h3": []}
    h1, h2, h3 = [], [], []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            h3.append(stripped[4:].strip())
        elif stripped.startswith("## "):
            h2.append(stripped[3:].strip())
        elif stripped.startswith("# "):
            h1.append(stripped[2:].strip())
    return {"h1": h1, "h2": h2, "h3": h3}


def extract_heading_sequence(content: str) -> List[Tuple[int, str]]:
    """Return list of (level, text) in document order for level 1-3 headings."""
    if not content:
        return []
    sequence = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            sequence.append((3, stripped[4:].strip()))
        elif stripped.startswith("## "):
            sequence.append((2, stripped[3:].strip()))
        elif stripped.startswith("# "):
            sequence.append((1, stripped[2:].strip()))
    return sequence


def keyword_density(content: str, keyword: str) -> Dict[str, Any]:
    """Calculate keyword density, placement, and score (0-20)."""
    if not content or not keyword:
        logger.warning("keyword_density called with empty content or keyword.")
        return {
            "occurrences": 0,
            "total_words": 0,
            "density_pct": 0.0,
            "in_first_100_words": False,
            "in_headings": 0,
            "status": "low",
            "score": 0,
        }
    c_lower = content.lower()
    k_lower = keyword.lower()
    occurrences = c_lower.count(k_lower)

    words_list = re.findall(r'\b\w+\b', content)
    total_words = len(words_list)

    if total_words == 0 or occurrences == 0:
        density_pct = 0.0
    else:
        kw_word_count = len(re.findall(r'\b\w+\b', keyword))
        density_pct = round((occurrences * kw_word_count) / total_words * 100, 2)

    first_100 = " ".join(words_list[:100]).lower()
    in_first_100 = k_lower in first_100

    headings = extract_markdown_headings(content)
    all_headings = headings["h1"] + headings["h2"] + headings["h3"]
    in_headings = sum(1 for h in all_headings if k_lower in h.lower())

    if occurrences == 0:
        status = "low"
        score = 0
    elif 0.5 <= density_pct <= 2.5:
        status = "optimal"
        score = 20
    elif density_pct < 0.5:
        status = "low"
        score = 10
    else:
        status = "high"
        score = 5

    return {
        "occurrences": occurrences,
        "total_words": total_words,
        "density_pct": density_pct,
        "in_first_100_words": in_first_100,
        "in_headings": in_headings,
        "status": status,
        "score": score,
    }


def analyze_title(title: str, keyword: str) -> Dict[str, Any]:
    """Analyze SEO title for length, keyword, proximity, numbers, and power words (score 0-15)."""
    if not title:
        logger.warning("analyze_title called with empty title.")
        return {
            "length_ok": False,
            "has_keyword": False,
            "keyword_near_start": False,
            "has_number": False,
            "has_power_word": False,
            "score": 0,
        }
    length_ok = 50 <= len(title) <= 60
    t_lower = title.lower()
    k_lower = keyword.lower() if keyword else ""
    has_keyword = bool(k_lower and k_lower in t_lower)

    title_words = re.findall(r'\b\w+\b', t_lower)
    first_5_words = " ".join(title_words[:5])
    keyword_near_start = bool(k_lower and (k_lower in first_5_words or any(w in title_words[:5] for w in k_lower.split())))

    has_number = bool(re.search(r'\d', title))
    power_words = ["best", "top", "guide", "how", "review", "vs", "cheap", "free", "tips", "ultimate"]
    has_power_word = bool(re.search(r'\b(' + '|'.join(power_words) + r')\b', title, re.IGNORECASE))

    score = 0
    if length_ok:
        score += 5
    if has_keyword:
        score += 4
    if keyword_near_start:
        score += 3
    if has_number:
        score += 1
    if has_power_word:
        score += 2

    return {
        "length_ok": length_ok,
        "has_keyword": has_keyword,
        "keyword_near_start": keyword_near_start,
        "has_number": has_number,
        "has_power_word": has_power_word,
        "score": score,
    }


def analyze_meta_description(description: str, keyword: str) -> Dict[str, Any]:
    """Analyze meta description for length and keyword (score 0-10)."""
    if not description:
        return {
            "length_ok": False,
            "has_keyword": False,
            "score": 0,
        }
    length_ok = 120 <= len(description) <= 160
    d_lower = description.lower()
    k_lower = keyword.lower() if keyword else ""
    has_keyword = bool(k_lower and k_lower in d_lower)

    score = 0
    if length_ok:
        score += 6
    if has_keyword:
        score += 4

    return {
        "length_ok": length_ok,
        "has_keyword": has_keyword,
        "score": score,
    }


def check_heading_hierarchy(headings: Dict[str, List[str]], sequence: List[Tuple[int, str]], keyword: str) -> Dict[str, Any]:
    """Check heading hierarchy (single H1, no skipped levels, keyword in H2) (score 0-15)."""
    h1_list = headings.get("h1", [])
    single_h1 = len(h1_list) == 1

    no_skipped_levels = True
    prev_level = None
    for level, _ in sequence:
        if prev_level is not None:
            if level > prev_level and (level - prev_level) > 1:
                no_skipped_levels = False
                break
        prev_level = level

    k_lower = keyword.lower() if keyword else ""
    keyword_in_h2 = bool(k_lower and any(k_lower in h2.lower() for h2 in headings.get("h2", [])))

    score = 0
    if single_h1:
        score += 6
    if no_skipped_levels:
        score += 5
    if keyword_in_h2:
        score += 4

    return {
        "single_h1": single_h1,
        "no_skipped_levels": no_skipped_levels,
        "keyword_in_h2": keyword_in_h2,
        "score": score,
    }


def readability_feedback(text: str) -> Dict[str, Any]:
    """Evaluate readability using Flesch Reading Ease score (score 0-15)."""
    if not text or not text.strip():
        return {
            "flesch_score": 0.0,
            "status": "hard",
            "score": 0,
        }
    s = readability_score(text)
    flesch_score = round(float(s), 2)

    if 60 <= flesch_score <= 80:
        status = "good"
        score = 15
    elif flesch_score > 80:
        status = "very_easy"
        score = 8
    else:
        status = "hard"
        score = 6

    return {
        "flesch_score": flesch_score,
        "status": status,
        "score": score,
    }


def content_length_check(word_count: int, competitor_metrics: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Check content length against competitor target (score 0-15)."""
    avg_wc = 0
    if competitor_metrics and isinstance(competitor_metrics, dict):
        avg_wc = competitor_metrics.get("avg_word_count", 0)
    
    # Target: 10% more than competitor, minimum 3000, maximum 4000
    if avg_wc > 0:
        target = int(avg_wc * 1.1)
        target = max(target, 3000)  # Minimum 3000
        target = min(target, 4000)  # Maximum 4000
    else:
        # Fallback: aim for 3500 (middle of 3000-4000 range)
        target = 3500
    
    if target == 0:
        ratio = 1.0 if word_count > 0 else 0.0
    else:
        ratio = word_count / target
    
    if word_count == 0:
        score = 0
    elif ratio >= 1.0:
        score = 15  # Exceeded target
    elif ratio >= 0.9:
        score = 12  # Within 10% of target
    elif ratio >= 0.8:
        score = 10
    elif ratio >= 0.6:
        score = 6
    else:
        score = 2
    
    return {
        "word_count": word_count,
        "target_word_count": target,
        "ratio": round(ratio, 2),
        "score": score,
    }


def engagement_check(content: str) -> Dict[str, Any]:
    """Check engagement elements (lists, tables, FAQ, links) (score 0-10)."""
    if not content:
        return {
            "has_lists": False,
            "has_table": False,
            "has_faq": False,
            "has_links": False,
            "score": 0,
        }
    lines = content.splitlines()
    has_lists = any(re.match(r'^\s*([-*]|\d+\.)\s', line) for line in lines)
    has_table = any("|" in line for line in lines)

    c_lower = content.lower()
    headings = extract_markdown_headings(content)
    all_headings = headings["h1"] + headings["h2"] + headings["h3"]
    has_faq = "faq" in c_lower or any(h.strip().endswith("?") for h in all_headings) or any(line.strip().endswith("?") for line in lines)
    has_links = bool(re.search(r'\[([^\]]+)\]\(([^)]+)\)', content))

    passed_count = sum(1 for v in [has_lists, has_table, has_faq, has_links] if v)
    score = int(round(passed_count * 2.5))
    score = max(0, min(10, score))

    return {
        "has_lists": has_lists,
        "has_table": has_table,
        "has_faq": has_faq,
        "has_links": has_links,
        "score": score,
    }


def internal_link_suggestions(primary_keyword: str, related_keywords: List[str], headings: Dict[str, List[str]]) -> List[str]:
    """Generate internal link suggestions for related keywords."""
    if not related_keywords:
        return []
    h2_list = headings.get("h2", []) if headings else []
    first_h2 = h2_list[0] if h2_list else "Introduction"

    suggestions = []
    for rkw in related_keywords[:5]:
        suggestions.append(f"Link anchor '{rkw}' from section '{first_h2}' to a supporting article")
    return suggestions


def compute_seo_report(
    content: str,
    title: str,
    meta_description: str,
    primary_keyword: str,
    related_keywords: List[str],
    competitor_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute comprehensive SEO report including scores, checks, improvements, and link suggestions."""
    if not content:
        content = ""
    if not title:
        h1_list = extract_markdown_headings(content).get("h1", [])
        title = h1_list[0] if h1_list else "Untitled"

    k_density = keyword_density(content, primary_keyword)
    t_analysis = analyze_title(title, primary_keyword)
    m_analysis = analyze_meta_description(meta_description, primary_keyword)
    headings = extract_markdown_headings(content)
    seq = extract_heading_sequence(content)
    h_hierarchy = check_heading_hierarchy(headings, seq, primary_keyword)
    r_feedback = readability_feedback(content)
    c_length = content_length_check(count_words(content), competitor_metrics)
    e_check = engagement_check(content)

    total_score = (
        k_density["score"] +
        t_analysis["score"] +
        m_analysis["score"] +
        h_hierarchy["score"] +
        r_feedback["score"] +
        c_length["score"] +
        e_check["score"]
    )
    seo_score = max(0, min(100, int(total_score)))

    improvements = []
    if not t_analysis["length_ok"]:
        improvements.append("Optimize title length to 50-60 characters")
    if not t_analysis["has_keyword"]:
        improvements.append("Add primary keyword to title")
    if not t_analysis["keyword_near_start"]:
        improvements.append("Place primary keyword near the start of the title")
    if not t_analysis["has_number"]:
        improvements.append("Include a number in the title")
    if not t_analysis["has_power_word"]:
        improvements.append("Add a power word (e.g., Best, Guide, Top) to the title")

    if not meta_description or not meta_description.strip():
        improvements.append("Meta description missing - write 120-160 chars including keyword")
    elif not m_analysis["length_ok"]:
        improvements.append("Optimize meta description length to 120-160 characters")
    if meta_description and meta_description.strip() and not m_analysis["has_keyword"]:
        improvements.append("Add primary keyword to meta description")

    if k_density["status"] == "low" and k_density["occurrences"] == 0:
        improvements.append("Add primary keyword to content")
    elif k_density["status"] == "low":
        improvements.append("Increase keyword density or usage")
    elif k_density["status"] == "high":
        improvements.append("Reduce keyword density (avoid keyword stuffing)")
    if not k_density["in_first_100_words"]:
        improvements.append("Add primary keyword to first 100 words")
    if k_density["in_headings"] == 0:
        improvements.append("Include primary keyword in at least one heading")

    if not h_hierarchy["single_h1"]:
        improvements.append("Ensure document has exactly one H1 heading")
    if not h_hierarchy["no_skipped_levels"]:
        improvements.append("Fix heading hierarchy (avoid skipping heading levels like H1 to H3)")
    if not h_hierarchy["keyword_in_h2"]:
        improvements.append("Include primary keyword in an H2 heading")

    if r_feedback["status"] == "hard":
        improvements.append("Improve content readability (aim for Flesch score 60-80)")
    elif r_feedback["status"] == "very_easy":
        improvements.append("Make content more substantive or professional")

    if c_length["score"] < 15:
        improvements.append("Increase content word count to meet or exceed target length")

    if not e_check["has_lists"] or not e_check["has_table"] or not e_check["has_faq"] or not e_check["has_links"]:
        if not e_check["has_table"] or not e_check["has_faq"]:
            improvements.append("Add a table or FAQ section for engagement")
        if not e_check["has_lists"]:
            improvements.append("Add bulleted or numbered lists for better engagement")
        if not e_check["has_links"]:
            improvements.append("Add markdown links to sources or references")

    link_sugs = internal_link_suggestions(primary_keyword, related_keywords, headings)

    checks = {
        "keyword_density": k_density,
        "title": t_analysis,
        "meta_description": m_analysis,
        "heading_hierarchy": h_hierarchy,
        "readability": r_feedback,
        "content_length": c_length,
        "engagement": e_check,
    }

    return {
        "seo_score": seo_score,
        "checks": checks,
        "improvements": improvements,
        "internal_link_suggestions": link_sugs,
    }
