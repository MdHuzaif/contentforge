"""Unit tests for Level 8 Uniscolian Static Website Exporter."""
from __future__ import annotations
import sys
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.exporters.template_extractor import extract_template, fill_template, ensure_template, PLACEHOLDER_KEYS
from core.exporters.wp_block_converter import convert_markdown_to_wp_blocks, build_ez_toc
from core.exporters.static_exporter import export_post_to_uniscolian
from core.exporters.engagement import ENGAGEMENT_BLOCK
from app.config import UNISCOLIAN_REFERENCE_POST, BLOGS_DIR


FIXTURE_HTML = """<!DOCTYPE html>
<html>
<head>
<title>Old</title>
<meta name="description" content="Old description">
<meta property="og:title" content="Old">
<meta property="og:description" content="Old description">
<meta property="og:image" content="wp-content/uploads/2023/01/laptop.jpg">
<meta property="article:published_time" content="2023-01-01T00:00:00+00:00">
<meta property="article:modified_time" content="2023-01-01T00:00:00+00:00">
<meta name="twitter:data2" content="22 minutes">
<script type="application/ld+json">
{
  "@graph": [
    {
      "@type": "WebSite",
      "@id": "//best-gaming-laptops/#website",
      "url": "//best-gaming-laptops/",
      "description": "Old site desc"
    },
    {
      "@type": "Person",
      "@id": "//best-gaming-laptops/#author",
      "description": "Old author bio"
    },
    {
      "@type": "BreadcrumbList",
      "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home"},
        {"@type": "ListItem", "position": 2, "name": "Old"}
      ]
    },
    {
      "@type": "Article",
      "@id": "//best-gaming-laptops/#article",
      "headline": "Old",
      "description": "Old description",
      "datePublished": "2023-01-01T00:00:00+00:00",
      "dateModified": "2023-01-01T00:00:00+00:00",
      "wordCount": 100,
      "thumbnailUrl": "wp-content/uploads/2023/01/laptop.jpg",
      "articleSection": ["Laptop"]
    }
  ]
}
</script>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
<h1 class="page-title" itemprop="headline">Old</h1>
<div class="meta-wrap">
<time class="ct-meta-element-date" datetime="2023-01-01">January 1, 2023</time>
<ul>
<li class="meta-categories" itemprop="about"><a href="http://example.com/cat">Laptop</a></li>
</ul>
</div>
</header>
<main>
<div class="entry-content is-layout-constrained">
<p>Old paragraph with wp-content/uploads/2023/01/x.jpg image.</p>
</div>
<div class="author-box">Author Bio</div>
</main>
</body>
</html>
"""


def test_extract_template():
    template = extract_template(FIXTURE_HTML)
    for k in PLACEHOLDER_KEYS:
        assert "{{" + k + "}}" in template, f"Missing placeholder {k}"
    assert '<link rel="stylesheet" href="style.css">' in template
    assert '<div class="author-box">Author Bio</div>' in template


def test_fill_template():
    template = extract_template(FIXTURE_HTML)
    values = {
        "TITLE": "Test Title",
        "TITLE_TAG": "Test Title - Uniscolian",
        "META_DESC": "Test meta description",
        "DATE_ISO": "2026-03-01T12:00:00+00:00",
        "DATE_HUMAN": "March 1, 2026",
        "READ_TIME": "5",
        "WORD_COUNT": "1000",
        "CATEGORY_NAME": "Laptop",
        "CATEGORY_URL": "./../laptop/index.html",
        "FEATURED_IMAGE_URL": "wp-content/uploads/2026/03/test-featured.jpg",
        "CONTENT_HTML": "<p>Hello World</p>",
    }
    filled = fill_template(template, values)
    assert "Test Title" in filled
    assert "March 1, 2026" in filled
    assert "<p>Hello World</p>" in filled
    assert "{{" not in filled  # all placeholders filled


def test_wp_block_converter():
    md = """# Main Title

## Section Two
This is a paragraph with **bold** and *italic* text and [link](https://example.com).

### Subsection Three
- Item A
- Item B

1. First ordered
2. Second ordered

> This is a blockquote.

---

| Col 1 | Col 2 |
|---|---|
| Val 1 | Val 2 |

![My Image](test-image.jpg)
"""
    body_html, images, headings = convert_markdown_to_wp_blocks(md, "2026/03")
    assert "wp-block-heading" in body_html
    assert "ez-toc-section" in body_html
    assert "wp-block-list" in body_html
    assert "wp-block-table" in body_html
    assert "wp-block-quote" in body_html
    assert "wp-block-separator" in body_html
    assert "wp-block-image" in body_html
    assert len(images) == 1
    assert images[0]["filename"] == "test-image.jpg"
    assert images[0]["relative_path"] == "wp-content/uploads/2026/03/test-image.jpg"
    assert len(headings) == 2


