"""Extract a reusable template from a real Uniscolian post and fill it with new data."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Dict

PLACEHOLDER_KEYS = ["TITLE", "TITLE_TAG", "META_DESC", "DATE_ISO", "DATE_HUMAN",
                    "READ_TIME", "WORD_COUNT", "CATEGORY_NAME", "CATEGORY_URL",
                    "FEATURED_IMAGE_URL", "CONTENT_HTML", "SLUG",
                    "TITLE_BREADCRUMB", "ARTICLE_SECTION", "SITE_DESCRIPTION", "AUTHOR_BIO",
                    "ENGAGEMENT_WIDGETS"]


def extract_template(html: str) -> str:
    t = html

    # --- head dynamic fields ---
    t = re.sub(r'<title>.*?</title>', '<title>{{TITLE_TAG}}</title>', t, count=1, flags=re.S)
    t = re.sub(r'(<meta name="description" content=")[^"]*(")', r'\1{{META_DESC}}\2', t, count=1)
    t = re.sub(r'(<meta property="og:title" content=")[^"]*(")', r'\1{{TITLE_TAG}}\2', t, count=1)
    t = re.sub(r'(<meta property="og:description" content=")[^"]*(")', r'\1{{META_DESC}}\2', t, count=1)
    t = re.sub(r'(<meta property="og:image" content=")[^"]*(")', r'\1{{FEATURED_IMAGE_URL}}\2', t, count=1)
    t = re.sub(r'(<meta property="article:published_time" content=")[^"]*(")', r'\1{{DATE_ISO}}\2', t, count=1)
    t = re.sub(r'(<meta property="article:modified_time" content=")[^"]*(")', r'\1{{DATE_ISO}}\2', t, count=1)
    t = re.sub(r'(<meta name="twitter:data2" content=")\d+(\s*minutes?")', r'\1{{READ_TIME}}\2', t, count=1)

    # --- schema.org JSON-LD dynamic fields (Order matters!) ---
    
    # 1. Headline and WordCount (Safe, no conflicts)
    t = re.sub(r'"headline":\s*"[^"]*"', '"headline": "{{TITLE}}"', t)
    t = re.sub(r'"wordCount":\s*\d+', '"wordCount": {{WORD_COUNT}}', t)
    t = re.sub(r'"datePublished":\s*"[^"]*"', '"datePublished": "{{DATE_ISO}}"', t)
    t = re.sub(r'"dateModified":\s*"[^"]*"', '"dateModified": "{{DATE_ISO}}"', t)
    
    # 2. Featured Image (thumbnailUrl)
    t = re.sub(r'("thumbnailUrl":\s*")[^"]*(")', r'\1{{FEATURED_IMAGE_URL}}\2', t)

    # 3. Specific Descriptions (MUST run BEFORE any global description replacement)
    # WebSite description
    t = re.sub(r'("@type":\s*"WebSite"[\s\S]*?"description":\s*")[^"]*(")', r'\1{{SITE_DESCRIPTION}}\2', t)
    # Person/Author description
    t = re.sub(r'("@type":\s*"Person"[\s\S]*?"description":\s*")[^"]*(")', r'\1{{AUTHOR_BIO}}\2', t)
    # Article description (Fallback if specific match fails)
    t = re.sub(r'("@type":\s*"Article"[\s\S]*?"description":\s*")[^"]*(")', r'\1{{META_DESC}}\2', t)

    # 4. SLUG and @id URLs
    ref_slug_match = re.search(r'"@id":\s*"//([^/#"]+)', t)
    if ref_slug_match:
        ref_slug = ref_slug_match.group(1)
        # Replace all variations of the old slug in URLs
        t = t.replace(f'"//{ref_slug}/"', '"//{{SLUG}}/"')
        t = t.replace(f'"//{ref_slug}/#', '"//{{SLUG}}/#')
        t = t.replace(f'//{ref_slug}/', '//{{SLUG}}/')

    # --- WebPage name (should match TITLE_TAG) ---
    t = re.sub(
        r'("@type":\s*"WebPage"[\s\S]*?"name":\s*")[^"]*(")',
        r'\1{{TITLE_TAG}}\2',
        t
    )

    # --- ImageObject URL/contentUrl/caption (primary featured image) ---
    t = re.sub(
        r'("@type":\s*"ImageObject"[\s\S]*?"@id":\s*"//\{\{SLUG\}\}/#primaryimage"[\s\S]*?"url":\s*")[^"]*(")',
        r'\1//{{FEATURED_IMAGE_URL}}\2',
        t
    )
    t = re.sub(
        r'("@type":\s*"ImageObject"[\s\S]*?"@id":\s*"//\{\{SLUG\}\}/#primaryimage"[\s\S]*?"contentUrl":\s*")[^"]*(")',
        r'\1//{{FEATURED_IMAGE_URL}}\2',
        t
    )
    t = re.sub(
        r'("@type":\s*"ImageObject"[\s\S]*?"@id":\s*"//\{\{SLUG\}\}/#primaryimage"[\s\S]*?"caption":\s*")[^"]*(")',
        r'\1{{TITLE}}\2',
        t
    )

    # 5. Breadcrumb Name
    t = re.sub(r'("@type":\s*"ListItem"[\s\S]*?"position":\s*2[\s\S]*?"name":\s*")[^"]*(")', r'\1{{TITLE_BREADCRUMB}}\2', t)

    # 6. Article Section
    t = re.sub(r'"articleSection":\s*\[[^\]]*\]', '"articleSection": ["{{ARTICLE_SECTION}}"]', t)

    # --- hero title ---
    t = re.sub(r'(<h1 class="page-title" itemprop="headline">).*?(</h1>)',
               r'\1{{TITLE}}\2', t, count=1, flags=re.S)

    # --- hero meta: date + category ---
    t = re.sub(r'(<time class="ct-meta-element-date" datetime=")[^"]*(">).*?(</time>)',
               r'\1{{DATE_ISO}}\2{{DATE_HUMAN}}\3', t, count=1, flags=re.S)
    t = re.sub(r'(<li class="meta-categories"[^>]*><a href=")[^"]*("[^>]*>).*?(</a></li>)',
               r'\1{{CATEGORY_URL}}\2{{CATEGORY_NAME}}\3', t, count=1, flags=re.S)

    # --- entry content: replace everything between entry-content open and its closing div ---
    start = t.find('<div class="entry-content')
    if start == -1:
        raise ValueError("entry-content marker not found in reference post")
    open_end = t.find('>', start) + 1
    author = t.find('<div class="author-box')
    if author == -1:
        raise ValueError("author-box marker not found in reference post")
    close = t.rfind('</div>', 0, author)
    t = t[:open_end] + "\n{{CONTENT_HTML}}\n" + t[close:]

    # --- engagement widgets (progress bar, back-to-top, typography styles) ---
    t = re.sub(r'(<body[^>]*>)', r'\1\n{{ENGAGEMENT_WIDGETS}}', t, count=1)

    return t


def ensure_template(reference_path: Path, template_path: Path) -> Path:
    """Build template from reference post if missing (or rebuild if --force)."""
    template_path.parent.mkdir(parents=True, exist_ok=True)
    if not reference_path.exists():
        raise FileNotFoundError(f"Reference post not found: {reference_path}")
    html = reference_path.read_text(encoding="utf-8")
    template_path.write_text(extract_template(html), encoding="utf-8")
    return template_path


def fill_template(template: str, values: Dict[str, str]) -> str:
    out = template
    for k in PLACEHOLDER_KEYS:
        out = out.replace("{{" + k + "}}", str(values.get(k, "")))
    return out
