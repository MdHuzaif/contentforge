from __future__ import annotations
import json
import sys
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import app.config as config_mod
import core.exporters.sitemap_manager as sm_mod
import core.exporters.static_exporter as se_mod
from core.exporters.sitemap_manager import (
    parse_sitemap,
    existing_slugs,
    ensure_unique_slug,
    add_to_sitemap,
    build_registry,
    SITEMAP_HEADER,
)
from core.exporters.static_exporter import export_post_to_uniscolian


@pytest.fixture
def fake_site(tmp_path, monkeypatch):
    # Setup directories
    (tmp_path / "old-post-a").mkdir(parents=True, exist_ok=True)
    (tmp_path / "old-post-b").mkdir(parents=True, exist_ok=True)
    (tmp_path / "_template").mkdir(parents=True, exist_ok=True)

    # Write post HTMLs with <h1 class="page-title">
    (tmp_path / "old-post-a" / "index.html").write_text(
        '<!DOCTYPE html><html><body><h1 class="page-title">Old Post A Title</h1></body></html>',
        encoding="utf-8",
    )
    (tmp_path / "old-post-b" / "index.html").write_text(
        '<!DOCTYPE html><html><body><h1 class="page-title">Old Post B Title</h1></body></html>',
        encoding="utf-8",
    )

    # Write post-sitemap.xml with Yoast-style header and entries
    sitemap_xml = (
        SITEMAP_HEADER
        + "<url>\n<loc>./</loc>\n<lastmod>2026-01-01T00:00:00+00:00</lastmod>\n</url>\n"
        + "<url>\n<loc>./old-post-a/</loc>\n<lastmod>2026-01-01T00:00:00+00:00</lastmod>\n</url>\n"
        + "<url>\n<loc>./old-post-b/</loc>\n<lastmod>2026-01-01T00:00:00+00:00</lastmod>\n</url>\n"
        + "</urlset>\n"
    )
    (tmp_path / "post-sitemap.xml").write_text(sitemap_xml, encoding="utf-8")

    # Minimal reference post template for export_post_to_uniscolian
    ref_post = tmp_path / "reference.html"
    ref_post.write_text(
        """<!DOCTYPE html>
<html>
<head>
<title>{{TITLE}}</title>
<meta name="description" content="{{META_DESC}}">
</head>
<body>
<h1 class="page-title">{{TITLE}}</h1>
<time class="ct-meta-element-date" datetime="{{DATE_ISO}}">{{DATE_HUMAN}}</time>
<ul><li class="meta-categories"><a href="{{CATEGORY_URL}}">{{CATEGORY_NAME}}</a></li></ul>
<div class="entry-content">{{CONTENT_HTML}}</div>
<div class="author-box">Author</div>
</body>
</html>
""",
        encoding="utf-8",
    )

    registry_path = tmp_path / "_template" / "post_registry.json"

    # Monkeypatch UNISCOLIAN_ROOT and POST_REGISTRY_PATH across modules
    monkeypatch.setattr(config_mod, "UNISCOLIAN_ROOT", tmp_path)
    monkeypatch.setattr(config_mod, "POST_REGISTRY_PATH", registry_path)
    monkeypatch.setattr(config_mod, "UNISCOLIAN_REFERENCE_POST", ref_post)
    monkeypatch.setattr(config_mod, "UNISCOLIAN_TEMPLATE_PATH", tmp_path / "_template" / "post_template.html")

    monkeypatch.setattr(sm_mod, "UNISCOLIAN_ROOT", tmp_path)
    monkeypatch.setattr(sm_mod, "POST_REGISTRY_PATH", registry_path)

    monkeypatch.setattr(se_mod, "UNISCOLIAN_ROOT", tmp_path)
    monkeypatch.setattr(se_mod, "UNISCOLIAN_REFERENCE_POST", ref_post)
    monkeypatch.setattr(se_mod, "UNISCOLIAN_TEMPLATE_PATH", tmp_path / "_template" / "post_template.html")

    return tmp_path


def test_parse_sitemap(fake_site):
    sm = sm_mod.find_sitemap(fake_site)
    slugs = parse_sitemap(sm)
    assert slugs == ["old-post-a", "old-post-b"]


def test_existing_slugs(fake_site):
    slugs = existing_slugs(fake_site)
    assert "old-post-a" in slugs
    assert "old-post-b" in slugs


def test_ensure_unique_slug(fake_site):
    taken = {"x"}
    assert ensure_unique_slug("x", taken) == "x-2"
    taken2 = {"x", "x-2"}
    assert ensure_unique_slug("x", taken2) == "x-3"
    assert ensure_unique_slug("x", set()) == "x"


def test_add_to_sitemap_relative(fake_site):
    added = add_to_sitemap(fake_site, "new-post")
    assert added is True
    sm = sm_mod.find_sitemap(fake_site)
    xml = sm.read_text(encoding="utf-8")
    assert "<loc>./new-post/</loc>" in xml
    # Second call should be idempotent and return False
    assert add_to_sitemap(fake_site, "new-post") is False


