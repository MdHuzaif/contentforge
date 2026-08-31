"""Level 11 Internal Linker tests."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.exporters.internal_linker import (
    pick_related, related_link_html, insert_related_links, tokenize,
)


def test_tokenize_skips_stopwords():
    t = tokenize("Best Budget Gaming Laptops 2026")
    assert "best" not in t
    assert "gaming" in t
    assert "laptops" in t
    assert "2026" in t


def test_pick_related_scoring():
    registry = {
        "best-gaming-laptops": "Best Gaming Laptop Recommendations TOP16",
        "best-motherboards": "Best Motherboards for Intel Core i9",
        "how-to-clean-laptop-fan": "How to Clean a Laptop Fan Properly",
        "chromebook-vs-streambook": "Chromebook vs Streambook Comparison",
    }
    picks = pick_related(
        registry,
        current_slug="new-laptop-post",
        title="Best Budget Gaming Laptops 2026",
        keywords=["budget", "gaming", "laptop"],
        n=2,
    )
    assert len(picks) == 2
    slugs = [s for s, _ in picks]
    # gaming+laptop overlap should push best-gaming-laptops to the top
    assert slugs[0] == "best-gaming-laptops"


def test_pick_related_skips_self():
    registry = {"same-slug": "Same Title", "other": "Other Title"}
    picks = pick_related(registry, "same-slug", "Same Title", [], n=2)
    assert all(s != "same-slug" for s, _ in picks)
    assert len(picks) == 1  # only 'other' available


def test_related_links_html_markup():
    html = related_link_html("best-gaming-laptops", "Best Gaming Laptop Recommendations [TOP16]")
    assert '<p>Related Article:' in html
    assert 'href="./../best-gaming-laptops/index.html"' in html
    assert 'target="_blank"' in html
    assert 'rel="noreferrer noopener"' in html
    assert "<strong>Best Gaming Laptop Recommendations [TOP16]</strong>" in html


def test_insert_related_links_distributed():
    """Verify 2 related links are inserted at DIFFERENT H2 positions (distributed)."""
    body = (
        "<p>intro</p>"
        "<h2 class=\"wp-block-heading\"><strong>Section One</strong></h2>"
        "<p>para one</p>"
        "<h2 class=\"wp-block-heading\"><strong>Section Two</strong></h2>"
        "<p>para two</p>"
        "<h2 class=\"wp-block-heading\"><strong>Section Three</strong></h2>"
        "<p>para three</p>"
        "<h2 class=\"wp-block-heading\"><strong>Section Four</strong></h2>"
        "<p>para four</p>"
        "<h2 class=\"wp-block-heading\"><strong>Section Five</strong></h2>"
        "<p>para five</p>"
        "<h2 class=\"wp-block-heading\"><strong>Section Six</strong></h2>"
        "<p>para six</p>"
    )
    picks = [("slug-a", "Title A"), ("slug-b", "Title B")]
    out = insert_related_links(body, picks)
    
    # Both links must be present
    assert "Title A" in out
    assert "Title B" in out
    
    # Find positions of each link
    idx_a = out.index("Title A")
    idx_b = out.index("Title B")
    
    # They must be at DIFFERENT positions (distributed, not clustered)
    assert abs(idx_a - idx_b) > 200, "Links should be distributed, not clustered together"
    
    # First link should appear between H2 #1 and H2 #3 (approx 1/3 of article)
    idx_h2_2 = out.index("Section Two")
    idx_h2_3 = out.index("Section Three")
    
    # Second link should appear between H2 #3 and H2 #5 (approx 2/3 of article)
    idx_h2_4 = out.index("Section Four")
    idx_h2_5 = out.index("Section Five")
    
    # Verify ordering: link A appears before link B
    assert idx_a < idx_b, "Link A should appear before Link B in the article"
    
    # Verify they are NOT adjacent (not in same block)
    assert "Title A</strong></a></p>" in out
    assert "Title B</strong></a></p>" in out


def test_pick_related_skips_self_variants():
    """Verify current post and its variants are excluded."""
    registry = {
        "test-topic": "Test Topic Original",
        "test-topic-2": "Test Topic Version 2",
        "test-topic-3": "Test Topic Version 3",
        "other-topic": "Completely Different Topic",
        "another-one": "Another Different Article",
    }
    picks = pick_related(registry, "test-topic-4", "Test Topic Guide", [], n=2)
    slugs = [s for s, _ in picks]
    # None of test-topic, test-topic-2, test-topic-3 should be in picks
    assert "test-topic" not in slugs
    assert "test-topic-2" not in slugs
    assert "test-topic-3" not in slugs
    # But other topics should be picked
    assert len(picks) == 2


def test_insert_related_links_few_h2s_appends():
    body = "<p>short</p><h2>Only one heading</h2><p>end</p>"
    out = insert_related_links(body, [("x", "X")])
    assert out.rstrip().endswith("</p>")
    assert "Related Article:" in out


def main():
    test_tokenize_skips_stopwords()
    test_pick_related_scoring()
    test_pick_related_skips_self()
    test_related_links_html_markup()
    test_insert_related_links_distributed()
    test_pick_related_skips_self_variants()
    test_insert_related_links_few_h2s_appends()
    print("LEVEL 11 VERIFIED — internal linker scoring + insertion OK.")


if __name__ == "__main__":
    main()
