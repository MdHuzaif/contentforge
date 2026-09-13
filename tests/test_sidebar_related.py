from __future__ import annotations
import pytest
from pathlib import Path
from core.exporters.sidebar_related import (
    pick_sidebar_related,
    extract_featured_image,
    build_sidebar_widget_html,
    inject_sidebar_related,
)


def test_pick_returns_max_5_and_excludes_current_slug():
    registry = {
        f"post-{i}": f"Topic About Tech {i}" for i in range(1, 11)
    }
    registry["current-slug"] = "Topic About Tech Current"
    picks = pick_sidebar_related(registry, "current-slug", "Topic About Tech Current", ["tech"], n=5)
    assert len(picks) <= 5
    assert not any(slug == "current-slug" for slug, _ in picks)


def test_pick_excludes_title_variants():
    registry = {
        "topic-1": "Best Gaming Laptops",
        "topic-2": "Best Gaming Laptops",
        "topic-3": "Best Gaming Laptops",
        "other-post": "Cooking Recipes for Beginners",
    }
    picks = pick_sidebar_related(registry, "topic-4", "Best Gaming Laptops", ["gaming"], n=5)
    # None of the same title ("Best Gaming Laptops") should appear
    for slug, title in picks:
        assert title.lower() != "best gaming laptops"


def test_scoring_prefers_keyword_overlap():
    registry = {
        "unrelated": "Gardening Tips and Flowers",
        "related": "Ultimate Gaming Laptop Review and Specs",
    }
    picks = pick_sidebar_related(registry, "current", "Gaming Laptop Guide", ["gaming", "laptop"], n=2)
    assert len(picks) > 0
    assert picks[0][0] == "related"


def test_extract_featured_image_from_og_meta():
    html = '<html><head><meta property="og:image" content="./../wp-content/uploads/2023/01/image.jpg"></head><body></body></html>'
    res = extract_featured_image(html)
    assert res == "wp-content/uploads/2023/01/image.jpg"


def test_extract_featured_image_fallback_to_figure():
    html = '<html><body><figure><img src="./../wp-content/uploads/2023/02/fig.jpg"></figure></body></html>'
    res = extract_featured_image(html)
    assert res == "wp-content/uploads/2023/02/fig.jpg"


def test_extract_featured_image_missing_returns_none():
    html = '<html><body><p>No images here</p></body></html>'
    res = extract_featured_image(html)
    assert res is None


def test_widget_html_structure():
    picks = [
        {"slug": "test-slug", "title": "Test Title", "img_rel": "wp-content/uploads/img.jpg"}
    ]
    html = build_sidebar_widget_html(picks)
    assert "<!-- cf-sidebar-related-widget" in html
    assert 'class="cf-sidebar-related"' in html
    assert 'href="./../test-slug/index.html"' in html
    assert 'src="./../wp-content/uploads/img.jpg"' in html
    assert "Test Title" in html


def test_widget_idempotent():
    page = '<html><body><article><p>Content</p></article></body></html>'
    res1 = inject_sidebar_related(page, "curr", "Title", ["kw"], n=1)
    # Inject second time
    res2 = inject_sidebar_related(res1, "curr", "Title", ["kw"], n=1)
    assert res1 == res2
    assert res2.count("cf-sidebar-related-widget") == 1


def test_injection_into_aside_container():
    page = '<html><body><article><p>Content</p></article></body></html>'
    res = inject_sidebar_related(page, "curr", "Title", ["kw"], n=1)
    assert "<aside" in res
    assert "cf-page-layout" in res
    assert "cf-sidebar-related" in res


def test_layout_wrapper_created():
    page = '<html><body><article id="p1"><p>Content</p></article></body></html>'
    res = inject_sidebar_related(page, "curr", "Title", ["kw"], n=1)
    assert '<div class="cf-page-layout">' in res
    assert '<aside class="cf-page-sidebar">' in res
    article_end = res.find("</article>")
    aside_start = res.find("<aside class=\"cf-page-sidebar\">")
    wrapper_end = res.find("</div>", aside_start)
    assert article_end < aside_start < wrapper_end


def test_responsive_css_present():
    page = '<html><head></head><body><article><p>Content</p></article></body></html>'
    res = inject_sidebar_related(page, "curr", "Title", ["kw"], n=1)
    assert "<!-- cf-page-layout-css -->" in res
    assert ".cf-page-layout{display:block;}" in res
    assert "@media (min-width:1024px)" in res
    assert "grid-template-columns:minmax(0,1fr) 320px" in res
    assert ".cf-page-sidebar{position:sticky" in res


def test_mobile_order():
    page = '<html><body><article><p>Content</p></article></body></html>'
    res = inject_sidebar_related(page, "curr", "Title", ["kw"], n=1)
    article_end = res.find("</article>")
    aside_start = res.find("<aside class=\"cf-page-sidebar\">")
    assert article_end < aside_start


def test_relayout_moves_old_bottom_widget():
    old_widget = '<!-- cf-sidebar-related-widget v1 -->\n<div class="cf-sidebar-related">Old</div>\n<style></style>'
    page = f'<html><body><article><p>Content</p>{old_widget}</article></body></html>'
    res = inject_sidebar_related(page, "curr", "Title", ["kw"], n=1)
    assert res.count("cf-sidebar-related-widget") == 1
    article_part = res[:res.find("</article>")]
    assert "cf-sidebar-related-widget" not in article_part
    aside_part = res[res.find("<aside class=\"cf-page-sidebar\">"):]
    assert "cf-sidebar-related-widget" in aside_part


def test_idempotent_second_run():
    page = '<html><body><article><p>Content</p></article></body></html>'
    res1 = inject_sidebar_related(page, "curr", "Title", ["kw"], n=1)
    res2 = inject_sidebar_related(res1, "curr", "Title", ["kw"], n=1)
    assert res1 == res2
    assert res2.count("cf-sidebar-related-widget") == 1
    assert res2.count('<div class="cf-page-layout">') == 1


def test_missing_image_uses_placeholder():
    picks = [
        {"slug": "no-img", "title": "No Image Post", "img_rel": None}
    ]
    html = build_sidebar_widget_html(picks)
    assert "cf-sr-placeholder" in html
    assert "No Image Post" in html


def test_static_exporter_calls_sidebar_injection():
    import inspect
    from core.exporters.static_exporter import export_post_to_uniscolian
    source = inspect.getsource(export_post_to_uniscolian)
    assert "inject_sidebar_related" in source


def test_titles_html_escaped():
    picks = [
        {"slug": "x", "title": '<script>alert("hack")</script>', "img_rel": None}
    ]
    html = build_sidebar_widget_html(picks)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
