"""Pick related posts for sidebar widgets and inject them into Uniscolian exported posts."""
from __future__ import annotations
import html
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import logger, UNISCOLIAN_ROOT
from core.exporters.internal_linker import pick_related, tokenize
from core.exporters.sitemap_manager import build_registry


def pick_sidebar_related(
    registry: Dict[str, str],
    current_slug: str,
    title: str,
    keywords: List[str],
    n: int = 5,
) -> List[Tuple[str, str]]:
    """Pick top-n sidebar related posts, excluding current post and title variants."""
    if not registry:
        return []
    try:
        raw_picks = pick_related(registry, current_slug, title, keywords, n=max(n * 2, 10))
    except Exception:
        raw_picks = []

    lower_title = title.strip().lower()
    base_slug = re.sub(r'-\d+$', '', current_slug)

    filtered = []
    for slug, t in raw_picks:
        if slug == current_slug or slug == base_slug or slug.startswith(base_slug + "-"):
            continue
        if t.strip().lower() == lower_title:
            continue
        filtered.append((slug, t))
        if len(filtered) >= n:
            break

    # If fewer than n entries remain, pad from registry
    if len(filtered) < n:
        seen = {s for s, _ in filtered}
        for slug, t in registry.items():
            if slug == current_slug or slug == base_slug or slug.startswith(base_slug + "-"):
                continue
            if t.strip().lower() == lower_title:
                continue
            if slug in seen:
                continue
            filtered.append((slug, t))
            seen.add(slug)
            if len(filtered) >= n:
                break

    return filtered[:n]


def extract_featured_image(post_html: str) -> Optional[str]:
    """Extract featured image path from post HTML using og:image, twitter:image, or figure img."""
    if not post_html:
        return None
    try:
        # 1. og:image
        m = re.search(r'<meta\s+property=[\'"]og:image[\'"]\s+content=[\'"]([^\'"]+)[\'"]', post_html, re.I)
        if not m:
            m = re.search(r'<meta\s+content=[\'"]([^\'"]+)[\'"]\s+property=[\'"]og:image[\'"]', post_html, re.I)
        # 2. twitter:image
        if not m:
            m = re.search(r'<meta\s+name=[\'"]twitter:image[\'"]\s+content=[\'"]([^\'"]+)[\'"]', post_html, re.I)
        # 3. figure img src
        if not m:
            m = re.search(r'<figure[^>]*>.*?<img[^>]*src=[\'"]([^\'"]+)[\'"]', post_html, re.S | re.I)
        # 4. any img with wp-post-image
        if not m:
            m = re.search(r'<img[^>]*class=[\'"][^\'"]*wp-post-image[^\'"]*[\'"][^>]*src=[\'"]([^\'"]+)[\'"]', post_html, re.I)
        # 5. first img src
        if not m:
            m = re.search(r'<img[^>]*src=[\'"]([^\'"]+)[\'"]', post_html, re.I)

        if m:
            url = m.group(1).strip()
            # Normalize leading ./../, ./, //, etc.
            url = re.sub(r'^(?:\.\/)+', '', url)
            url = re.sub(r'^(?:\.\.\/)+', '', url)
            url = re.sub(r'^//', '', url)
            if "wp-content/" in url:
                idx = url.find("wp-content/")
                url = url[idx:]
            return url
    except Exception:
        pass
    return None


