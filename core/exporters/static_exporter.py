"""Export an assembled Markdown blog into the Uniscolian static site."""
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.config import (logger, UNISCOLIAN_ROOT, UNISCOLIAN_REFERENCE_POST,
                        UNISCOLIAN_TEMPLATE_PATH, UNISCOLIAN_UPLOADS_DIR,
                        DEFAULT_CATEGORY_NAME, DEFAULT_CATEGORY_SLUG,
                        RELATED_LINKS_COUNT)
from core.exporters.template_extractor import ensure_template, fill_template
from core.exporters.wp_block_converter import (convert_markdown_to_wp_blocks,
                                               build_ez_toc, slugify_anchor,
                                               strip_heading_number)
from core.exporters.image_generator import generate_featured_image
from core.exporters.sitemap_manager import (ensure_unique_slug, existing_slugs,
                                            add_to_sitemap, build_registry)
from core.exporters.internal_linker import pick_related, insert_related_links
from core.exporters.engagement import ENGAGEMENT_BLOCK


def slugify_slug(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r'[^a-z0-9\s-]', '', t)
    return re.sub(r'[\s-]+', '-', t).strip('-')[:80]


def export_post_to_uniscolian(
    markdown: str,
    topic: str,
    category_name: str = DEFAULT_CATEGORY_NAME,
    category_slug: str = DEFAULT_CATEGORY_SLUG,
    featured_image_filename: Optional[str] = None,
    generate_image: bool = True,
    avoid_duplicates: bool = True,
    update_sitemap: bool = True,
    keywords: Optional[List[str]] = None,
    add_related: bool = True,
) -> Dict:
    now = datetime.now()
    uploads_ym = now.strftime("%Y/%m")
    base_slug = slugify_slug(topic)
    if avoid_duplicates:
        slug = ensure_unique_slug(base_slug, existing_slugs(UNISCOLIAN_ROOT))
    else:
        slug = base_slug

    # Title from first H1, else topic
    m = re.search(r'^#\s+(.+)$', markdown, re.M)
    title = strip_heading_number(m.group(1).strip()) if m else topic.title()

    # Meta description from first non-heading paragraph
    first_para = ""
    for line in markdown.split("\n"):
        s = line.strip()
        if s and not s.startswith(("#", ">", "|", "!", "-")):
            first_para = re.sub(r'[\*\_]', '', s)
            break
    meta_desc = (first_para[:155] + "…") if len(first_para) > 155 else first_para

    word_count = len(markdown.split())
    read_time = max(1, round(word_count / 220))

    body_html, images, headings = convert_markdown_to_wp_blocks(markdown, uploads_ym)
    
    related_picks: List[Tuple[str, str]] = []
    if add_related:
        try:
            registry = build_registry()
            related_picks = pick_related(
                registry, slug, title, keywords or [], RELATED_LINKS_COUNT
            )
            if related_picks:
                body_html = insert_related_links(body_html, related_picks)
                logger.info("Inserted %d related links into %s", len(related_picks), slug)
            else:
                logger.info("No related posts found for %s (registry has %d entries)",
                            slug, len(registry))
        except Exception as e:
            logger.warning("Related-link injection skipped: %s", e)

    toc_html = build_ez_toc(headings)

    # Featured image convention: {slug}-featured.jpg
    featured = featured_image_filename or f"{slug}-featured.jpg"
    featured_rel = f"wp-content/uploads/{uploads_ym}/{featured}"

    img_info = generate_featured_image(topic, title, slug) if generate_image else {"status": "skipped", "source": "none", "relative_path": featured_rel, "file_exists": False}

    if not img_info.get("file_exists"):
        images.insert(0, {"filename": featured, "relative_path": featured_rel,
                          "alt": title, "role": "featured"})

    # Featured figure at top of content (like reference posts)
    if img_info.get("file_exists"):
        featured_figure = (
            f'<figure class="wp-block-image aligncenter size-full is-resized">'
            f'<img decoding="async" width="450" height="377" src="./../{featured_rel}" srcset="./../{featured_rel} 2x" '
            f'alt="{title}" class="wp-image-1126" loading="lazy" '
            f'style="width:450px;max-width:100%;height:auto;">'
            f'</figure>'
        )
    else:
        featured_figure = (
            f'<figure class="wp-block-image aligncenter size-full is-resized">'
            f'<img decoding="async" width="450" height="377" src="./../{featured_rel}" srcset="./../{featured_rel} 2x" '
            f'alt="{title}" class="wp-image-1126" loading="lazy" '
            f'style="width:450px;max-width:100%;height:auto;">'
            f'<figcaption class="wp-element-caption">[IMAGE] {title} — <code>{featured_rel}</code></figcaption></figure>'
        )

    content_html = featured_figure + "\n" + toc_html + "\n" + body_html

    # Ensure template exists
    ensure_template(UNISCOLIAN_REFERENCE_POST, UNISCOLIAN_TEMPLATE_PATH)
    template = UNISCOLIAN_TEMPLATE_PATH.read_text(encoding="utf-8")

    values = {
        "TITLE": title,
        "TITLE_TAG": f"{title} - Uniscolian",
        "META_DESC": meta_desc.replace('"', "'"),
        "DATE_ISO": now.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "DATE_HUMAN": now.strftime("%B %d, %Y"),
        "READ_TIME": str(read_time),
        "WORD_COUNT": str(word_count),
        "CATEGORY_NAME": category_name,
        "CATEGORY_URL": f"./../{category_slug}/index.html",
        "FEATURED_IMAGE_URL": featured_rel,
        "CONTENT_HTML": content_html,
        "SLUG": slug,
        "TITLE_BREADCRUMB": title,
        "ARTICLE_SECTION": category_name,
        "SITE_DESCRIPTION": "Technology for food security and human dignity",
        "AUTHOR_BIO": "I research and explain emerging technologies like AI, automation, and smart infrastructure, focusing on real-world solutions for sustainability, food systems, and everyday digital challenges. I believe technology should serve humanity, not overwhelm it.",
        "ENGAGEMENT_WIDGETS": ENGAGEMENT_BLOCK,
    }
    final_html = fill_template(template, values)

    post_dir = UNISCOLIAN_ROOT / slug
    post_dir.mkdir(parents=True, exist_ok=True)
    post_file = post_dir / "index.html"
    post_file.write_text(final_html, encoding="utf-8")
    logger.info("[OK] Uniscolian post exported: %s", post_file)

    sitemap_updated = add_to_sitemap(UNISCOLIAN_ROOT, slug) if update_sitemap else False

    return {
        "slug": slug,
        "path": str(post_file),
        "url": f"/{slug}/",
        "word_count": word_count,
        "read_time": read_time,
        "expected_images": images,
        "image": img_info,
        "sitemap_updated": sitemap_updated,
        "slug_renamed": slug != base_slug,
        "related": [{"slug": s, "title": t} for s, t in related_picks],
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python -m core.exporters.static_exporter <markdown_file> <topic>")
        sys.exit(1)
    md_path = Path(sys.argv[1])
    result = export_post_to_uniscolian(md_path.read_text(encoding="utf-8"), sys.argv[2])
    if result.get("slug_renamed"):
        print("[RENAMED] duplicate avoided ->", result["slug"])
    print("Sitemap updated:", result["sitemap_updated"])
    print("[LINKS] Related links:",
          ", ".join(r["slug"] for r in result["related"]) if result["related"] else "none")
    print("\n[OK] EXPORTED:", result["url"])
    print(f"\nImage: {result['image']['status']} ({result['image']['source']}) -> {result['image']['relative_path']}")
    if result["expected_images"]:
        print("\nExpected Images:")
        for img in result["expected_images"]:
            print(f"   - {img['relative_path']}   (role: {img['role']}, alt: {img['alt']})")
