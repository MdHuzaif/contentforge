from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.tools import (
    analyze_meta_description,
    analyze_title,
    check_heading_hierarchy,
    compute_seo_report,
    content_length_check,
    engagement_check,
    extract_heading_sequence,
    extract_markdown_headings,
    internal_link_suggestions,
    keyword_density,
    readability_feedback,
)


def test_extract_markdown_headings():
    content = """
# Main Title
Some intro text.
## Sub Heading 1
Content 1.
### Section A
Content A.
## Sub Heading 2
Content 2.
    """
    headings = extract_markdown_headings(content)
    assert headings["h1"] == ["Main Title"]
    assert headings["h2"] == ["Sub Heading 1", "Sub Heading 2"]
    assert headings["h3"] == ["Section A"]


def test_extract_heading_sequence():
    content = """
# Title
## H2 One
### H3 One
## H2 Two
    """
    seq = extract_heading_sequence(content)
    assert seq == [
        (1, "Title"),
        (2, "H2 One"),
        (3, "H3 One"),
        (2, "H2 Two"),
    ]


def test_keyword_density():
    content = "best ai tools are amazing. You should use best ai tools for productivity."
    res = keyword_density(content, "best ai tools")
    assert res["occurrences"] == 2
    assert res["total_words"] > 0
    assert res["density_pct"] > 0
    assert res["in_first_100_words"] is True
    assert res["score"] > 0


def test_analyze_title():
    title = "Top 10 Best AI Tools for Writers in 2026 Guide"
    res = analyze_title(title, "best ai tools")
    assert res["has_keyword"] is True
    assert res["has_number"] is True
    assert res["has_power_word"] is True
    assert res["score"] > 0


def test_analyze_meta_description():
    desc = "Discover the best ai tools to boost your content workflow. This guide covers everything you need to know about productivity software."
    res = analyze_meta_description(desc, "best ai tools")
    assert res["length_ok"] is True
    assert res["has_keyword"] is True
    assert res["score"] == 10


def test_check_heading_hierarchy():
    headings = {"h1": ["Title"], "h2": ["Overview of best ai tools", "Features"], "h3": []}
    seq = [(1, "Title"), (2, "Overview of best ai tools"), (2, "Features")]
    res = check_heading_hierarchy(headings, seq, "best ai tools")
    assert res["single_h1"] is True
    assert res["no_skipped_levels"] is True
    assert res["keyword_in_h2"] is True
    assert res["score"] == 15


def test_readability_feedback():
    text = "ContentForge AI is a powerful content engine. It helps users write great articles. Readers love clear and simple text."
    res = readability_feedback(text)
    assert "flesch_score" in res
    assert "status" in res
    assert res["score"] > 0


def test_content_length_check():
    res = content_length_check(1600, {"avg_word_count": 1400})
    assert res["word_count"] == 1600
    assert res["score"] == 15


def test_engagement_check():
    content = """
# Guide
- Point 1
- Point 2

| Col 1 | Col 2 |
|---|---|
| A | B |

[Link](https://example.com)

## FAQ
Is this good? Yes.
    """
    res = engagement_check(content)
    assert res["has_lists"] is True
    assert res["has_table"] is True
    assert res["has_faq"] is True
    assert res["has_links"] is True
    assert res["score"] == 10


def test_internal_link_suggestions():
    headings = {"h1": ["Title"], "h2": ["Introduction Section", "Main Part"], "h3": []}
    sugs = internal_link_suggestions("ai tools", ["content engine", "ai writing"], headings)
    assert len(sugs) == 2
    assert "content engine" in sugs[0]
    assert "Introduction Section" in sugs[0]


def test_compute_seo_report():
    content = """
# Best AI Tools Guide
Here is the best ai tools guide for everyone.
## Understanding Best AI Tools
- Feature one
- Feature two

| Tool | Rating |
|---|---|
| Tool A | 5/5 |

[Source](https://example.com)

## FAQ Section
What are the best ai tools?
    """
    title = "Top 10 Best AI Tools for 2026 Ultimate Guide"
    meta_desc = "Discover the best ai tools to boost your productivity. Read our comprehensive review of top platforms with features, pricing, and comparisons for 2026."
    r = compute_seo_report(content, title, meta_desc, "best ai tools", ["ai writing"])
    assert "seo_score" in r
    assert "checks" in r
    assert "improvements" in r
    assert "internal_link_suggestions" in r
    assert isinstance(r["seo_score"], int)
    assert 0 <= r["seo_score"] <= 100


def main():
    test_extract_markdown_headings()
    test_extract_heading_sequence()
    test_keyword_density()
    test_analyze_title()
    test_analyze_meta_description()
    test_check_heading_hierarchy()
    test_readability_feedback()
    test_content_length_check()
    test_engagement_check()
    test_internal_link_suggestions()
    test_compute_seo_report()
    print("LEVEL 7 SEO TOOLS VERIFIED — All tests passed successfully.")


if __name__ == "__main__":
    main()