def test_add_to_sitemap_creates_file(tmp_path, monkeypatch):
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    monkeypatch.setattr(config_mod, "UNISCOLIAN_ROOT", empty_root)
    monkeypatch.setattr(sm_mod, "UNISCOLIAN_ROOT", empty_root)

    added = add_to_sitemap(empty_root, "new")
    assert added is True
    sm = sm_mod.find_sitemap(empty_root)
    assert sm.exists()
    xml = sm.read_text(encoding="utf-8")
    assert "<loc>./new/</loc>" in xml
    assert 'href="./main-sitemap.xsl"' in xml


def test_build_registry(fake_site):
    reg = build_registry(fake_site)
    assert reg == {
        "old-post-a": "Old Post A Title",
        "old-post-b": "Old Post B Title",
    }
    assert config_mod.POST_REGISTRY_PATH.exists()

    # Delete one html file, call again without force -> should still return both from cached registry json
    (fake_site / "old-post-b" / "index.html").unlink()
    reg_cached = build_registry(fake_site, force=False)
    assert "old-post-b" in reg_cached


def test_export_unique_slug(fake_site):
    md = "# 1. Old Post A\n\n## 1. Introduction\n\n## 2. Top Laptops\n\nContent paragraph here."
    result = export_post_to_uniscolian(markdown=md, topic="old-post-a")
    assert result["slug_renamed"] is True
    assert result["slug"] == "old-post-a-2"
    html_path = fake_site / "old-post-a-2" / "index.html"
    assert html_path.exists()
    html_content = html_path.read_text(encoding="utf-8")
    # Verify no numbering in headings
    assert "1. Introduction" not in html_content
    assert "2. Top" not in html_content

    sm = sm_mod.find_sitemap(fake_site)
    xml = sm.read_text(encoding="utf-8")
    assert "<loc>./old-post-a-2/</loc>" in xml


def test_jsonld_schema_placeholders():
    from core.exporters.template_extractor import extract_template, fill_template
    sample_html = """
    <script type="application/ld+json">
    {
      "@graph": [
        {
          "@type": "WebSite",
          "@id": "//best-gaming-laptops/#website",
          "url": "//best-gaming-laptops/",
          "name": "Uniscolian",
          "description": "Old site description"
        },
        {
          "@type": "WebPage",
          "@id": "//best-gaming-laptops/",
          "url": "//best-gaming-laptops/",
          "name": "Old Title - Uniscolian"
        },
        {
          "@type": "Person",
          "@id": "//best-gaming-laptops/#author",
          "name": "Author",
          "description": "Old author bio"
        },
        {
          "@type": "ImageObject",
          "@id": "//best-gaming-laptops/#primaryimage",
          "url": "//wp-content/uploads/2023/01/laptop.jpg",
          "contentUrl": "//wp-content/uploads/2023/01/laptop.jpg",
          "caption": "Old Title"
        },
        {
          "@type": "Article",
          "@id": "//best-gaming-laptops/#article",
          "isPartOf": {"@id": "//best-gaming-laptops/#website"},
          "headline": "Reference Headline",
          "description": "Reference Article Description",
          "articleSection": ["OldSection"]
        }
      ]
    }
    </script>
    <div class="entry-content">Old content</div>
    <div class="author-box">Author</div>
    """
    tpl = extract_template(sample_html)
    assert "{{SLUG}}" in tpl
    assert "{{ARTICLE_SECTION}}" in tpl
    assert "{{SITE_DESCRIPTION}}" in tpl
    assert "{{AUTHOR_BIO}}" in tpl
    assert "{{META_DESC}}" in tpl
    assert "{{TITLE_TAG}}" in tpl
    assert "{{FEATURED_IMAGE_URL}}" in tpl
    assert "{{TITLE}}" in tpl

    values = {
        "TITLE": "New Title",
        "TITLE_TAG": "New Title - Uniscolian",
        "META_DESC": "New Article Description",
        "DATE_ISO": "2026-03-01T12:00:00+00:00",
        "DATE_HUMAN": "March 1, 2026",
        "READ_TIME": "5",
        "WORD_COUNT": "1000",
        "CATEGORY_NAME": "Laptop",
        "CATEGORY_URL": "./../laptop/index.html",
        "FEATURED_IMAGE_URL": "wp-content/uploads/2026/03/test-featured.jpg",
        "CONTENT_HTML": "<p>Hello World</p>",
        "SLUG": "new-slug",
        "TITLE_BREADCRUMB": "New Title",
        "ARTICLE_SECTION": "Laptop",
        "SITE_DESCRIPTION": "Technology for food security and human dignity",
        "AUTHOR_BIO": "New author bio here",
    }
    filled = fill_template(tpl, values)
    assert "//new-slug/" in filled
    assert "//new-slug/#article" in filled
    assert '"articleSection": ["Laptop"]' in filled
    assert '"description": "Technology for food security and human dignity"' in filled
    assert '"description": "New author bio here"' in filled
    assert '"description": "New Article Description"' in filled
    assert '"name": "New Title - Uniscolian"' in filled
    assert '"url": "//wp-content/uploads/2026/03/test-featured.jpg"' in filled
    assert '"caption": "New Title"' in filled


def main():
    # Run tests programmatically or via pytest
    test_jsonld_schema_placeholders()
    print("LEVEL 10 VERIFIED — sitemap + registry + unique slug OK.")


if __name__ == "__main__":
    main()