def build_sidebar_widget_html(picks: List[dict | tuple]) -> str:
    """Build self-contained Related Posts sidebar widget HTML with scoped CSS."""
    if not picks:
        return ""

    items_html = []
    for pick in picks:
        if isinstance(pick, dict):
            slug = pick.get("slug", "")
            p_title = pick.get("title", "")
            img_rel = pick.get("img_rel") or pick.get("img_rel_or_None")
        else:
            slug = pick[0] if len(pick) > 0 else ""
            p_title = pick[1] if len(pick) > 1 else ""
            img_rel = pick[2] if len(pick) > 2 else None

        escaped_title = html.escape(p_title)

        if img_rel:
            thumb_html = f'<img class="cf-sr-thumb" src="./../{img_rel}" alt="{escaped_title}" loading="lazy">'
        else:
            thumb_html = '<div class="cf-sr-thumb cf-sr-placeholder"></div>'

        item_html = f"""      <a class="cf-sr-item" href="./../{slug}/index.html">
        {thumb_html}
        <span class="cf-sr-title">{escaped_title}</span>
      </a>"""
        items_html.append(item_html)

    items_str = "\n".join(items_html)

    widget = f"""<!-- cf-sidebar-related-widget v1 -->
<div class="cf-sidebar-related">
  <div class="cf-sr-heading">Related Posts</div>
{items_str}
</div>
<style>
.cf-sidebar-related {{
  background: #fdfdfd;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 24px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
  font-family: inherit;
}}
.cf-sr-heading {{
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 14px;
  padding-left: 10px;
  border-left: 4px solid #6d28d9;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}
.cf-sr-item {{
  display: flex;
  align-items: center;
  gap: 12px;
  text-decoration: none;
  background: #ffffff;
  border-radius: 10px;
  padding: 8px;
  margin-bottom: 10px;
  border: 1px solid #f1f5f9;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}}
.cf-sr-item:last-child {{
  margin-bottom: 0;
}}
.cf-sr-item:hover {{
  transform: translateY(-3px);
  box-shadow: 0 10px 15px -3px rgba(109, 40, 217, 0.15);
}}
.cf-sr-thumb {{
  width: 96px;
  height: 72px;
  object-fit: cover;
  border-radius: 8px;
  flex-shrink: 0;
  background: #e2e8f0;
}}
.cf-sr-placeholder {{
  background: linear-gradient(135deg, #6d28d9 0%, #9333ea 100%);
}}
.cf-sr-title {{
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}}
</style>"""
    return widget


def _remove_existing_widget(html: str) -> str:
    if not html:
        return html
    try:
        # 1. Remove old widget block
        html = re.sub(r'<!-- cf-sidebar-related-widget v1 -->.*?</style>\s*', '', html, flags=re.DOTALL)
        # 2. Remove layout CSS block and surrounding whitespace
        html = re.sub(r'\s*(?:<!-- cf-page-layout-css -->|/\* cf-page-layout-css \*/)\s*<style>.*?</style>\s*', '', html, flags=re.DOTALL)
        html = re.sub(r'\s*<!-- cf-page-layout-css -->\s*', '', html, flags=re.DOTALL)
        html = re.sub(r'\s*/\* cf-page-layout-css \*/.*?</style>\s*', '', html, flags=re.DOTALL)
        # 3. Remove any <aside class="cf-page-sidebar">...</aside>
        html = re.sub(r'<aside class="cf-page-sidebar">.*?</aside>\s*', '', html, flags=re.DOTALL | re.I)
        # 4. Unwrap <div class="cf-page-layout"> ... </div>
        html = re.sub(r'<div class="cf-page-layout">\s*(<article\b.*?</article>)\s*</div>\s*', r'\1', html, flags=re.DOTALL | re.I)
    except Exception:
        pass
    return html