def test_build_ez_toc():
    headings = [(2, "Introduction"), (3, "Specs")]
    toc = build_ez_toc(headings)
    assert "ez-toc-container" in toc
    assert 'href="#Introduction"' in toc
    assert 'href="#Specs"' not in toc  # H3 must not be present in TOC by default


def test_engagement_widgets():
    template = extract_template(FIXTURE_HTML)
    assert "{{ENGAGEMENT_WIDGETS}}" in template
    values = {
        "TITLE": "Test", "TITLE_TAG": "Test", "META_DESC": "Test",
        "DATE_ISO": "2026-01-01T00:00:00+00:00", "DATE_HUMAN": "January 1, 2026",
        "READ_TIME": "1", "WORD_COUNT": "100", "CATEGORY_NAME": "Cat",
        "CATEGORY_URL": "./cat/", "FEATURED_IMAGE_URL": "img.jpg",
        "CONTENT_HTML": "<p>Content</p>", "SLUG": "slug",
        "TITLE_BREADCRUMB": "Test", "ARTICLE_SECTION": "Cat",
        "SITE_DESCRIPTION": "Desc", "AUTHOR_BIO": "Bio",
        "ENGAGEMENT_WIDGETS": ENGAGEMENT_BLOCK,
    }
    filled = fill_template(template, values)
    assert 'id="cf-progress"' in filled
    assert '.entry-content h2{font-size' in filled


def test_optional_real_export(tmp_path, monkeypatch):
    # If real reference post exists and markdown exists, test real export
    md_file = BLOGS_DIR / "best-budget-laptop-for-video-editing.md"
    if UNISCOLIAN_REFERENCE_POST.exists() and md_file.exists():
        res = export_post_to_uniscolian(
            markdown=md_file.read_text(encoding="utf-8"),
            topic="Best Budget Laptop for Video Editing"
        )
        assert Path(res["path"]).exists()
        assert "wp-block-heading" in Path(res["path"]).read_text(encoding="utf-8")


def test_ensure_template_raises(tmp_path):
    missing_ref = tmp_path / "missing.html"
    tpl_path = tmp_path / "template.html"
    with pytest.raises(FileNotFoundError):
        ensure_template(missing_ref, tpl_path)


def test_heading_numbering_removed():
    """Verify that '1. Introduction' becomes 'Introduction' in exported HTML."""
    from core.exporters.wp_block_converter import convert_markdown_to_wp_blocks
    
    md = """# Title

## 1. Introduction & Quick Picks

Some intro text.

## 2. Top Business Laptops for 2026

Content about laptops.

### 2.1 Subsection

More content.

## 3. Alternative Models Tested

Final section.
"""
    
    body_html, images, headings = convert_markdown_to_wp_blocks(md, "2026/03")
    
    # Check that numbering is removed from HTML
    assert "Introduction &amp; Quick Picks" in body_html or "Introduction & Quick Picks" in body_html
    assert "1. Introduction" not in body_html
    assert "Top Business Laptops for 2026" in body_html
    assert "2. Top Business Laptops" not in body_html
    assert "Alternative Models Tested" in body_html
    assert "3. Alternative Models" not in body_html
    
    # Check that numbering is removed from headings list (used for TOC)
    heading_texts = [h[1] for h in headings]
    assert "Introduction & Quick Picks" in heading_texts
    assert "1. Introduction & Quick Picks" not in heading_texts
    assert "Top Business Laptops for 2026" in heading_texts
    assert "Alternative Models Tested" in heading_texts
    
    print("[OK] Heading numbering correctly stripped")


def main():
    test_extract_template()
    test_fill_template()
    test_wp_block_converter()
    test_build_ez_toc()
    test_heading_numbering_removed()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        missing_ref = tmp_path / "missing.html"
        tpl_path = tmp_path / "template.html"
        try:
            ensure_template(missing_ref, tpl_path)
            raise AssertionError("Expected FileNotFoundError")
        except FileNotFoundError:
            pass

    md_file = BLOGS_DIR / "best-budget-laptop-for-video-editing.md"
    if UNISCOLIAN_REFERENCE_POST.exists() and md_file.exists():
        res = export_post_to_uniscolian(
            markdown=md_file.read_text(encoding="utf-8"),
            topic="Best Budget Laptop for Video Editing"
        )
        assert Path(res["path"]).exists()
        assert "wp-block-heading" in Path(res["path"]).read_text(encoding="utf-8")

    print("LEVEL 8 UNISCOLIAN VERIFIED — template + converter + exporter OK.")


if __name__ == "__main__":
    main()
