"""TDD tests for post UPDATE mode (replace index.html of existing slug)."""
from __future__ import annotations
import sys, pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import app.config as config_mod
import core.exporters.sitemap_manager as sm_mod
import core.exporters.static_exporter as se
import core.exporters.sidebar_related as sb
from core.exporters.static_exporter import export_post_to_uniscolian, parse_update_target

REF_TEMPLATE = ('<!DOCTYPE html><html><head><title>{{TITLE}}</title>'
                '<meta name="description" content="{{META_DESC}}">'
                '<meta property="og:title" content="{{TITLE}}">'
                '<meta property="og:description" content="{{META_DESC}}">'
                '</head><body><h1 class="page-title">{{TITLE}}</h1>'
                '<time class="ct-meta-element-date" datetime="2026-01-01T00:00:00+00:00">January 01, 2026</time>'
                '<ul><li class="meta-categories"><a href="./category/">Category</a></li></ul>'
                '<div class="entry-content">{{CONTENT_HTML}}</div>'
                '<div class="author-box">Author</div></body></html>')
NEW_MD = "# New Title\n## Introduction\nFresh content paragraph.\n"

@pytest.fixture
def fake_site(tmp_path, monkeypatch):
    for d in ("old-post", "other-post", "_template"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    (tmp_path / "old-post" / "index.html").write_text(
        '<html><body><h1 class="page-title">Old Title</h1>Old content</body></html>', encoding="utf-8")
    (tmp_path / "other-post" / "index.html").write_text(
        '<html><body><h1 class="page-title">Other Post</h1>Other</body></html>', encoding="utf-8")
    ref = tmp_path / "_template" / "reference.html"
    ref.write_text(REF_TEMPLATE, encoding="utf-8")
    (tmp_path / "post-sitemap.xml").write_text(
        '<?xml version="1.0"?>\n<urlset>'
        '<url><loc>./old-post/</loc><lastmod>2026-01-01T00:00:00+00:00</lastmod></url>'
        '<url><loc>./other-post/</loc><lastmod>2026-01-01T00:00:00+00:00</lastmod></url>'
        '</urlset>', encoding="utf-8")
    for mod in (config_mod, se, sb):
        monkeypatch.setattr(mod, "UNISCOLIAN_ROOT", tmp_path, raising=False)
    monkeypatch.setattr(config_mod, "UNISCOLIAN_REFERENCE_POST", ref)
    monkeypatch.setattr(se, "UNISCOLIAN_REFERENCE_POST", ref)
    monkeypatch.setattr(config_mod, "POST_REGISTRY_PATH", tmp_path / "_template" / "post_registry.json")
    monkeypatch.setattr(sm_mod, "POST_REGISTRY_PATH", tmp_path / "_template" / "post_registry.json", raising=False)
    monkeypatch.setattr(se, "generate_featured_image",
        lambda topic, title, slug: {"source": "mock", "file_exists": False,
            "relative_path": f"wp-content/uploads/2026/01/{slug}-featured.jpg"})
    yield tmp_path

# --- parsing ---
def test_parse_full_https_url():
    assert parse_update_target("https://uniscolian.com/best-budget-laptop-2026/") == "best-budget-laptop-2026"
def test_parse_relative_and_index_html():
    assert parse_update_target("./best-x/index.html") == "best-x"
    assert parse_update_target("best-x/") == "best-x"
    assert parse_update_target("best-x") == "best-x"
def test_parse_strips_query_and_upper():
    assert parse_update_target("https://uniscolian.com/Best-X/?ref=1") == "best-x"
def test_parse_empty_returns_empty():
    assert parse_update_target("") == "" and parse_update_target("   ") == ""
def test_parse_invalid_raises():
    with pytest.raises(ValueError): parse_update_target("../../etc/passwd")
    with pytest.raises(ValueError): parse_update_target("not a slug!!")

# --- update behavior ---
def test_update_replaces_index_html(fake_site):
    res = export_post_to_uniscolian(markdown=NEW_MD, topic="t", update_slug="old-post")
    html = (fake_site / "old-post" / "index.html").read_text(encoding="utf-8")
    assert "New Title" in html and "Old content" not in html
    assert res["updated"] is True and res["slug"] == "old-post" and res["slug_renamed"] is False
def test_update_does_not_touch_sitemap(fake_site):
    before = (fake_site / "post-sitemap.xml").read_text(encoding="utf-8")
    export_post_to_uniscolian(markdown=NEW_MD, topic="t", update_slug="old-post")
    assert (fake_site / "post-sitemap.xml").read_text(encoding="utf-8") == before
def test_update_no_suffix_and_no_new_folder(fake_site):
    res = export_post_to_uniscolian(markdown=NEW_MD, topic="t", update_slug="old-post")
    assert res["slug"] == "old-post" and not (fake_site / "old-post-2").exists()
def test_update_nonexistent_errors_without_writes(fake_site):
    res = export_post_to_uniscolian(markdown=NEW_MD, topic="t", update_slug="ghost-post")
    assert res.get("error") and res["updated"] is False and not (fake_site / "ghost-post").exists()
def test_empty_update_url_uses_new_post_flow(fake_site):
    res = export_post_to_uniscolian(markdown=NEW_MD, topic="brand new topic", update_slug="")
    assert res["updated"] is False
    assert f"./{res['slug']}/" in (fake_site / "post-sitemap.xml").read_text(encoding="utf-8")
def test_update_preserves_other_posts(fake_site):
    before = (fake_site / "other-post" / "index.html").read_text(encoding="utf-8")
    export_post_to_uniscolian(markdown=NEW_MD, topic="t", update_slug="old-post")
    assert (fake_site / "other-post" / "index.html").read_text(encoding="utf-8") == before
def test_update_refreshes_registry(fake_site):
    export_post_to_uniscolian(markdown=NEW_MD, topic="t", update_slug="old-post")
    assert sm_mod.build_registry(fake_site, force=False)["old-post"] == "New Title"
def test_update_twice_idempotent_single_sidebar(fake_site):
    export_post_to_uniscolian(markdown=NEW_MD, topic="t", update_slug="old-post")
    export_post_to_uniscolian(markdown="# Third Title\n## Intro\nx\n", topic="t", update_slug="old-post")
    html = (fake_site / "old-post" / "index.html").read_text(encoding="utf-8")
    assert "Third Title" in html and html.count("cf-sidebar-related-widget") <= 1
def test_update_overwrites_featured_image(fake_site, monkeypatch):
    ym_dir = fake_site / "wp-content" / "uploads" / "2026/01"
    ym_dir.mkdir(parents=True, exist_ok=True)
    (ym_dir / "old-post-featured.jpg").write_bytes(b"OLDIMG")
    def fake_gen(topic, title, slug):
        (ym_dir / f"{slug}-featured.jpg").write_bytes(b"NEWIMG")
        return {"source": "mock", "file_exists": True,
                "relative_path": f"wp-content/uploads/2026/01/{slug}-featured.jpg"}
    monkeypatch.setattr(se, "generate_featured_image", fake_gen)
    export_post_to_uniscolian(markdown=NEW_MD, topic="t", update_slug="old-post", generate_image=True)
    assert (ym_dir / "old-post-featured.jpg").read_bytes() == b"NEWIMG"


def test_registry_cache_not_polluted_by_tests(tmp_path, monkeypatch):
    """Regression: running tests must NOT write to production cache."""
    prod_cache = sm_mod.POST_REGISTRY_PATH  # default production path
    if prod_cache.exists():
        content = prod_cache.read_text(encoding="utf-8")
        assert "New Title" not in content, "Production cache polluted by test data"
        assert "Other Post" not in content, "Production cache polluted by test data"
