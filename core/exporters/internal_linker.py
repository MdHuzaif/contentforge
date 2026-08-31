"""Pick related old posts from the registry and inject site-native 'Related Article' links at distributed positions."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Tuple

from app.config import logger, RELATED_LINKS_COUNT

STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with", "at", "by",
    "from", "is", "are", "be", "was", "were", "been", "being", "it", "its", "this",
    "that", "these", "those", "you", "your", "we", "our", "my", "me", "i", "as",
    "but", "not", "no", "if", "so", "do", "does", "did", "has", "have", "had",
    "will", "would", "can", "could", "should", "may", "might", "must", "shall",
    "best", "top", "vs", "versus", "how", "what", "why", "when", "where", "which",
    "who", "whom", "all", "any", "some", "each", "every", "both", "few", "more",
    "most", "other", "such", "only", "own", "same", "than", "too", "very", "just",
    "because", "about", "into", "through", "during", "before", "after", "above",
    "below", "up", "down", "out", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "guide", "review", "reviews", "complete",
    "ultimate", "comprehensive", "essential", "new", "latest", "update", "updated",
}


def tokenize(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def pick_related(
    registry: Dict[str, str],
    current_slug: str,
    title: str,
    keywords: List[str],
    n: int = RELATED_LINKS_COUNT,
) -> List[Tuple[str, str]]:
    """Pick top-n most relevant old posts by keyword-overlap, excluding current post variants."""
    if not registry:
        return []
    my_tokens = tokenize(title + " " + " ".join(keywords or []))
    if not my_tokens:
        my_tokens = tokenize(title)

    # BUG 1 FIX: Extract base slug (remove -2, -3, etc. suffix) to avoid self-linking
    base_slug = re.sub(r'-\d+$', '', current_slug)

    scored = []
    for slug, t in registry.items():
        # Skip current post AND all its variants (topic, topic-2, topic-3...)
        if slug == current_slug or slug.startswith(base_slug + "-") or slug == base_slug:
            continue
        overlap = len(my_tokens & tokenize(t))
        scored.append((overlap, slug, t))
    scored.sort(key=lambda x: (-x[0], x[1]))

    picks = [(s, t) for _, s, t in scored[:n]]

    # Fallback: pad with other posts (NOT current or its variants)
    seen = {s for s, _ in picks}
    for slug, t in registry.items():
        if slug == current_slug or slug.startswith(base_slug + "-") or slug == base_slug or slug in seen:
            continue
        picks.append((slug, t))
        seen.add(slug)
        if len(picks) >= n:
            break

    # BUG 3 FIX: Ensure we never return more than n items
    return picks[:n]


def related_link_html(slug: str, title: str) -> str:
    """Build a single 'Related Article:' line matching the site's native style."""
    return (
        f'<p>Related Article: <a href="./../{slug}/index.html" '
        f'target="_blank" rel="noreferrer noopener"><strong>{title}</strong></a></p>'
    )


def insert_related_links(body_html: str, picks: List[Tuple[str, str]]) -> str:
    """DISTRIBUTE related links across the article at 1/3 and 2/3 positions of H2 headings.
    
    Each link is inserted BEFORE a different H2, so readers encounter them naturally
    at different points while reading, instead of seeing them all clustered together.
    """
    if not picks:
        return body_html
    
    h2_matches = list(re.finditer(r"<h2\b", body_html))
    
    # If fewer than 2 H2s, append all at the end (fallback)
    if len(h2_matches) < 2:
        block = "\n".join(related_link_html(s, t) for s, t in picks)
        return body_html + "\n" + block
    
    # Calculate distributed insertion positions
    # For n picks: place them at positions that divide the H2s into (n+1) equal parts
    # E.g., 2 picks with 6 H2s -> positions at H2 index 2 (1/3) and 4 (2/3)
    positions = []
    for i in range(len(picks)):
        # Distribute evenly: position = (i+1) * total_h2s / (num_picks + 1)
        idx = int(len(h2_matches) * (i + 1) / (len(picks) + 1))
        # Clamp to safe range: never insert before first H2 or after last H2
        idx = max(1, min(idx, len(h2_matches) - 1))
        positions.append(idx)
    
    # Deduplicate positions (if very few H2s, positions might collide)
    # Shift colliding positions forward
    seen_pos = set()
    for i in range(len(positions)):
        while positions[i] in seen_pos and positions[i] < len(h2_matches) - 1:
            positions[i] += 1
        seen_pos.add(positions[i])
    
    # Insert from LAST to FIRST so earlier indices stay valid
    for i in reversed(range(len(picks))):
        slug, title = picks[i]
        h2_idx = positions[i]
        at = h2_matches[h2_idx].start()
        block = related_link_html(slug, title) + "\n"
        body_html = body_html[:at] + block + body_html[at:]
    
    return body_html
