"""Manage the Uniscolian post sitemap, unique slugs, and slug->title registry."""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from app.config import logger, UNISCOLIAN_ROOT, SITE_BASE_URL, POST_REGISTRY_PATH

SITEMAP_CANDIDATES = ["post-sitemap.xml", "post_sitemap.xml", "sitemap-posts.xml"]

SITEMAP_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<?xml-stylesheet type="text/xsl" href="./main-sitemap.xsl"?>\n'
    '<urlset xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1" '
    'xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9 '
    'http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd '
    'http://www.google.com/schemas/sitemap-image/1.1 '
    'http://www.google.com/schemas/sitemap-image/1.1/sitemap-image.xsd" '
    'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
)


def find_sitemap(root: Path = UNISCOLIAN_ROOT) -> Optional[Path]:
    for name in SITEMAP_CANDIDATES:
        p = root / name
        if p.exists():
            return p
    hits = sorted(root.glob("*post*sitemap*.xml"))
    return hits[0] if hits else None


def _slug_from_loc(loc: str) -> str:
    """'./best-gaming-laptops/' or 'https://x.com/best-gaming-laptops/' -> 'best-gaming-laptops'; './' -> ''."""
    loc = loc.strip()
    loc = re.sub(r'^https?://[^/]+', '', loc)
    if loc.startswith("./"):
        loc = loc[2:]
    loc = loc.strip("/")
    return loc.split("/")[0] if loc else ""


def parse_sitemap(path: Path) -> List[str]:
    xml = path.read_text(encoding="utf-8", errors="ignore")
    return [s for s in (_slug_from_loc(m) for m in re.findall(r"<loc>([^<]+)</loc>", xml)) if s]


def detect_loc_style(path: Path) -> str:
    xml = path.read_text(encoding="utf-8", errors="ignore")
    for loc in (l.strip() for l in re.findall(r"<loc>([^<]+)</loc>", xml)):
        if loc in ("./", "/"):
            continue
        if loc.startswith("http"):
            return "absolute"
        return "relative"
    return "relative"


def existing_slugs(root: Path = UNISCOLIAN_ROOT) -> Set[str]:
    """Taken slugs = sitemap slugs + on-disk post folders (union)."""
    slugs: Set[str] = set()
    sm = find_sitemap(root)
    if sm:
        slugs.update(parse_sitemap(sm))
    for d in root.glob("*/index.html"):
        name = d.parent.name
        if name in ("_template", "blog") or name.startswith("wp-"):
            continue
        slugs.add(name)
    return slugs


def ensure_unique_slug(base_slug: str, taken: Set[str]) -> str:
    """base_slug if free, else base_slug-2, base_slug-3, ... until unique."""
    if base_slug not in taken:
        return base_slug
    n = 2
    while f"{base_slug}-{n}" in taken:
        n += 1
    final = f"{base_slug}-{n}"
    logger.info("Slug collision detected: '%s' taken -> using '%s'", base_slug, final)
    return final


def _extract_title(html: str) -> str:
    m = re.search(r'<h1 class="page-title"[^>]*>(.*?)</h1>', html, re.S)
    return re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else ""


def build_registry(root: Path = UNISCOLIAN_ROOT, force: bool = False) -> Dict[str, str]:
    if POST_REGISTRY_PATH.exists() and not force:
        try:
            return json.loads(POST_REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Static pages that should NOT be in the blog registry
    STATIC_PAGE_SLUGS = {
        "about-us", "about", "contact", "privacy-policy", "terms-and-conditions",
        "terms", "disclaimer", "affiliate-disclosure", "service", "sitemap",
        "home", "blog", "shop", "cart", "checkout", "my-account",
    }
    
    registry: Dict[str, str] = {}
    for slug in sorted(existing_slugs(root)):
        if slug.lower() in STATIC_PAGE_SLUGS:
            continue  # Skip static pages
        f = root / slug / "index.html"
        if f.exists():
            title = _extract_title(f.read_text(encoding="utf-8", errors="ignore")[:300_000])
            if title:
                registry[slug] = title
    POST_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    POST_REGISTRY_PATH.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Post registry built: %d posts", len(registry))
    return registry


def add_to_sitemap(root: Path, slug: str, lastmod: Optional[str] = None) -> bool:
    """Add <url><loc>./{slug}/</loc>... entry (relative style). Idempotent."""
    lastmod = lastmod or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    sm = find_sitemap(root)
    if sm is None:
        xml = (SITEMAP_HEADER
               + f"<url>\n<loc>./</loc>\n<lastmod>{lastmod}</lastmod>\n</url>\n"
               + f"<url>\n<loc>./{slug}/</loc>\n<lastmod>{lastmod}</lastmod>\n</url>\n"
               + "</urlset>\n")
        (root / "post-sitemap.xml").write_text(xml, encoding="utf-8")
        logger.info("Created post-sitemap.xml with %s", slug)
        return True

    if slug in parse_sitemap(sm):
        return False  # already listed -> idempotent

    style = detect_loc_style(sm)
    loc = f"./{slug}/" if style == "relative" else f"{SITE_BASE_URL.rstrip('/')}/{slug}/"
    entry = f"<url>\n<loc>{loc}</loc>\n<lastmod>{lastmod}</lastmod>\n</url>"
    xml = sm.read_text(encoding="utf-8")
    xml = xml.replace("</urlset>", f"{entry}\n</urlset>")
    sm.write_text(xml, encoding="utf-8")

    try:  # optional: bump lastmod in sitemap_index.xml
        idx = root / "sitemap_index.xml"
        if idx.exists():
            ix = idx.read_text(encoding="utf-8")
            ix = re.sub(r"(<loc>[^<]*post[-_]sitemap\.xml</loc>\s*<lastmod>)[^<]*(</lastmod>)",
                        rf"\g<1>{lastmod}\g<2>", ix, count=1)
            idx.write_text(ix, encoding="utf-8")
    except Exception as e:
        logger.warning("sitemap_index lastmod update skipped: %s", e)

    logger.info("Sitemap updated: %s", slug)
    return True