def inject_sidebar_related(
    final_html: str,
    current_slug: str,
    title: str,
    keywords: List[str],
    n: int = 5,
) -> str:
    """Inject Related Posts widget into responsive sidebar layout of exported post HTML."""
    if not final_html:
        return final_html

    # Clean up existing widget, layout wrapper, and CSS to always start fresh
    final_html = _remove_existing_widget(final_html)

    try:
        registry = build_registry()
    except Exception as e:
        logger.warning("Sidebar related registry build failed: %s", e)
        return final_html

    try:
        picks = pick_sidebar_related(registry, current_slug, title, keywords, n=n)
    except Exception as e:
        logger.warning("Sidebar related picking failed: %s", e)
        return final_html

    if not picks:
        return final_html

    picks_data = []
    for slug, p_title in picks:
        img_rel = None
        try:
            post_dir = UNISCOLIAN_ROOT / slug
            post_file = post_dir / "index.html"
            if post_file.exists():
                content = post_file.read_text(encoding="utf-8", errors="ignore")
                img_rel = extract_featured_image(content)
        except Exception:
            pass
        picks_data.append({
            "slug": slug,
            "title": p_title,
            "img_rel": img_rel,
        })

    widget_html = build_sidebar_widget_html(picks_data)

    try:
        m_art = re.search(r'(<article\b[^>]*>.*?</article>)', final_html, re.I | re.DOTALL)
        if not m_art:
            logger.warning("No <article> tag found in HTML for %s; related posts widget skipped.", current_slug)
            return final_html

        article_block = m_art.group(1)
        a_start = m_art.start()
        a_end = m_art.end()

        new_block = (
            '<div class="cf-page-layout">\n'
            + article_block
            + '\n<aside class="cf-page-sidebar">\n'
            + widget_html
            + '\n</aside>\n</div>\n'
        )

        final_html = final_html[:a_start] + new_block + final_html[a_end:]

        if "<!-- cf-page-layout-css -->" not in final_html:
            layout_css = """<!-- cf-page-layout-css --><style>
.cf-page-layout{display:block;}
.cf-page-sidebar{margin:40px auto 0;max-width:750px;}
@media (min-width:1024px){
  .cf-page-layout{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:36px;align-items:start;max-width:1200px;width:100%;margin:0 auto;padding:0 20px;box-sizing:border-box;}
  .cf-page-sidebar{position:sticky;top:24px;margin:0;max-width:none;}
  .cf-page-layout article{max-width:none!important;width:auto!important;margin:0!important;}
}
</style>"""
            if "</head>" in final_html:
                final_html = final_html.replace("</head>", layout_css + "\n</head>", 1)
            elif "</body>" in final_html:
                final_html = final_html.replace("</body>", layout_css + "\n</body>", 1)
            else:
                final_html += "\n" + layout_css
    except Exception as e:
        logger.warning("Sidebar layout injection failed for %s: %s", current_slug, e)

    return final_html


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--backfill":
        print("Starting Uniscolian sidebar related posts backfill...")
        if not UNISCOLIAN_ROOT.exists():
            print(f"Error: UNISCOLIAN_ROOT does not exist at {UNISCOLIAN_ROOT}")
            sys.exit(1)
        registry = build_registry(UNISCOLIAN_ROOT, force=True)
        updated = 0
        skipped = 0
        static_slugs = {
            "about-us", "about", "contact", "privacy-policy", "terms-and-conditions",
            "terms", "disclaimer", "affiliate-disclosure", "service", "sitemap",
            "home", "blog", "shop", "cart", "checkout", "my-account", "_template"
        }
        for d in UNISCOLIAN_ROOT.iterdir():
            if not d.is_dir() or d.name.startswith("_") or d.name.startswith("wp-"):
                continue
            if d.name.lower() in static_slugs:
                continue
            f = d / "index.html"
            if not f.exists():
                continue
            try:
                html_content = f.read_text(encoding="utf-8", errors="ignore")
                tm = re.search(r'<h1 class="page-title"[^>]*>(.*?)</h1>', html_content, re.S)
                if tm:
                    t = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
                else:
                    tm = re.search(r'<title>(.*?)</title>', html_content, re.I)
                    t = re.sub(r'<[^>]+>', '', tm.group(1)).strip() if tm else d.name
                kw = list(tokenize(t))
                new_h = inject_sidebar_related(html_content, d.name, t, kw, n=5)
                if new_h != html_content:
                    f.write_text(new_h, encoding="utf-8")
                    updated += 1
                    print(f"  [UPDATED] {d.name}")
                else:
                    skipped += 1
            except Exception as e:
                skipped += 1
                print(f"  [ERROR] {d.name}: {e}")
        print(f"Backfill complete. Updated: {updated}, Skipped: {skipped}")
