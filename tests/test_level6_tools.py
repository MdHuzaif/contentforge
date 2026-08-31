from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.tools import (
    aggregate_metrics,
    analyze_html,
    count_words,
    extract_headings,
    extract_main_text,
    get_meta_info,
    readability_score,
)
from backend.tools.serp_scraper import clean_html, _decode_ddg_url


def test_clean_html():
    raw = "<p>Hello <b>World</b> &amp; friends!</p><script>alert('hi');</script>"
    cleaned = clean_html(raw)
    assert "Hello World & friends!" in cleaned
    assert "alert" not in cleaned


def test_decode_ddg_url():
    url_ddg = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpath%3Fq%3D1"
    decoded = _decode_ddg_url(url_ddg)
    assert decoded == "https://example.com/path?q=1"

    plain = "https://example.com"
    assert _decode_ddg_url(plain) == plain


def test_extract_headings():
    html_sample = """
    <html>
      <head><title>Test Page</title></head>
      <body>
        <h1>Main Heading</h1>
        <h2>Sub Heading 1</h2>
        <h2>Sub Heading 2</h2>
        <h3>Section 3</h3>
      </body>
    </html>
    """
    headings = extract_headings(html_sample)
    assert headings["h1"] == ["Main Heading"]
    assert headings["h2"] == ["Sub Heading 1", "Sub Heading 2"]
    assert headings["h3"] == ["Section 3"]


def test_extract_main_text():
    html_sample = """
    <html>
      <nav>Navigation bar content</nav>
      <body>
        <header>Header content</header>
        <script>var x = 1;</script>
        <p>This is the main visible text content of the page.</p>
        <footer>Footer info</footer>
      </body>
    </html>
    """
    text = extract_main_text(html_sample)
    assert "This is the main visible text content" in text
    assert "Navigation bar content" not in text
    assert "Header content" not in text
    assert "Footer info" not in text
    assert "var x = 1" not in text


def test_count_words():
    text = "ContentForge AI is a powerful content engine."
    assert count_words(text) == 7
    assert count_words("") == 0


def test_readability_score():
    text = "ContentForge AI is a powerful content engine. It helps users write great articles. Readers love clear and simple text."
    score = readability_score(text)
    assert isinstance(score, float)
    assert score > 0


def test_get_meta_info():
    html_sample = """
    <html>
      <head>
        <title>Sample SEO Title</title>
        <meta name="description" content="This is a test meta description for SEO analysis."/>
        <link rel="canonical" href="https://example.com/canonical"/>
        <script type="application/ld+json">{"@context": "https://schema.org", "@type": "Article"}</script>
      </head>
    </html>
    """
    meta = get_meta_info(html_sample)
    assert meta["title"] == "Sample SEO Title"
    assert meta["meta_description"] == "This is a test meta description for SEO analysis."
    assert meta["has_meta_description"] is True
    assert meta["has_schema"] is True
    assert meta["has_canonical"] is True


def test_analyze_html():
    html_sample = """
    <html>
      <head>
        <title>Competitor Article</title>
        <meta name="description" content="Great competitor article about AI content."/>
      </head>
      <body>
        <h1>AI Content Generation</h1>
        <h2>Introduction</h2>
        <p>Artificial intelligence is transforming content creation workflows. Content engines automate repetitive tasks efficiently.</p>
        <h2>Benefits</h2>
        <ul>
          <li>Speed</li>
          <li>Scale</li>
        </ul>
        <table><tr><td>Data</td></tr></table>
        <img src="img.jpg" alt="AI"/>
        <a href="https://external.com/article">External Link</a>
        <a href="/internal">Internal Link</a>
      </body>
    </html>
    """
    analysis = analyze_html(html_sample, url="https://example.com/page")
    assert analysis["url"] == "https://example.com/page"
    assert analysis["word_count"] > 0
    assert analysis["h1_count"] == 1
    assert analysis["h2_count"] == 2
    assert analysis["image_count"] == 1
    assert analysis["total_links"] == 2
    assert analysis["external_links_count"] == 1
    assert analysis["meta"]["has_meta_description"] is True
    assert analysis["engagement_signals"]["has_lists"] is True
    assert analysis["engagement_signals"]["has_table"] is True


def test_aggregate_metrics():
    analyses = [
        {
            "word_count": 1000,
            "h2_count": 3,
            "h3_count": 2,
            "image_count": 5,
            "readability": 65.0,
            "meta": {"has_meta_description": True, "has_schema": True},
            "engagement_signals": {"has_lists": True, "has_table": False, "has_video_embed": True}
        },
        {
            "word_count": 1500,
            "h2_count": 5,
            "h3_count": 4,
            "image_count": 8,
            "readability": 60.0,
            "meta": {"has_meta_description": True, "has_schema": False},
            "engagement_signals": {"has_lists": True, "has_table": True, "has_video_embed": False}
        }
    ]
    agg = aggregate_metrics(analyses)
    assert agg["competitor_count"] == 2
    assert agg["avg_word_count"] == 1250.0
    assert agg["avg_h2_count"] == 4.0
    assert agg["pct_with_meta_description"] == 100.0
    assert agg["pct_with_schema"] == 50.0
    assert agg["pct_with_lists"] == 100.0
    assert agg["pct_with_table"] == 50.0
    assert agg["pct_with_video"] == 50.0


def test_aggregate_metrics_empty():
    agg = aggregate_metrics([])
    assert agg["competitor_count"] == 0
    assert agg["avg_word_count"] == 0.0


def main():
    test_clean_html()
    test_decode_ddg_url()
    test_extract_headings()
    test_extract_main_text()
    test_count_words()
    test_readability_score()
    test_get_meta_info()
    test_analyze_html()
    test_aggregate_metrics()
    test_aggregate_metrics_empty()
    print("LEVEL 6 TOOLS VERIFIED — All tests passed successfully.")


if __name__ == "__main__":
    main()
